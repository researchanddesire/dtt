"""Compile the actual DHCP parsing/receive functions with offline C ports."""
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "src/services/dhcp_server_patch.c"


def function(source, signature):
    start = source.index(signature)
    # Upstream C functions close at column zero; nested blocks are indented.
    end = source.index("\n}", source.index("{", start)) + 2
    return source[start:end]


class DhcpParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="dtt-dhcp-parser-")
        temporary = Path(cls.directory.name)
        source = SOURCE.read_text()
        fixture = (HERE / "fixture.c.in").read_text()
        definitions = "\n".join(re.findall(
            r"^#define (?:DHCP(?:DISCOVER|REQUEST|DECLINE|RELEASE)|DHCP_OPTION_\w+|DHCPS_STATE_\w+|DHCPS_DEBUG)\s+[^\n]+",
            source, re.MULTILINE,
        ))
        fixture = fixture.replace("// ACTUAL_DEFINITIONS", definitions)
        for marker, signature in {
            "OPTIONS": "static u8_t parse_options(",
            "MESSAGE": "static s16_t parse_msg(",
            "HANDLER": "static void handle_dhcp(",
            "INSERT": "static void node_insert_to_list(",
            "REMOVE": "void node_remove_from_list(",
        }.items():
            fixture = fixture.replace("// ACTUAL_" + marker, function(source, signature))
        cls.executable = temporary / "dhcp-parser"
        path = temporary / "fixture.c"
        path.write_text(fixture)
        command = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", str(path), "-o", str(cls.executable),
        ]
        subprocess.run(command, check=True)
        print("Tested DHCP source SHA-256:", hashlib.sha256(SOURCE.read_bytes()).hexdigest())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_group(self, group):
        subprocess.run([str(self.executable), group], check=True, timeout=60)

    def test_exact_option_buffers_and_protocol_states(self):
        self.run_group("options")

    def test_deterministic_exact_buffer_fuzz(self):
        self.run_group("fuzz")

    def test_receive_lengths_chains_and_cleanup(self):
        self.run_group("receive")

    def test_lease_validation_replay_release_and_allocation_failures(self):
        self.run_group("leases")


if __name__ == "__main__":
    unittest.main()
