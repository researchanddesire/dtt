import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from check_firmware_size import (
    APPROVED_PARTITION_GIT_BLOB,
    V1_PARTITION_GIT_BLOB,
    REQUIRED_HEADROOM_BYTES,
    FirmwareSizeError,
    file_sha256,
    git_blob_sha1,
    inspect_firmware,
    main,
    markdown_summary,
    ota_slot_sizes,
    parse_partition_size,
)


FIRMWARE_ROOT = Path(__file__).resolve().parents[2] / "software" / "firmware"
APPROVED_PARTITION = FIRMWARE_ROOT / "partition-v2.csv"
V1_PARTITION = FIRMWARE_ROOT / "partition-v1.csv"
V2_PARTITION = FIRMWARE_ROOT / "partition-v2.csv"


class FirmwareSizeTests(unittest.TestCase):
    @staticmethod
    def write_compiled_partition(directory: str) -> tuple[Path, str]:
        partition_binary = Path(directory) / "partitions.bin"
        partition_binary.write_bytes(b"compiled approved partition")
        return partition_binary, file_sha256(partition_binary)

    def test_repository_partition_is_exact_approved_layout(self):
        self.assertEqual(
            git_blob_sha1(APPROVED_PARTITION), APPROVED_PARTITION_GIT_BLOB
        )
        self.assertEqual(ota_slot_sizes(APPROVED_PARTITION), [0x780000, 0x780000])
        self.assertEqual(git_blob_sha1(V1_PARTITION), V1_PARTITION_GIT_BLOB)
        self.assertEqual(ota_slot_sizes(V1_PARTITION), [0x140000, 0x140000])
        self.assertEqual(git_blob_sha1(V2_PARTITION), APPROVED_PARTITION_GIT_BLOB)

    def test_partition_sizes_accept_platformio_suffixes(self):
        self.assertEqual(parse_partition_size("0x140000"), 0x140000)
        self.assertEqual(parse_partition_size("1280K"), 0x140000)
        self.assertEqual(parse_partition_size("1M"), 1024 * 1024)

    def test_image_at_limit_passes_and_reports_all_summary_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "firmware.bin"
            partition_binary, partition_binary_sha256 = (
                self.write_compiled_partition(directory)
            )
            maximum = 0x780000 - REQUIRED_HEADROOM_BYTES
            firmware.write_bytes(b"\0" * maximum)

            result = inspect_firmware(
                environment="staging",
                partition=APPROVED_PARTITION,
                partition_binary=partition_binary,
                firmware=firmware,
                expected_partition_binary_sha256=partition_binary_sha256,
            )

            self.assertTrue(result.passed)
            self.assertEqual(result.maximum_firmware_bytes, 7_847_936)
            self.assertEqual(result.remaining_bytes, REQUIRED_HEADROOM_BYTES)
            summary = markdown_summary(result)
            self.assertIn("Partition file", summary)
            self.assertIn("Compiled partition SHA-256", summary)
            self.assertIn("OTA slot capacity", summary)
            self.assertIn("Firmware binary", summary)
            self.assertIn("Remaining in OTA slot", summary)
            self.assertIn("OTA slot used", summary)

    def test_image_one_byte_over_limit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "firmware.bin"
            partition_binary, partition_binary_sha256 = (
                self.write_compiled_partition(directory)
            )
            firmware.write_bytes(
                b"\0" * (0x780000 - REQUIRED_HEADROOM_BYTES + 1)
            )

            import check_firmware_size

            original_sha256 = check_firmware_size.APPROVED_PARTITION_BINARY_SHA256
            check_firmware_size.APPROVED_PARTITION_BINARY_SHA256 = (
                partition_binary_sha256
            )
            try:
                with contextlib.redirect_stdout(
                    io.StringIO()
                ), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = main(
                        [
                            "--environment",
                            "production",
                            "--partition",
                            str(APPROVED_PARTITION),
                            "--partition-binary",
                            str(partition_binary),
                            "--firmware",
                            str(firmware),
                        ]
                    )
            finally:
                check_firmware_size.APPROVED_PARTITION_BINARY_SHA256 = original_sha256
            self.assertEqual(exit_code, 1)

    def test_partition_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            partition = Path(directory) / "partition.csv"
            partition_binary, partition_binary_sha256 = (
                self.write_compiled_partition(directory)
            )
            firmware = Path(directory) / "firmware.bin"
            partition.write_bytes(APPROVED_PARTITION.read_bytes() + b"\n")
            firmware.write_bytes(b"firmware")

            with self.assertRaisesRegex(FirmwareSizeError, "partition table changed"):
                inspect_firmware(
                    environment="production",
                    partition=partition,
                    partition_binary=partition_binary,
                    firmware=firmware,
                    expected_partition_binary_sha256=partition_binary_sha256,
                )

    def test_compiled_partition_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            partition_binary = Path(directory) / "partitions.bin"
            firmware = Path(directory) / "firmware.bin"
            partition_binary.write_bytes(b"unexpected partition table")
            firmware.write_bytes(b"firmware")

            with self.assertRaisesRegex(
                FirmwareSizeError, "compiled partition artifact changed"
            ):
                inspect_firmware(
                    environment="staging",
                    partition=APPROVED_PARTITION,
                    partition_binary=partition_binary,
                    firmware=firmware,
                )

    def test_partition_requires_two_ota_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            partition = Path(directory) / "partition.csv"
            partition.write_text(
                "# Name,Type,SubType,Offset,Size,Flags\n"
                "app0,app,ota_0,0x10000,0x140000,\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(FirmwareSizeError, "at least two"):
                ota_slot_sizes(partition)


if __name__ == "__main__":
    unittest.main()
