Import("env")
import csv
import os
import re
import socket
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


def get_local_ip():
    try:
        # Create a socket connection to an external server (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error getting local IP: {e}")
        return None

# Function to check if SW_VERSION is already in CPPDEFINES
def get_build_flag_value(flag_name):
    try:
        build_flags = env.ParseFlags(env['BUILD_FLAGS'])
        all_defines = build_flags.get('CPPDEFINES', [])
        
        for define in all_defines:
            if isinstance(define, (list, tuple)) and len(define) >= 2 and define[0] == flag_name:
                print(f"Found Build Flag {flag_name} = {define[1]}")
                return define[1]
        
        print(f"Found Build Flag {flag_name} = None")
        return None
    except KeyError:
        return None

# Function to check if a flag is defined (with or without value)
def is_build_flag_defined(flag_name):
    return has_build_define(flag_name)

# Replace "localhost" with the local IP address in all BUILD_FLAGS
def replace_localhost_in_flags():
    local_ip = get_local_ip()
    if not local_ip:
        print("No local IP found, skipping localhost replacement")
        return
    
    build_flags = env.get('BUILD_FLAGS', [])
    new_flags = []
    replacements = []
    
    for flag in build_flags:
        if isinstance(flag, str) and 'localhost' in flag:
            new_flag = flag.replace('localhost', local_ip)
            replacements.append((flag, new_flag))
            new_flags.append(new_flag)
        else:
            new_flags.append(flag)
    
    if replacements:
        print(f"\nLocalhost -> {local_ip}")
        print(f"{'Key':<20}{'Old':<25}{'New'}")
        print("-" * 65)
        for orig, repl in replacements:
            if '=' in orig:
                key = orig.split('=')[0].replace('-D ', '').strip()
                old_val = orig.split('=', 1)[1].strip('"')
                new_val = repl.split('=', 1)[1].strip('"')
            else:
                key, old_val, new_val = orig, orig, repl
            print(f"{key:<20}{old_val:<25}{new_val}")
        print()
    
    env.Replace(BUILD_FLAGS=new_flags)


# Replace localhost with local IP (only for VERSIONDEV builds)
if is_build_flag_defined('VERSIONDEV'):
    print("VERSIONDEV is defined")
    
    local_ip = get_local_ip()
    print(f"Detected local IP: {local_ip}")
    
    replace_localhost_in_flags()
    
    print(f"Final BUILD_FLAGS: {env['BUILD_FLAGS']}")
else:
    print("VERSIONDEV is not defined")
