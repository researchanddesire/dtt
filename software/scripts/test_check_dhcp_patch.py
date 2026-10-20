"""Synthetic GNU map regressions; no firmware execution or network access."""
from pathlib import Path
import tempfile
import unittest

from check_dhcp_patch import REQUIRED_SECTIONS, verify_link_map


OBJECT = ".pio/build/production-v1/src/services/dhcp_server_patch.c.o"


def sections(*, address="0x00000000400db988", size="0x47a", origin=OBJECT,
             omitted=None, wrapped=True):
    return "".join(
        f" {name}" + ("\n                " if wrapped else " ") +
        f"{address} {size} {origin}\n"
        for name in REQUIRED_SECTIONS if name != omitted
    )


def link_map(retained=None, discarded="", prefix=""):
    if retained is None:
        retained = sections()
    return (prefix + "Discarded input sections\n" + discarded +
            "\nMemory Configuration\n\nLinker script and memory map\n" + retained)


class DhcpLinkMapTests(unittest.TestCase):
    def check(self, content, valid=False):
        with tempfile.TemporaryDirectory(prefix="dtt-dhcp-map-") as directory:
            path = Path(directory) / "firmware.map"
            path.write_text(content)
            if valid:
                verify_link_map(path)
            else:
                with self.assertRaises(ValueError):
                    verify_link_map(path)

    def test_accepts_retained_wrapped_and_single_line_entries(self):
        for wrapped in (True, False):
            with self.subTest(wrapped=wrapped):
                self.check(link_map(sections(wrapped=wrapped)), valid=True)

    def test_discarded_zero_entries_do_not_hide_valid_retained_entries(self):
        self.check(link_map(discarded=sections(address="0x0")), valid=True)

    def test_each_required_function_must_be_retained(self):
        for section in REQUIRED_SECTIONS:
            with self.subTest(section=section):
                self.check(link_map(sections(omitted=section)))

    def test_discarded_or_load_only_patch_does_not_pass(self):
        self.check(link_map("", discarded=sections()))
        self.check(link_map(f"LOAD {OBJECT}\n", discarded=sections(address="0x0")))

    def test_zero_address_or_zero_size_does_not_pass(self):
        self.check(link_map(sections(address="0x0000000000000000")))
        self.check(link_map(sections(size="0x0")))

    def test_sdk_archive_member_anywhere_is_rejected(self):
        for member in ("dhcpserver.c.obj", "dhcpserver.c.o", "dhcpserver.o",
                       "dhcpserver.obj", "apps/dhcpserver.c.obj"):
            for position in ("prefix", "discarded", "retained"):
                with self.subTest(member=member, position=position):
                    sdk = f"/sdk/liblwip.a({member})\n"
                    kwargs = {position: sdk + sections() if position == "retained" else sdk}
                    self.check(link_map(**kwargs))
        self.check(link_map(prefix="/sdk/liblwip.a:dhcpserver.c.o\n"))

    def test_wrong_or_tampered_object_origin_is_rejected(self):
        for origin in (
            ".pio/build/production-v1/src/services/dhcp_server_patch.c.o.old",
            ".pio/build/production-v1/src/services/other.c.o",
            ".pio/build/production-v1/src/services/dhcp_server_patch.cc.o",
            "/sdk/libother.a(src/services/dhcp_server_patch.c.o)",
            OBJECT + " injected trailing text",
        ):
            with self.subTest(origin=origin):
                self.check(link_map(sections(origin=origin)))

    def test_missing_or_ambiguous_retained_boundary_is_rejected(self):
        self.check(sections())
        self.check(link_map() + "Linker script and memory map\n" + sections())
        self.check(link_map() + "Discarded input sections\n")

    def test_duplicate_or_malformed_required_entries_are_rejected(self):
        self.check(link_map(sections() + sections()))
        self.check(link_map(sections().replace("0x47a", "invalid", 1)))
        self.check(link_map(sections().replace(" .text.handle_dhcp\n", " .text.handle_dhcp 0x1\n", 1)))

    def test_missing_or_invalid_utf8_map_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="dtt-dhcp-map-") as directory:
            path = Path(directory) / "missing.map"
            with self.assertRaises(ValueError):
                verify_link_map(path)
            path.write_bytes(b"\xff")
            with self.assertRaises(ValueError):
                verify_link_map(path)


if __name__ == "__main__":
    unittest.main()
