#!/usr/bin/env python3
"""Verify the flash-size declaration in an ESP application image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ESP_IMAGE_MAGIC = 0xE9
ESP32_FLASH_SIZE_IDS = {
    1 * 1024 * 1024: 0,
    2 * 1024 * 1024: 1,
    4 * 1024 * 1024: 2,
    8 * 1024 * 1024: 3,
    16 * 1024 * 1024: 4,
}


def verify_image_flash_size(path: Path, expected_flash_size_bytes: int) -> None:
    expected_size_id = ESP32_FLASH_SIZE_IDS.get(expected_flash_size_bytes)
    if expected_size_id is None:
        raise ValueError(
            f"unsupported expected flash size: {expected_flash_size_bytes} bytes"
        )
    header = path.read_bytes()[:4]
    if len(header) != 4 or header[0] != ESP_IMAGE_MAGIC:
        raise ValueError("artifact is not an ESP application image")
    flash_size_id = header[3] >> 4
    if flash_size_id != expected_size_id:
        raise ValueError(
            f"image must declare {expected_flash_size_bytes // (1024 * 1024)} MiB "
            f"flash (size id {expected_size_id}, got {flash_size_id})"
        )


def verify_migration_image(path: Path) -> None:
    verify_image_flash_size(path, 16 * 1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--expected-flash-size-bytes",
        type=int,
        default=16 * 1024 * 1024,
    )
    args = parser.parse_args()
    try:
        verify_image_flash_size(args.image, args.expected_flash_size_bytes)
    except (OSError, ValueError) as error:
        print(f"ESP image check failed: {error}", file=sys.stderr)
        return 1
    print(
        "ESP image declares "
        f"{args.expected_flash_size_bytes // (1024 * 1024)} MiB flash: {args.image}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
