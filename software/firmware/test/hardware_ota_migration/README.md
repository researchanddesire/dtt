# Wired DTT OTA migration validation

These environments and the local HTTP resolver exist only for a connected lab
DTT. Staging and production builds never define
`DTT_MIGRATION_LAB_INSECURE_HTTP`.

The `migration-lab` environment also pauses for 30 seconds after rebooting
through the migrated 16 MiB bootloader while the legacy partition table is
still active. The `MIGRATOR_LAB_BOOTLOADER_CHECKPOINT` marker is the window for
a wired readback of both regions. No staging or production environment defines
this pause.

Build each application with an explicit local resolver origin:

```sh
PLATFORMIO_BUILD_FLAGS='-D RAD_SERVER=\"http://192.168.1.149:8765\"' \
  RELEASE_BUILD_SHA=1111111111111111 pio run -e lab-ota-v1 -j 1
PLATFORMIO_BUILD_FLAGS='-D RAD_SERVER=\"http://192.168.1.149:8765\"' \
  RELEASE_BUILD_SHA=2222222222222222 pio run -e lab-ota-v2 -j 1
PLATFORMIO_BUILD_FLAGS='-D RAD_SERVER=\"http://192.168.1.149:8765\"' \
  pio run -e migration-lab -j 1
```

The server starts in `hold` mode. Its control endpoint (`POST /__lab/control`)
accepts `{"mode": ...}` with `hold`, `legacy-update`, `corrupt-migration`,
`corrupt-final`, `pause-final`, `migrate`, and `unreachable`, and
`{"gate": true|false}`.
This permits an operator to prove no-update behavior, hash rejection for both
migration and final application artifacts, and the complete migration.

- The bridge stages the final application before it changes anything, so
  `corrupt-final` and `pause-final` must end with
  `MIGRATOR_REFUSED final-firmware-unavailable`,
  `MIGRATOR_RETURNING_TO_PREVIOUS_FIRMWARE`, and the previous firmware
  booting again. Switch to `hold` at that point: the previous firmware
  otherwise installs the bridge again on its next boot.
- `unreachable` drops every device connection unanswered, as an outage
  would. Switched on once the bridge has booted, it must end the same way.
- `legacy-update` offers the image given with `--v1` (and `--v1-build`) to a
  legacy-layout device. Use it to move the running firmware into its other
  OTA slot, so both starting positions are exercised.
- With `--approved-bootloaders <sha256,...>` and the gate on, a device that
  reports any other bootloader is not offered the bridge, as the dashboard
  resolver does. With the gate off the bridge itself must refuse that device
  and return it to its firmware.
- `--bridge-url` and `--v2-url` serve the artifacts from another origin, for
  example HTTPS storage; the bytes must match the local files.
- To exercise the network install that remains under the V2 table, erase the
  staging record (`esptool erase_region 0xF08000 0x1000`) after
  `PARTITION_TABLE_WRITE_OK`. The bridge must then print
  `MIGRATOR_FINAL_OTA_OK` instead of `MIGRATOR_FINAL_ACTIVATED`.

Start each run from a field-style image: the legacy bootloader and table, an
NVS partition holding Wi-Fi credentials and a trainer ID, and the firmware
under test in `app0` or `app1`. Bootloaders from other Arduino-ESP32 releases
cover the refusal path.

Always take and checksum a wired flash backup before using this harness. Never
publish a lab artifact or leave a device running a lab build.
