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
