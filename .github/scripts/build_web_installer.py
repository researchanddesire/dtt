#!/usr/bin/env python3
"""Build and validate a merged ESP Web Tools factory image."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    chip: str
    chip_id: int
    flash_size: str
    capacity: int
    bootloader_offset: int
    flash_size_id: int
    flash_mode_id: int
    flash_freq_id: int


PROFILES = {
    "esp32-4mb": Profile(
        "esp32", 0, "4MB", 4 * 1024 * 1024, 0x1000, 0x2, 0x2, 0x0
    ),
    "esp32-16mb": Profile(
        "esp32", 0, "16MB", 16 * 1024 * 1024, 0x1000, 0x4, 0x2, 0x0
    ),
    "esp32s3-16mb": Profile(
        "esp32s3", 9, "16MB", 16 * 1024 * 1024, 0x0, 0x4, 0x2, 0x0
    ),
}


def require_image(path: Path, label: str) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"{label} image is missing or empty: {path}")
    return path


def find_boot_app0() -> Path:
    platformio_home = Path(
        os.environ.get("PLATFORMIO_HOME_DIR", Path.home() / ".platformio")
    )
    active = (
        platformio_home
        / "packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin"
    )
    if active.is_file():
        return require_image(active, "boot_app0")
    candidates = sorted(
        platformio_home.glob(
            "packages/framework-arduinoespressif32*/tools/partitions/boot_app0.bin"
        )
    )
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one PlatformIO boot_app0.bin, found {len(candidates)}"
        )
    return require_image(candidates[0], "boot_app0")


def find_esptool() -> Path:
    platformio_home = Path(
        os.environ.get("PLATFORMIO_HOME_DIR", Path.home() / ".platformio")
    )
    active = platformio_home / "packages/tool-esptoolpy/esptool.py"
    if active.is_file():
        return active
    candidates = sorted(platformio_home.glob("packages/tool-esptoolpy*/esptool.py"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one PlatformIO esptool.py, found {len(candidates)}")
    return require_image(candidates[0], "esptool.py")


def partition_offset(path: Path, partition_name: str) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.reader(line for line in handle if not line.lstrip().startswith("#"))
        for row in rows:
            if row and row[0].strip() == partition_name:
                return int(row[3].strip(), 0)
    raise RuntimeError(f"partition {partition_name!r} was not found in {path}")


def build_components(
    profile: Profile,
    build_dir: Path,
    boot_app0: Path,
    filesystem: Path | None = None,
    filesystem_offset: int | None = None,
) -> list[tuple[int, Path]]:
    components = [
        (
            profile.bootloader_offset,
            require_image(build_dir / "bootloader.bin", "bootloader"),
        ),
        (0x8000, require_image(build_dir / "partitions.bin", "partition table")),
        (0xE000, require_image(boot_app0, "boot_app0")),
        (0x10000, require_image(build_dir / "firmware.bin", "application")),
    ]
    if filesystem is not None:
        if filesystem_offset is None:
            raise RuntimeError("a filesystem offset is required with a filesystem image")
        components.append(
            (filesystem_offset, require_image(filesystem, "filesystem"))
        )
    components = sorted(components)
    for (offset, path), (next_offset, _) in zip(components, components[1:]):
        if offset + path.stat().st_size > next_offset:
            raise RuntimeError(
                f"component at {hex(offset)} overlaps component at {hex(next_offset)}"
            )
    if components[-1][0] + components[-1][1].stat().st_size > profile.capacity:
        raise RuntimeError("the final component exceeds the physical flash capacity")
    return components


def merge_command(
    esptool: Path,
    profile: Profile,
    output: Path,
    components: list[tuple[int, Path]],
) -> list[str]:
    command = [
        sys.executable,
        str(esptool),
        "--chip",
        profile.chip,
        "merge_bin",
        "--output",
        str(output),
        "--flash_mode",
        "keep",
        "--flash_freq",
        "keep",
        "--flash_size",
        profile.flash_size,
    ]
    for offset, path in components:
        command.extend((hex(offset), str(path)))
    return command


def validate_merged_image(
    output: Path, profile: Profile, components: list[tuple[int, Path]]
) -> None:
    content = require_image(output, "merged web installer").read_bytes()
    if len(content) > profile.capacity:
        raise RuntimeError(
            f"merged image is {len(content)} bytes, beyond {profile.capacity}-byte flash"
        )

    for offset in (profile.bootloader_offset, 0x10000):
        if offset >= len(content) or content[offset] != 0xE9:
            raise RuntimeError(f"ESP image magic is missing at {hex(offset)}")

    bootloader_header = content[
        profile.bootloader_offset : profile.bootloader_offset + 4
    ]
    if len(bootloader_header) != 4:
        raise RuntimeError("merged bootloader header is incomplete")
    if bootloader_header[3] >> 4 != profile.flash_size_id:
        raise RuntimeError(
            f"merged bootloader does not declare {profile.flash_size} flash"
        )
    if bootloader_header[2] != profile.flash_mode_id:
        raise RuntimeError("merged bootloader flash mode does not match the profile")
    if bootloader_header[3] & 0x0F != profile.flash_freq_id:
        raise RuntimeError("merged bootloader flash frequency does not match the profile")
    extended_header = content[
        profile.bootloader_offset + 12 : profile.bootloader_offset + 14
    ]
    if len(extended_header) != 2:
        raise RuntimeError("merged bootloader extended header is incomplete")
    if int.from_bytes(extended_header, "little") != profile.chip_id:
        raise RuntimeError("merged bootloader chip ID does not match the profile")

    for offset, source_path in components:
        source = source_path.read_bytes()
        merged = content[offset : offset + len(source)]
        if offset == profile.bootloader_offset:
            # esptool deliberately rewrites flash mode/frequency/size bytes 2-3.
            matches = merged[:2] == source[:2] and merged[4:] == source[4:]
        else:
            matches = merged == source
        if not matches:
            raise RuntimeError(f"merged component mismatch at {hex(offset)}")


def build(args: argparse.Namespace) -> None:
    profile = PROFILES[args.profile]
    filesystem_offset = None
    if args.filesystem:
        if not args.partition_table:
            raise RuntimeError("--partition-table is required with --filesystem")
        filesystem_offset = partition_offset(
            args.partition_table, args.filesystem_partition
        )
    boot_app0 = args.boot_app0 or find_boot_app0()
    components = build_components(
        profile,
        args.build_dir,
        boot_app0,
        args.filesystem,
        filesystem_offset,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    esptool = args.esptool or find_esptool()
    subprocess.run(
        merge_command(esptool, profile, args.output, components), check=True
    )
    validate_merged_image(args.output, profile, components)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=tuple(PROFILES))
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--boot-app0", type=Path)
    parser.add_argument("--esptool", type=Path)
    parser.add_argument("--filesystem", type=Path)
    parser.add_argument("--partition-table", type=Path)
    parser.add_argument("--filesystem-partition", default="spiffs")
    args = parser.parse_args()
    try:
        build(args)
        print(f"Built validated web installer: {args.output}")
        return 0
    except Exception as error:
        print(f"Web installer build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
