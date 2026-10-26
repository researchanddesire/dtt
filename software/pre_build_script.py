Import("env")
import csv
import os
import sys
from pathlib import Path


def parse_size(value):
    normalized = value.strip().lower()
    multiplier = 1
    if normalized.endswith("kb"):
        multiplier = 1024
        normalized = normalized[:-2]
    elif normalized.endswith("mb"):
        multiplier = 1024 * 1024
        normalized = normalized[:-2]
    elif normalized.endswith("k"):
        multiplier = 1024
        normalized = normalized[:-1]
    elif normalized.endswith("m"):
        multiplier = 1024 * 1024
        normalized = normalized[:-1]
    return int(normalized, 0) * multiplier


def has_build_define(flag_name):
    build_flags = env.ParseFlags(env.get("BUILD_FLAGS", []))
    for define in build_flags.get("CPPDEFINES", []):
        if isinstance(define, (list, tuple)):
            if define and define[0] == flag_name:
                return True
        elif define == flag_name:
            return True
    return False


def validate_partition_table_fits_flash():
    partition_name = env.GetProjectOption("board_build.partitions")
    partition_path = Path(env.subst("$PROJECT_DIR")) / partition_name
    flash_size = env.BoardConfig().get("upload.flash_size")

    highest_address = 0
    with partition_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if not row or row[0].lstrip().startswith("#"):
                continue
            if len(row) < 5 or not row[3].strip():
                raise ValueError(
                    f"Partition table {partition_name} must use explicit offsets"
                )
            highest_address = max(
                highest_address,
                parse_size(row[3]) + parse_size(row[4]),
            )

    configured_flash_size = parse_size(flash_size)
    if (
        has_build_define("PROVISION")
        and configured_flash_size != 16 * 1024 * 1024
    ):
        raise ValueError(
            "Provisioning builds require exactly 16 MiB flash; "
            f"configured value is {flash_size}."
        )
    if highest_address > configured_flash_size:
        raise ValueError(
            f"Partition table {partition_name} ends at 0x{highest_address:x}, "
            f"beyond the configured {flash_size} flash. Set "
            "board_upload.flash_size to match the physical device."
        )


validate_partition_table_fits_flash()


# The dashboard API credential is supplied at build time (a CI secret) and is
# never committed. Environments opt in with custom_rad_public_key = environment;
# others keep src/wifiSettings.cpp's DEV_KEY_123 default.
def apply_api_credential():
    if has_build_define("RAD_PUBLIC_KEY"):
        return
    if env.GetProjectOption("custom_rad_public_key", "") != "environment":
        return
    credential = os.environ.get("RAD_PUBLIC_KEY", "").strip()
    if credential:
        env.Append(CPPDEFINES=[("RAD_PUBLIC_KEY", env.StringifyMacro(credential))])
        print("RAD_PUBLIC_KEY supplied from the build environment")
    elif not has_build_define("VERSIONDEV"):
        print("WARNING: RAD_PUBLIC_KEY is not set; this release build uses DEV_KEY_123")


apply_api_credential()


# Build flags may contain local credentials. Never print or rewrite them, and
# never infer a development endpoint from the machine's network interfaces.
if str(env.get("PIOENV", "")).startswith(("production", "staging")):
    for forbidden in ("BYPASS_EEPROM", "FORCE_TRAINER_ID", "WIFI_SSID", "WIFI_PASSWORD"):
        if has_build_define(forbidden):
            raise ValueError("Release builds cannot embed development identity or Wi-Fi settings")


sys.path.insert(0, str(Path(env.subst("$PROJECT_DIR")) / "scripts"))
if str(env.get("PIOENV", "")) in ("development-v1", "development-v2"):
    from development_server import development_server

    if has_build_define("RAD_SERVER"):
        raise ValueError("Configure Development through ignored local.settings.json")
    server = development_server(Path(env.subst("$PROJECT_DIR")))
    env.Append(CPPDEFINES=[("RAD_SERVER", env.StringifyMacro(server))])

from check_dhcp_patch import verify_link_map


def _flat(values):
    if isinstance(values, str) or not hasattr(values, "__iter__"):
        yield str(values)
        return
    for value in values:
        yield from _flat(value)


def linker_map_path(env):
    # Arduino links with -Map=$BUILD_DIR/$PROGNAME.map. ESP-IDF profiles use
    # CMake's link flags, which name the map after the CMake project. The
    # linker writes the last map option it receives.
    path = "$BUILD_DIR/${PROGNAME}.map"
    for flag in _flat(env.get("LINKFLAGS", [])):
        for prefix in ("-Wl,--Map=", "-Wl,-Map="):
            if flag.startswith(prefix):
                path = flag[len(prefix):].strip('"')
    return Path(env.subst(path))


def verify_dhcp_patch(source, target, env):
    verify_link_map(linker_map_path(env))


env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", verify_dhcp_patch)
