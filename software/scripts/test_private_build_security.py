"""Exercise the real pre-build guard with synthetic build settings only."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1] / "firmware"
sys.path.insert(0, str(ROOT.parent / "dev"))


class Environment(dict):
    def ParseFlags(self, flags):
        return {"CPPDEFINES": self["defines"]}

    def GetProjectOption(self, option, default=None):
        if option == "board_build.partitions":
            return "partition-v1.csv"
        return self.get("options", {}).get(option, default)

    def Append(self, CPPDEFINES):
        self["defines"] = self["defines"] + CPPDEFINES

    def StringifyMacro(self, value):
        return '"%s"' % value

    def subst(self, value):
        return (value.replace("$PROJECT_DIR", str(ROOT))
                .replace("$BUILD_DIR", str(self.get("build_dir", ROOT / ".pio/build/test")))
                .replace("${PROGNAME}", self.get("program", "firmware")))

    def BoardConfig(self):
        return {"upload.flash_size": self.get("flash", "4MB")}

    def AddPostAction(self, target, callback):
        self.setdefault("post_actions", []).append((target, callback))


def run_guard(environment):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        runpy.run_path(str(ROOT / "pre_build_script.py"), init_globals={
            "Import": lambda name: None, "env": environment,
        })
    return output.getvalue()


class PrivateBuildSecurityTests(unittest.TestCase):
    def test_variant_development_uses_explicit_local_server_only(self):
        for profile in ("development-v1", "development-v2"):
            env = Environment(PIOENV=profile, defines=["VERSIONDEV"])
            with mock.patch("development_server.development_server", return_value="http://192.168.2.59:3000") as load:
                self.assertEqual(run_guard(env), "")
            load.assert_called_once_with(ROOT.parent / "dev")
            self.assertIn(("RAD_SERVER", '"http://192.168.2.59:3000"'), env["defines"])
            with self.assertRaises(ValueError):
                run_guard(Environment(PIOENV=profile, defines=["VERSIONDEV", "RAD_SERVER"]))

    def test_release_does_not_read_local_development_settings(self):
        for profile in ("staging-v1", "staging-v2", "production-v1", "production-v2"):
            with mock.patch("development_server.development_server", side_effect=AssertionError("Release read local settings")):
                self.assertEqual(run_guard(Environment(PIOENV=profile, defines=[])), "")

    def test_development_flags_are_neither_logged_nor_rewritten(self):
        env = Environment(PIOENV="development", defines=[
            ("WIFI_PASSWORD", "synthetic-do-not-log"),
            ("RAD_SERVER", "http://localhost:3000"), "VERSIONDEV",
        ], BUILD_FLAGS=["synthetic-do-not-log"])
        self.assertEqual(run_guard(env), "")
        self.assertEqual(env["BUILD_FLAGS"], ["synthetic-do-not-log"])

    def test_release_rejects_embedded_local_identity_and_network(self):
        for track in ("production-v1", "production-v2", "staging-v1", "staging-v2"):
            for flag in ("WIFI_SSID", "WIFI_PASSWORD", "BYPASS_EEPROM", "FORCE_TRAINER_ID"):
                with self.subTest(track=track, flag=flag), self.assertRaises(ValueError):
                    run_guard(Environment(PIOENV=track, defines=[flag]))

    def test_release_credential_comes_from_the_environment_unprinted(self):
        credential = "synthetic-credential-do-not-log"
        env = Environment(PIOENV="staging-v1", defines=[],
                          options={"custom_rad_public_key": "environment"})
        with mock.patch.dict(os.environ, {"RAD_PUBLIC_KEY": credential}):
            output = run_guard(env)
        self.assertNotIn(credential, output)
        self.assertIn(("RAD_PUBLIC_KEY", '"%s"' % credential), env["defines"])

    def test_partition_flash_limit_still_applies(self):
        with self.assertRaises(ValueError):
            run_guard(Environment(PIOENV="development", defines=[], flash="1MB"))

    def test_elf_post_action_rejects_a_missing_dhcp_patch(self):
        with tempfile.TemporaryDirectory(prefix="dtt-build-hook-") as directory:
            env = Environment(PIOENV="production-v1", defines=[], build_dir=directory)
            run_guard(env)
            self.assertEqual(len(env["post_actions"]), 1)
            target, callback = env["post_actions"][0]
            self.assertEqual(target, "$BUILD_DIR/${PROGNAME}.elf")
            with self.assertRaises(ValueError):
                callback([], [], env)

    def test_elf_post_action_reads_the_selected_program_map(self):
        with tempfile.TemporaryDirectory(prefix="dtt-build-hook-") as directory:
            env = Environment(PIOENV="production-v1", defines=[],
                              build_dir=directory, program="fixture")
            run_guard(env)
            names = ("handle_dhcp", "dhcps_start", "dhcps_stop")
            body = "Linker script and memory map\n" + "".join(
                f" .text.{name} 0x400d0000 0x10 src/services/dhcp_server_patch.c.o\n"
                for name in names
            )
            (Path(directory) / "fixture.map").write_text(body)
            env["post_actions"][0][1]([], [], env)

    def test_elf_post_action_follows_the_linker_map_option(self):
        with tempfile.TemporaryDirectory(prefix="dtt-build-hook-") as directory:
            env = Environment(PIOENV="staging-v2", defines=[], build_dir=directory)
            run_guard(env)
            # ESP-IDF profiles name the map after the CMake project.
            env["LINKFLAGS"] = [
                '-Wl,-Map="$BUILD_DIR/${PROGNAME}.map"',
                ["-Wl,--gc-sections", f'-Wl,--Map="{directory}/DT_Trainer.map"'],
            ]
            names = ("handle_dhcp", "dhcps_start", "dhcps_stop")
            body = "Linker script and memory map\n" + "".join(
                f" .text.{name} 0x400d0000 0x10 src/services/dhcp_server_patch.c.o\n"
                for name in names
            )
            (Path(directory) / "firmware.map").write_text(body)
            with self.assertRaises(ValueError):
                env["post_actions"][0][1]([], [], env)
            (Path(directory) / "DT_Trainer.map").write_text(body)
            env["post_actions"][0][1]([], [], env)


if __name__ == "__main__":
    unittest.main()
