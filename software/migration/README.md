# DTT 16 MiB OTA migration bridge

The migration bridge is a third, temporary firmware role. It is built against
the legacy V1 partition table so an installed DTT can receive it through its
existing OTA slot, while its ESP image header declares the physical 16 MiB
flash that the bridge is permitted to migrate.

The bridge is published first as a validating release, but it is not eligible
for delivery until the required hardware validation succeeds. Its compatibility
rule then restricts it to the inspected 16 MiB legacy-layout cohort:

- CI builds, size-checks, and publishes a validating immutable release. The
  resolver excludes it until every required validation is recorded.
- `approved_bootloader_hashes.txt` contains only bootloader-region hashes
  confirmed by two independent reads from inspected physical DTTs. Every
  other bootloader still fails closed before changing flash layout.
- `approved_bootloader_transitions.txt` pins the only allowed byte-exact
  4 MiB-to-16 MiB bootloader transformation. The deployed bootloader code is
  retained; only its flash-size header and validation hash change.
- V2 firmware is published into the independently controlled V2 lane.

## Migration sequence

1. The normal V1 firmware reports physical flash size, OTA slot size,
   partition layout, partition-table SHA-256, and bootloader SHA-256.
2. The resolver may eventually select a V2 migration release only for a DTT
   reporting at least 16 MiB of physical flash with the exact legacy layout.
3. If the bridge boots from legacy `app1`, it copies and verifies itself in
   legacy `app0`, selects `app0`, and reboots.
4. From `app0`, it snapshots identity into the unused final sector of legacy
   `app1`, derives the exact approved 16 MiB bootloader from the allowlisted
   deployed bytes, verifies a high-flash staging copy, copies it to the primary
   bootloader with the deployed ESP-IDF partition APIs, rewriting only the five
   sectors occupied by the bootloader image, verifies the entire region, and
   reboots while the legacy partition table is still installed.
5. After the migrated bootloader proves it can boot the bridge from `app0`, the
   bridge promotes the identity snapshot into the future migration-state
   sector, verifies both copies, writes the canonical V2 partition table, and
   verifies the table sector before rebooting.
6. Under the V2 table it verifies or restores the preserved identity, resolves
   the final V2 application, and installs it into the new `app1` slot.

The canonical 0x140000-slot table and the historical 0x1A0000-slot table are
accepted by exact sector hash; no geometry-only match is sufficient.

Secure Boot, flash encryption, unknown partition-table bytes, physical flash
below 16 MiB, and unapproved bootloaders are all hard failures. The ESP32 ROM
has no fallback primary bootloader, and the partition table also has no backup.
A power loss during either final copy cannot be made atomic. The bridge stages
and verifies every byte first, separates the bootloader and table writes with a
successful reboot, and remains restricted to the approved hardware cohort.

## Hardware activation checklist

1. Read the connected DTT's physical flash size, running OTA slot, partition
   table sector, bootloader region, security state, and identity fields without
   writing flash.
2. Confirm its partition-table hash equals one of the generated legacy hashes.
3. Build its exact 16 MiB bootloader from the pinned platform and prove it
   differs from the device bootloader only in the header byte and validation
   hash.
4. Record both exact region hashes and patch geometry, then rebuild.
5. Exercise legacy `app0` and `app1` starting positions, rejection before any
   critical write, the post-bootloader/pre-table reboot checkpoint, identity
   preservation, V2 final OTA, and wired recovery.
6. Only after those checks, mark both the bridge and final V2 release as
   hardware-validated, then promote the V2 production target.

There is no separate bridge target or toggle. After both releases reach 5/5 and
the V2 firmware is set as the production target, an eligible device routes
automatically from `legacy-v1` to the migration bridge, then to
`dtt-ota-16mb-v1`, and finally to the V2 firmware.
