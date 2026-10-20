#!/usr/bin/env python3
"""Fail a firmware build that cannot safely fit in the approved OTA slots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


APPROVED_PARTITION_GIT_BLOB = "87b066320a83be1d390fd4cdfea9d1b5b6bccea4"
APPROVED_PARTITION_BINARY_SHA256 = (
    "df8bb78d1134d502246d4ae7de59d397bc1d2529fa9c4affdd68aa78514e6c09"
)
V1_PARTITION_GIT_BLOB = "62778131c63221bcb0433e31ea5cde8eedc815f6"
V1_PARTITION_BINARY_SHA256 = (
    "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1"
)
REQUIRED_HEADROOM_BYTES = 16 * 1024
OTA_SUBTYPE = re.compile(r"^ota_[0-9]+$", re.IGNORECASE)


class FirmwareSizeError(ValueError):
    """Raised when the partition table or firmware artifact is invalid."""


@dataclass(frozen=True)
class FirmwareSizeResult:
    environment: str
    partition: Path
    partition_blob: str
    partition_binary: Path
    partition_binary_sha256: str
    firmware: Path
    slot_capacity: int
    firmware_bytes: int
    required_headroom: int

    @property
    def maximum_firmware_bytes(self) -> int:
        return self.slot_capacity - self.required_headroom

    @property
    def remaining_bytes(self) -> int:
        return self.slot_capacity - self.firmware_bytes

    @property
    def used_percent(self) -> float:
        return self.firmware_bytes * 100.0 / self.slot_capacity

    @property
    def passed(self) -> bool:
        return self.firmware_bytes <= self.maximum_firmware_bytes


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_partition_size(value: str) -> int:
    normalized = value.strip().lower()
    multiplier = 1
    if normalized.endswith("k"):
        multiplier = 1024
        normalized = normalized[:-1]
    elif normalized.endswith("m"):
        multiplier = 1024 * 1024
        normalized = normalized[:-1]
    try:
        size = int(normalized, 0) * multiplier
    except ValueError as error:
        raise FirmwareSizeError(f"invalid partition size: {value!r}") from error
    if size <= 0:
        raise FirmwareSizeError(f"partition size must be positive: {value!r}")
    return size


def ota_slot_sizes(partition: Path) -> list[int]:
    if not partition.is_file():
        raise FirmwareSizeError(f"partition table does not exist: {partition}")

    slots: list[int] = []
    with partition.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            if len(row) < 5:
                raise FirmwareSizeError(
                    f"partition row {line_number} has fewer than five columns"
                )
            partition_type = row[1].strip().lower()
            subtype = row[2].strip().lower()
            if partition_type == "app" and OTA_SUBTYPE.fullmatch(subtype):
                slots.append(parse_partition_size(row[4]))

    if len(slots) < 2:
        raise FirmwareSizeError(
            "partition table must contain at least two OTA application slots"
        )
    return slots


def inspect_firmware(
    *,
    environment: str,
    partition: Path,
    partition_binary: Path,
    firmware: Path,
    expected_partition_blob: str = APPROVED_PARTITION_GIT_BLOB,
    expected_partition_binary_sha256: str | None = None,
    required_headroom: int = REQUIRED_HEADROOM_BYTES,
) -> FirmwareSizeResult:
    partition_blob = git_blob_sha1(partition)
    if partition_blob != expected_partition_blob:
        raise FirmwareSizeError(
            "partition table changed: "
            f"expected Git blob {expected_partition_blob}, got {partition_blob}"
        )
    if not firmware.is_file():
        raise FirmwareSizeError(f"firmware artifact does not exist: {firmware}")
    if not partition_binary.is_file():
        raise FirmwareSizeError(
            f"compiled partition artifact does not exist: {partition_binary}"
        )

    partition_binary_sha256 = file_sha256(partition_binary)
    expected_binary_sha256 = (
        APPROVED_PARTITION_BINARY_SHA256
        if expected_partition_binary_sha256 is None
        else expected_partition_binary_sha256
    )
    if partition_binary_sha256 != expected_binary_sha256:
        raise FirmwareSizeError(
            "compiled partition artifact changed: "
            f"expected SHA-256 {expected_binary_sha256}, "
            f"got {partition_binary_sha256}"
        )

    slot_capacity = min(ota_slot_sizes(partition))
    if required_headroom < 0 or required_headroom >= slot_capacity:
        raise FirmwareSizeError("required headroom must be smaller than an OTA slot")

    return FirmwareSizeResult(
        environment=environment,
        partition=partition,
        partition_blob=partition_blob,
        partition_binary=partition_binary,
        partition_binary_sha256=partition_binary_sha256,
        firmware=firmware,
        slot_capacity=slot_capacity,
        firmware_bytes=firmware.stat().st_size,
        required_headroom=required_headroom,
    )


def markdown_summary(result: FirmwareSizeResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    return "\n".join(
        (
            f"### Firmware partition size — {result.environment}",
            "",
            "| Field | Value |",
            "| --- | ---: |",
            f"| Result | **{status}** |",
            f"| Partition file | `{result.partition}` |",
            f"| Partition Git blob | `{result.partition_blob}` |",
            f"| Compiled partition | `{result.partition_binary}` |",
            f"| Compiled partition SHA-256 | `{result.partition_binary_sha256}` |",
            f"| OTA slot capacity | {result.slot_capacity:,} bytes |",
            f"| Firmware binary | {result.firmware_bytes:,} bytes |",
            f"| Remaining in OTA slot | {result.remaining_bytes:,} bytes |",
            f"| Required headroom | {result.required_headroom:,} bytes |",
            f"| Maximum accepted image | {result.maximum_firmware_bytes:,} bytes |",
            f"| OTA slot used | {result.used_percent:.2f}% |",
            "",
        )
    )


def append_summary(summary: str, path: str | None) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(summary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--partition", required=True, type=Path)
    parser.add_argument("--partition-binary", required=True, type=Path)
    parser.add_argument("--firmware", required=True, type=Path)
    parser.add_argument(
        "--expected-partition-blob",
        default=APPROVED_PARTITION_GIT_BLOB,
    )
    parser.add_argument(
        "--expected-partition-binary-sha256",
        default=APPROVED_PARTITION_BINARY_SHA256,
    )
    parser.add_argument(
        "--summary-file",
        default=os.environ.get("GITHUB_STEP_SUMMARY"),
        help="Markdown summary file (defaults to GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    try:
        result = inspect_firmware(
            environment=args.environment,
            partition=args.partition,
            partition_binary=args.partition_binary,
            firmware=args.firmware,
            expected_partition_blob=args.expected_partition_blob,
            expected_partition_binary_sha256=args.expected_partition_binary_sha256,
        )
    except (FirmwareSizeError, OSError) as error:
        print(f"Firmware size check failed: {error}", file=sys.stderr)
        return 1

    summary = markdown_summary(result)
    print(summary, end="")
    append_summary(summary, args.summary_file)
    if not result.passed:
        print(
            "Firmware size check failed: "
            f"{result.firmware_bytes:,} bytes exceeds the "
            f"{result.maximum_firmware_bytes:,}-byte limit",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
