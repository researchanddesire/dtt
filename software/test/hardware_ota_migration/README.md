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

The server starts in `hold` mode. Its control endpoint accepts `hold`,
`corrupt-migration`, `corrupt-final`, `pause-final`, and `migrate`. This permits
an operator to prove no-update behavior, hash rejection for both migration and
final application artifacts, recovery after the V2 partition table is
installed but before final firmware is available, and the complete final OTA.
The `corrupt-final` case may partially overwrite inactive V2 `app1`; verify that
OTA selection remains on the bridge in `app0`, then switch to `migrate` and
prove that a clean retry repairs and boots `app1`.

Always take and checksum a wired flash backup before using this harness. Never
publish a lab artifact or leave a device running a lab build.
