# DHCP parser backport regression tests

Run offline from the repository root:

```sh
python3 test/security_dhcp_parser/test_parser.py
```

Requires Python 3 and a C11 compiler with AddressSanitizer and
UndefinedBehaviorSanitizer (`CC` may select the compiler). The runner extracts
the actual `parse_options`, `parse_msg`, lease-list helpers and `handle_dhcp`
functions from `src/services/dhcp_server_patch.c`; it does not maintain a second
parser implementation. Temporary binaries are removed after the run.

Four test groups cover exact-sized and truncated option buffers, all one- and
two-byte inputs, 100,000 deterministic fuzz inputs, PAD/END and unknown options,
message/IP minimum lengths, discover/request/renew/release, invalid options
without lease mutation, both lease-allocation failures, packet size guards,
multi-pbuf copying, short copies and cleanup. Allocation and network ports are
synthetic. No packet is sent and no live device or network service is used.

## Source and advisory

The replacement starts from Espressif's
[ESP-IDF v4.4.7 DHCP server source](https://github.com/espressif/esp-idf/blob/v4.4.7/components/lwip/apps/dhcpserver/dhcpserver.c).
The unmodified source has SHA-256
`a7ff751cf191de080f60bf592de26a3b8768785c774e4ce9bd1b824b4cb7c8c4`.
Its Apache-2.0 license is retained at `src/services/dhcp_server_patch.LICENSE`.

[GHSA-g764-gwc3-75m5 / CVE-2026-45160](https://github.com/espressif/esp-idf/security/advisories/GHSA-g764-gwc3-75m5)
describes out-of-bounds option reads in the SoftAP DHCP server. The local
backport applies the bounds-checking approach of Espressif's
[upstream fix 8b4b5d53](https://github.com/espressif/esp-idf/commit/8b4b5d53):
skip PAD, stop at END, and validate each length and payload before access.
The advisory's version list does not enumerate v4.4.7; applicability here was
confirmed by inspecting that pinned source's unchecked option accesses.

This is a local adaptation, not a claim that the entire SDK is upgraded.
Malformed options return IDLE before lease changes. Additional local guards
reject packets shorter than 240 bytes or larger than `INT16_MAX`, copy every
pbuf segment, and handle packet/lease allocation failures. The compile guard
pins the replacement to ESP-IDF 4.4.7; firmware build hooks separately verify
the ELF link map selects this replacement instead of the SDK archive object.

These tests verify the extracted parsing and allocation paths, not the complete
radio/lwIP runtime, hardware DHCP interoperability, or every SDK vulnerability.
