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
  other bootloader is refused before anything is written, and the DTT returns
  to the firmware it was running. The one approved hash is the bootloader
  PlatformIO `espressif32@6.12.0` builds for a 4 MiB DIO 40 MHz image; a DTT
  flashed from any other toolchain version carries a different one.
- The dashboard resolver keeps its own copy of the approved bootloader and
  legacy-table hashes (`dttMigrationBridgeWouldRefuse` in rad-app
  `apps/web/src/lib/firmware/selection.ts`). Add a newly approved bootloader,
  and its migrated counterpart, there before assigning a bridge that accepts
  it.
- `approved_bootloader_transitions.txt` pins the only allowed byte-exact
  4 MiB-to-16 MiB bootloader transformation. The deployed bootloader code is
  retained; only its flash-size header and validation hash change.
- V2 firmware is published into the independently controlled V2 lane.

## Migration sequence

1. The normal V1 firmware reports physical flash size, OTA slot size,
   partition layout, partition-table SHA-256, and bootloader SHA-256.
2. The resolver selects the migration release only for a DTT reporting at
   least 16 MiB of physical flash, the exact legacy layout, an approved
   bootloader and legacy table, and a trainer ID the bridge can carry over.
   Every other 16 MiB DTT on the legacy layout stays on the V1 lane.
3. The bridge prepares while the firmware it replaced can still be booted. It
   checks the bootloader, the table, the flash size, the security state and
   the stored identity, then downloads the final V2 application into the
   flash the 16 MiB table will call `app1` and verifies it there. If any of
   this fails, it selects the previous firmware and reboots into it; nothing
   the legacy layout uses has been changed.
4. With the final firmware staged, the bridge confirms itself and switches
   Wi-Fi off. If it booted from legacy `app1`, it copies and verifies itself
   in legacy `app0`, selects `app0`, and reboots.
5. From `app0`, it snapshots identity into the unused final sector of legacy
   `app1`, derives the exact approved 16 MiB bootloader from the allowlisted
   deployed bytes, verifies a high-flash staging copy, copies it to the primary
   bootloader with the deployed ESP-IDF partition APIs, rewriting only the five
   sectors occupied by the bootloader image, verifies the entire region, and
   reboots while the legacy partition table is still installed.
6. After the migrated bootloader proves it can boot the bridge from `app0`, the
   bridge promotes the identity snapshot into the future migration-state
   sector, verifies both copies, writes the canonical V2 partition table, and
   verifies the table sector before rebooting.
7. Under the V2 table it verifies or restores the preserved identity, checks
   the staged application against its record once more, selects `app1`, and
   reboots into the final firmware. If that firmware's first start is
   interrupted, the bootloader returns to the bridge, which selects the staged
   copy again, up to four times. Only if the staged copy is missing, no longer
   matches, or has been tried four times does it resolve and install the final
   application over the network, retrying every minute.

Steps 4 to 7 use neither Wi-Fi nor the dashboard. The bridge has no display
code, so the screen stays dark from the moment it boots until the final
firmware starts; on the bench that is about a minute plus the download.

A bridge that cannot proceed prints `MIGRATOR_REFUSED <reason>` and
`MIGRATOR_RETURNING_TO_PREVIOUS_FIRMWARE`. The return selects the other
legacy slot explicitly, so it also works with bootloaders that cannot roll
back by themselves. `MIGRATOR_NO_PREVIOUS_FIRMWARE` followed by
`MIGRATOR_FAIL_CLOSED` means the other slot no longer holds the previous
firmware; the bridge then retries every minute.

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
