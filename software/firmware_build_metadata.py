Import("env")

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(env.subst("$PROJECT_DIR")) / "scripts"))
from ble_memory import install
install(env)
from tls_log_size import install as install_tls_log_size
install_tls_log_size(env)


project_dir = Path(env.subst("$PROJECT_DIR"))
build_sha = os.getenv("RELEASE_BUILD_SHA", os.getenv("GITHUB_SHA", "unknown"))
if str(env.get("PIOENV", "")).startswith("migration-"):
    sys.path.insert(0, str(project_dir / "scripts"))
    from migration_build_identity import migration_build_identity

    build_sha = migration_build_identity(project_dir)

env.Append(
    CPPDEFINES=[
        (
            "FIRMWARE_BUILD_SHA",
            env.StringifyMacro(build_sha),
        )
    ]
)

# Staging hardware observation uses the ordinary application and normal updates.
profile = env.subst("$PIOENV")
if "arduino" in env.get("PIOFRAMEWORK", []):
    # Preserve the firmware's existing no-RTTI C++ behavior without sending a
    # C++-only option to SDK C sources (mbedTLS treats warnings as errors).
    env.Append(CXXFLAGS=["-fno-rtti"])
if profile == "staging" or profile.startswith("staging-"):
    if profile == "staging-v2":
        env.Append(LINKFLAGS=["-Wl,--wrap=log_printf"])
    variant = profile.split("-", 1)[1] if "-" in profile else "v1"
    env.Append(CPPDEFINES=[
        ("RAD_HIL_PRODUCT", env.StringifyMacro("dtt")),
        ("RAD_HIL_VARIANT", env.StringifyMacro(variant)),
        "RAD_HIL_ARDUINO_HTTP",
    ])

# Development screen rows and SDK logs share the serial writer.
if env.subst("$PIOENV").startswith("development") and "espidf" in env.get("PIOFRAMEWORK", []):
    env.Append(LINKFLAGS=["-Wl,--wrap=log_printf"])

# Model names describe this image's target, separate from measured physical RAM.
import sys
sys.path.insert(0, env.subst("$PROJECT_DIR"))
from serial_identity_build import install as install_serial_identity
install_serial_identity(env, "DTT")
