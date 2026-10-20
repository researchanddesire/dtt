# DTT firmware

Repository-wide rules (branches, Supabase projects, releases, secrets,
documentation) are in `../AGENTS.md`.

## Build

- Run `pio` from this directory. Release environments are `staging-v1`,
  `staging-v2`, `production-v1`, and `production-v2`; `migration-staging` and
  `migration-production` build the legacy-layout bridge.
- Staging firmware reports the `staging` track and checks
  `https://staging.researchanddesire.com`. Main firmware reports `main` and
  checks `https://dashboard.researchanddesire.com`.
- Environments marked `custom_rad_public_key = environment` take
  `RAD_PUBLIC_KEY` from the build environment (`pre_build_script.py`); all
  others, and builds without it, use the `DEV_KEY_123` default. Never write the
  credential into `platformio.ini`.

## Development Safety

- Keep stable `hashId`, physical flash size, partition layout, migration hops, checksum, reboot, and rollback behavior covered by native and hardware tests.
- Never commit credentials, local build products, or generated secrets.

## Device security

- Dashboard and update HTTPS verify the CA bundle, hostname and certificate dates through `firmware::CertificateDateClient`; never use `setInsecure()`. Profiles whose SDK lacks `MBEDTLS_HAVE_TIME_DATE` must keep `MBEDTLS_SSL_KEEP_PEER_CERTIFICATE`.
- `src/services/dhcp_server_patch.c` replaces the pinned ESP-IDF 4.4.7 SoftAP DHCP server, and every build fails unless the link map uses it. Re-review it before changing the SDK.
- Validate dashboard and BLE sessions with `SessionValidation.h` before parsing or persisting them. Keep its bounds in step with what rad-app's `get-settings` sends; a rejected page leaves the device on its cached session.
- Never log trainer IDs, request or response bodies, or Wi-Fi credentials. Release environments reject embedded Wi-Fi and identity defines.

## PR hardware validation

- Every PR into staging or main builds all hardware variants, including docs-only changes.
- Install the exact staging bundle for the PR merge SHA; production still builds.
- Require Build validation and Hardware validation in addition to existing checks.
- Firmware bundles and hardware evidence are Actions artifacts, never tracked files.
- The reviewed harness and fixture inventory live outside the runner work directory.
- Never infer product identity or flash capacity from a COM port or advertising name.
- Follow scripts/hil/README.md for enrollment, shared-device locks, and rollout.
- Keep Wi-Fi credentials, fixture identities, and raw device logs outside the repository.
- A missing device or incomplete three-minute observation must fail validation.

## Development display capture

- Development builds expose the read-only USB `screen` command; staging and production omit it.
- Follow ../developer-docs/docs/firmware/development-screen-capture.md; use the display mutex for snapshots and keep serial transmission outside it.
- Preserve the capture mirror when adding TFT bulk drawing paths. Keep capture files outside Git.

## Serial identity

- All firmware tracks expose the read-only boot/`info` identity described in ../developer-docs/docs/firmware/serial-identity.md.
- Keep one serial input reader; development screen commands register with it.
- Report target memory and measured memory separately; a label never authorizes flashing or motion.
