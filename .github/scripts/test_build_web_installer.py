#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).with_name("build_web_installer.py")
SPEC = importlib.util.spec_from_file_location("build_web_installer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildWebInstallerTests(unittest.TestCase):
    def test_profiles_use_platform_offsets_and_physical_capacity(self):
        self.assertEqual(MODULE.PROFILES["esp32-4mb"].bootloader_offset, 0x1000)
        self.assertEqual(MODULE.PROFILES["esp32-16mb"].capacity, 16 * 1024 * 1024)
        self.assertEqual(MODULE.PROFILES["esp32s3-16mb"].bootloader_offset, 0)
        self.assertEqual(MODULE.PROFILES["esp32-4mb"].flash_size_id, 0x2)
        self.assertEqual(MODULE.PROFILES["esp32-16mb"].flash_size_id, 0x4)
        self.assertEqual(MODULE.PROFILES["esp32-4mb"].chip_id, 0)
        self.assertEqual(MODULE.PROFILES["esp32s3-16mb"].chip_id, 9)

    def test_partition_offset_is_read_from_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "partitions.csv"
            table.write_text(
                "# Name,Type,SubType,Offset,Size\n"
                "littlefs,data,spiffs,0xc90000,0x1000\n",
                encoding="utf-8",
            )
            self.assertEqual(MODULE.partition_offset(table, "littlefs"), 0xC90000)

    def test_platformio_tools_prefer_the_active_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_boot = (
                root
                / "packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin"
            )
            stale_boot = (
                root
                / "packages/framework-arduinoespressif32@old/tools/partitions/boot_app0.bin"
            )
            active_esptool = root / "packages/tool-esptoolpy/esptool.py"
            stale_esptool = root / "packages/tool-esptoolpy@old/esptool.py"
            for path in (active_boot, stale_boot, active_esptool, stale_esptool):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"active" if "@old" not in str(path) else b"stale")

            with mock.patch.dict(
                MODULE.os.environ, {"PLATFORMIO_HOME_DIR": str(root)}
            ):
                self.assertEqual(MODULE.find_boot_app0(), active_boot)
                self.assertEqual(MODULE.find_esptool(), active_esptool)

    def test_validation_checks_magic_and_exact_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = MODULE.PROFILES["esp32-4mb"]
            sources = {}
            for offset, name, content in (
                (
                    0x1000,
                    "bootloader.bin",
                    b"\xe9\x01\x02\x03boot\x00\x00\x00\x00\x00\x00\x00\x00",
                ),
                (0x8000, "partitions.bin", b"partition-table"),
                (0xE000, "boot_app0.bin", b"boot-app"),
                (0x10000, "firmware.bin", b"\xe9firmware"),
            ):
                path = root / name
                path.write_bytes(content)
                sources[offset] = path
            merged = bytearray(b"\xff" * 0x10020)
            for offset, path in sources.items():
                content = path.read_bytes()
                merged[offset : offset + len(content)] = content
            merged[0x1002] = 0x02
            merged[0x1003] = 0x20
            output = root / "web-installer.bin"
            output.write_bytes(merged)

            MODULE.validate_merged_image(output, profile, sorted(sources.items()))

            merged[0x10000] = 0
            output.write_bytes(merged)
            with self.assertRaisesRegex(RuntimeError, "magic"):
                MODULE.validate_merged_image(output, profile, sorted(sources.items()))

    def test_validation_rejects_wrong_declared_flash_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            for offset, name, content in (
                (
                    0x1000,
                    "bootloader.bin",
                    b"\xe9\x01\x02\x03boot\x00\x00\x00\x00\x00\x00\x00\x00",
                ),
                (0x8000, "partitions.bin", b"partition-table"),
                (0xE000, "boot_app0.bin", b"boot-app"),
                (0x10000, "firmware.bin", b"\xe9firmware"),
            ):
                path = root / name
                path.write_bytes(content)
                sources[offset] = path
            merged = bytearray(b"\xff" * 0x10020)
            for offset, path in sources.items():
                content = path.read_bytes()
                merged[offset : offset + len(content)] = content
            merged[0x1003] = 0x40
            output = root / "web-installer.bin"
            output.write_bytes(merged)

            with self.assertRaisesRegex(RuntimeError, "declare 4MB"):
                MODULE.validate_merged_image(
                    output,
                    MODULE.PROFILES["esp32-4mb"],
                    sorted(sources.items()),
                )

            merged[0x1003] = 0x20
            merged[0x1002] = 0x00
            output.write_bytes(merged)
            with self.assertRaisesRegex(RuntimeError, "flash mode"):
                MODULE.validate_merged_image(
                    output,
                    MODULE.PROFILES["esp32-4mb"],
                    sorted(sources.items()),
                )

            merged[0x1002] = 0x02
            merged[0x1003] = 0x21
            output.write_bytes(merged)
            with self.assertRaisesRegex(RuntimeError, "flash frequency"):
                MODULE.validate_merged_image(
                    output,
                    MODULE.PROFILES["esp32-4mb"],
                    sorted(sources.items()),
                )

            merged[0x1003] = 0x20
            merged[0x100C] = 0x09
            output.write_bytes(merged)
            with self.assertRaisesRegex(RuntimeError, "chip ID"):
                MODULE.validate_merged_image(
                    output,
                    MODULE.PROFILES["esp32-4mb"],
                    sorted(sources.items()),
                )

    def test_components_must_not_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_dir = root / "build"
            build_dir.mkdir()
            (build_dir / "bootloader.bin").write_bytes(b"\xe9" * 0x8000)
            (build_dir / "partitions.bin").write_bytes(b"partitions")
            (build_dir / "firmware.bin").write_bytes(b"\xe9firmware")
            boot_app0 = root / "boot_app0.bin"
            boot_app0.write_bytes(b"boot-app")

            with self.assertRaisesRegex(RuntimeError, "overlaps"):
                MODULE.build_components(
                    MODULE.PROFILES["esp32-4mb"], build_dir, boot_app0
                )


if __name__ == "__main__":
    unittest.main()
