#!/usr/bin/env python3
"""Calculate the immutable identity embedded in the DTT migration bridge."""

from __future__ import annotations

import hashlib
from pathlib import Path


INPUTS = (
    "platformio.ini",
    "partition-v1.csv",
    "partition-v2.csv",
    "migration/partition-legacy-ota-1a.csv",
    "generate_migration_assets.py",
    "firmware_build_metadata.py",
    "migration/approved_bootloader_hashes.txt",
    "migration/approved_bootloader_transitions.txt",
    "src/migration/main.cpp",
    "src/services/eeprom_service.cpp",
    "src/services/eeprom_service.h",
    "lib/FirmwareUpdateProtocol/src/DttMigrationPlan.h",
    "lib/FirmwareUpdateProtocol/src/FirmwareUpdateProtocol.h",
    "lib/FirmwareUpdateProtocol/src/FirmwareUpdateRuntime.cpp",
    "lib/FirmwareUpdateProtocol/src/FirmwareUpdateRuntime.h",
)


def migration_build_identity(project_dir: Path) -> str:
    digest = hashlib.sha256()
    for relative in INPUTS:
        path = project_dir / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    print(migration_build_identity(Path(__file__).resolve().parents[1] / "firmware"))
