import tempfile
import unittest
from pathlib import Path

from check_migration_image import verify_image_flash_size, verify_migration_image


class MigrationImageTests(unittest.TestCase):
    def test_accepts_esp32_16mb_header(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "firmware.bin"
            image.write_bytes(bytes((0xE9, 1, 2, 0x40)))
            verify_migration_image(image)

    def test_rejects_4mb_header(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "firmware.bin"
            image.write_bytes(bytes((0xE9, 1, 2, 0x20)))
            with self.assertRaisesRegex(ValueError, "16 MiB"):
                verify_migration_image(image)

    def test_accepts_4mb_header_when_explicitly_required(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "firmware.bin"
            image.write_bytes(bytes((0xE9, 1, 2, 0x20)))
            verify_image_flash_size(image, 4 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
