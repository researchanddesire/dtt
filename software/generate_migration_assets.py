Import("env")

import hashlib
import re
import subprocess
import sys
from pathlib import Path


if str(env.get("PIOENV", "")).startswith("migration-"):
    project_dir = Path(env.subst("$PROJECT_DIR"))
    generated_dir = Path(env.subst("$BUILD_DIR")) / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    framework_dir = Path(
        env.PioPlatform().get_package_dir("framework-arduinoespressif32")
    )
    generator = framework_dir / "tools" / "gen_esp32part.py"

    def partition_sector(csv_name):
        output = generated_dir / f"{Path(csv_name).stem}.bin"
        subprocess.run(
            [sys.executable, str(generator), str(project_dir / csv_name), str(output)],
            check=True,
        )
        content = output.read_bytes()
        if len(content) > 0x1000:
            raise RuntimeError(f"{csv_name} exceeds one flash sector")
        return content + bytes([0xFF]) * (0x1000 - len(content))

    legacy_sector = partition_sector("partition-v1.csv")
    legacy_ota_1a_sector = partition_sector(
        "migration/partition-legacy-ota-1a.csv"
    )
    v2_sector = partition_sector("partition-v2.csv")
    allowlist = []
    for line in (project_dir / "migration/approved_bootloader_hashes.txt").read_text().splitlines():
        value = line.split("#", 1)[0].strip().lower()
        if not value:
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RuntimeError(f"invalid approved bootloader SHA-256: {value}")
        allowlist.append(value)
    transitions = []
    for line in (
        project_dir / "migration/approved_bootloader_transitions.txt"
    ).read_text().splitlines():
        value = line.split("#", 1)[0].strip().lower()
        if not value:
            continue
        fields = value.split()
        if len(fields) != 6:
            raise RuntimeError(f"invalid approved bootloader transition: {value}")
        legacy_hash, migrated_hash, image_size, hash_offset, old_header, new_header = (
            fields
        )
        if not re.fullmatch(r"[0-9a-f]{64}", legacy_hash) or not re.fullmatch(
            r"[0-9a-f]{64}", migrated_hash
        ):
            raise RuntimeError(f"invalid bootloader transition hash: {value}")
        parsed = (
            legacy_hash,
            migrated_hash,
            int(image_size, 10),
            int(hash_offset, 10),
            int(old_header, 16),
            int(new_header, 16),
        )
        if (
            parsed[2] <= 32
            or parsed[2] > 0x7000
            or parsed[3] != parsed[2] - 32
            or parsed[0] == parsed[1]
            or parsed[4] > 0xFF
            or parsed[5] > 0xFF
            or parsed[4] == parsed[5]
        ):
            raise RuntimeError(f"unsafe bootloader transition geometry: {value}")
        transitions.append(parsed)
    transition_legacy_hashes = [transition[0] for transition in transitions]
    if (
        len(set(allowlist)) != len(allowlist)
        or len(set(transition_legacy_hashes)) != len(transition_legacy_hashes)
        or set(transition_legacy_hashes) != set(allowlist)
    ):
        raise RuntimeError(
            "every approved legacy bootloader must have exactly one transition"
        )

    def byte_array(content):
        rows = []
        for offset in range(0, len(content), 16):
            rows.append(
                "    " + ", ".join(f"0x{byte:02x}" for byte in content[offset : offset + 16])
            )
        return ",\n".join(rows)

    hashes = (
        ",\n".join(f'    "{value}"' for value in allowlist)
        if allowlist
        else "    nullptr"
    )
    transition_rows = ",\n".join(
        "    {"
        f'"{legacy_hash}", "{migrated_hash}", {image_size}U, {hash_offset}U, '
        f"0x{old_header:02x}, 0x{new_header:02x}"
        "}"
        for (
            legacy_hash,
            migrated_hash,
            image_size,
            hash_offset,
            old_header,
            new_header,
        ) in transitions
    )
    header = generated_dir / "DttMigrationAssets.h"
    header.write_text(
        "#pragma once\n\n"
        "#include <cstddef>\n"
        "#include <cstdint>\n\n"
        "namespace dtt_migration_generated {\n\n"
        "alignas(4) inline std::uint8_t V2_PARTITION_TABLE_SECTOR[0x1000] = {\n"
        f"{byte_array(v2_sector)}\n"
        "};\n\n"
        "inline constexpr const char *LEGACY_PARTITION_TABLE_SHA256[] = {\n"
        f'    "{hashlib.sha256(legacy_sector).hexdigest()}",\n'
        f'    "{hashlib.sha256(legacy_ota_1a_sector).hexdigest()}"\n'
        "};\n"
        "inline constexpr std::size_t LEGACY_PARTITION_TABLE_COUNT = 2;\n"
        f'inline constexpr char V2_PARTITION_TABLE_SHA256[] = "{hashlib.sha256(v2_sector).hexdigest()}";\n'
        "inline constexpr const char *APPROVED_BOOTLOADER_SHA256[] = {\n"
        f"{hashes}\n"
        "};\n"
        f"inline constexpr std::size_t APPROVED_BOOTLOADER_COUNT = {len(allowlist)};\n\n"
        "struct BootloaderTransition {\n"
        "    const char *legacyRegionSha256;\n"
        "    const char *migratedRegionSha256;\n"
        "    std::uint32_t imageSize;\n"
        "    std::uint32_t validationHashOffset;\n"
        "    std::uint8_t legacyHeaderByte;\n"
        "    std::uint8_t migratedHeaderByte;\n"
        "};\n\n"
        "inline constexpr BootloaderTransition BOOTLOADER_TRANSITIONS[] = {\n"
        f"{transition_rows}\n"
        "};\n"
        f"inline constexpr std::size_t BOOTLOADER_TRANSITION_COUNT = {len(transitions)};\n\n"
        "}  // namespace dtt_migration_generated\n",
        encoding="utf-8",
    )
    env.Append(CPPPATH=[str(generated_dir)])
