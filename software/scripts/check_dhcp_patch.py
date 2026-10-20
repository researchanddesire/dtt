"""Require the bounded DHCP parser implementation in a final GNU linker map."""
import argparse
from pathlib import Path
import re


REQUIRED_SECTIONS = (".text.handle_dhcp", ".text.dhcps_start", ".text.dhcps_stop")
PATCH_OBJECT = "src/services/dhcp_server_patch.c.o"
SDK_MEMBER = re.compile(
    r"\bliblwip\.a(?:\(\s*(?:[^()\r\n]*[/\\])?"
    r"dhcpserver(?:\.c)?\.(?:obj|o)\s*\)|:"
    r"\s*(?:[^\s:]*[/\\])?dhcpserver(?:\.c)?\.(?:obj|o)\b)",
    re.IGNORECASE,
)
SECTION = re.compile(
    r"^[ \t]+(\.text\.(?:handle_dhcp|dhcps_start|dhcps_stop))"
    r"(?=[ \t]|$)(.*)$"
)
ENTRY = re.compile(r"\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(.+?)\s*")


def verify_link_map(path):
    """Fail closed unless all three retained sections come from the patch.

    Discarded input sections and archive-selection summaries are not evidence
    of retained code. The SDK DHCP member is forbidden anywhere in the map,
    even when a second patched object is also mentioned.
    """
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError("DHCP link map is missing or unreadable") from error
    if SDK_MEMBER.search(content):
        raise ValueError("SDK DHCP server archive member is present")
    lines = content.splitlines()
    starts = [index for index, line in enumerate(lines)
              if line.strip() == "Linker script and memory map"]
    if len(starts) != 1:
        raise ValueError("DHCP link map has no unique retained-section boundary")
    retained = lines[starts[0] + 1:]
    if any(line.strip() == "Discarded input sections" for line in retained):
        raise ValueError("DHCP link map section boundaries are malformed")

    found = set()
    for index, line in enumerate(retained):
        section = SECTION.fullmatch(line)
        if section is None:
            continue
        name, entry = section.groups()
        if name in found:
            raise ValueError("DHCP link map contains an ambiguous required section")
        if not entry.strip():
            entry = retained[index + 1] if index + 1 < len(retained) else ""
        fields = ENTRY.fullmatch(entry)
        if fields is None:
            raise ValueError("DHCP retained section has no address, size, or object")
        address, size, origin = fields.groups()
        if int(address, 16) == 0 or int(size, 16) == 0:
            raise ValueError("DHCP required section is not retained code")
        origin = origin.replace("\\", "/")
        if ("(" in origin or ")" in origin or
                not (origin == PATCH_OBJECT or origin.endswith("/" + PATCH_OBJECT))):
            raise ValueError("DHCP required section does not use the patch object")
        found.add(name)
    if found != set(REQUIRED_SECTIONS):
        raise ValueError("DHCP patch retained sections are incomplete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path, help="Final firmware GNU linker map")
    args = parser.parse_args()
    try:
        verify_link_map(args.map)
    except ValueError as error:
        parser.exit(1, f"DHCP link guard failed: {error}\n")
    print("DHCP link guard passed: all required patched functions are retained")


if __name__ == "__main__":
    main()
