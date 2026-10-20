# Open-Source Deepthroat Trainer (DTT)

Firmware/software uses MPL-2.0 and hardware uses CERN-OHL-S v2; retain LICENSE,
LICENSES, and third-party notices. This is the canonical DTT repository;
`__legacy_DT_Trainer` and `__legacy_DT_Trainer-OSS` are retired and read-only.

## Layout

- `software/` is the PlatformIO firmware project. Run `pio` there and follow
  `software/AGENTS.md` for firmware rules.
- `hardware/` holds the CAD assembly, PCB source, and manufacturing outputs.
- `assembly-docs/` (build guide, published by the docs hub), `docs/` (user
  guides), and `developer-docs/` (engineering) document the device.
- `.github/` holds CI for the whole repository, with its scripts in
  `.github/scripts/`.

## Branches and history

- Never force-push, rewrite, or delete `staging` or `main`; the docs hub orders
  files by commit date.
- Persistent branches are lowercase `staging` and `main`. Fetch before branching.
- The firmware directory is `software/` (except the harness copy in `software/scripts/hil/`). `FIRMWARE_PATHS` in `pr-firmware.yml` and `pr-target-policy.yml` and the `publish_firmware.yml` push paths define it; keep them in sync.
- Firmware changes enter `staging` first: branch from `origin/staging` and open the PR into `staging`. Promote with a same-repository `staging` → `main` PR.
- A production fix may take firmware to `main` directly from a `fix/<issue>` branch (an owner prefix such as `AJ/fix/<issue>` also works) started from `origin/main`.
- Changes outside the firmware directory (documentation, hardware, BOMs, workflows) may open their PR straight into `main`; they need no build or hardware checks. `PR target policy` enforces these rules.
- After every merge into `main` that is not a promotion, `hotfix-sync.yml` merges `main` back into `staging` directly (main wins documentation, staging keeps its own firmware version) and opens a `main` → `staging` PR only when a conflict needs a person.
- Squash feature and fix PRs into one focused commit with a concise, imperative title. Merge `staging` → `main` promotions and `main` → `staging` sync PRs with a merge commit; never squash or rebase them.
- Documentation is the exception: see Documentation below.

## Supabase

- The only Supabase project agents and workflows address is `acjajruwevyyatztbkdf`, through the organization secret `SUPABASE_ACCESS_TOKEN`. Name it explicitly in every remote operation; never infer a project from a URL, environment variable, cached CLI link, neighboring repository or prior conversation.
- Firmware releases reach it only through the dashboard firmware API. PR hardware evidence videos go to its private `hil-evidence` bucket.
- `release_alpha.yml` and `release_production.yml` copy verified releases into
  its `dtt-firmware` aliases (`alpha`, `production`, `v/latest`).

## Firmware releases (Supabase only)

- Releases live only in Supabase. Never publish firmware through GitHub Pages,
  S3, or committed binaries.
- `publish_firmware.yml` runs on firmware pushes to `staging` and `main`: the
  control plane allocates the version, the rad-version-control app commits the
  bump, CI builds V1, V2, and the migration bridge, and signed immutable
  artifacts are published as `validating` releases.
- A release becomes update-eligible only after its artifacts and every
  required validation record verify. Never bypass a gate.
- `release_alpha.yml` and `release_production.yml` (manual, by release ID) copy
  a verified V1 release into the `dtt-firmware` aliases that legacy update
  checks read. `finalize_release.yml` adds the numeric tag and a
  metadata-only GitHub release.
- Release secrets live in the `firmware-staging` (branch `staging`) and
  `firmware-production` (branch `main`) environments: `FIRMWARE_PUBLISH_TOKEN`,
  `FIRMWARE_PROVENANCE_SIGNING_KEY_PEM`, and `RAD_PUBLIC_KEY`. Org-level:
  `RAD_VERSION_CONTROL_APP_ID`, `RAD_VERSION_CONTROL_PRIVATE_KEY`, and
  `SUPABASE_ACCESS_TOKEN`.

## Public repository safety

- `RAD_PUBLIC_KEY` is the shared dashboard API bearer credential, not a key.
  Release builds read it from the environment. Never commit it, local
  settings, test result dumps, or compiled images.
- CI scans source and history with gitleaks; keep the credential rule in
  `.gitleaks.toml`.
- Do not change physical flash sizes or partition offsets for deployed hardware.

## Hardware validation

- PRs into `staging` or `main` that change the firmware directory, or the validation tooling (`software/scripts/hil/`, `pr-firmware.yml`, `hardware-run.yml`, `.github/scripts/hil_evidence.py`), build every hardware variant and run the exact staging bundle for the PR merge SHA on the shared Test Rig. Other PRs skip both; `Build validation` and `Hardware validation` then pass without work.
- `PR target policy`, `Build validation` and `Hardware validation` are required on `staging` and `main`.
- The rig records the product's camera for the whole run; `Hardware evidence` comments on the PR with each device's video and result, pass or fail. Video never decides a result.
- Merging a firmware change into `staging` or `main` allocates the next version and publishes a signed candidate through `publish_firmware.yml`.
- `pr-firmware.yml` calls the reviewed wrapper
  `.github/workflows/hardware-run.yml` pinned by commit SHA. The org runner
  group `rad-firmware-validation` allows only that exact ref, and
  `software/scripts/hil/reviewed-workflows.json` must match it.
- The shared rig harness is installed from the LKBX repository's
  `scripts/hil/`; keep DTT's `software/scripts/hil/` byte-identical to it.
- Changing `hardware-run.yml` needs a new pin in all three places.

## Documentation

- Docs sync runs `main` to `main` only, and `main` always wins. Commit
  documentation directly to `main`; never sync docs into or out of `staging`.
- The rad-app docs hub imports `assembly-docs/**` from `main`. Every change
  there, deletions included, reaches the live assembly site within minutes
  without review. Ask AJ before deleting or moving written docs.
- Keep `.github/workflows/trigger-assembly-docs.yml` on `main`; it notifies the
  hub.
- `assembly-docs/_bom/source.json` stays `{"repo":
  "Open-Source-Deepthroat-Trainer_DTT", "commit": "main"}`. Regenerate
  `bom.json` in the same commit as any `_bom/bom.csv` change, or the hub
  import fails.
- `docs/` mirrors `simple-docs/content/dtt`; edit user-guide content upstream.
  `sync-user-docs.yml` (via `scripts/sync_user_docs.py`) refreshes it and never
  writes `assembly-docs/`. Engineering pages belong in `developer-docs/docs/`.
- Write concise descriptions of the design as it is. Omit change narratives
  and confidence/status properties from CAD models and product documentation.

## PCB source and manufacturing

- Edit `hardware/pcb/kicad-rev4/217A_dttrainer_rev4/` as the rev4 KiCad source.
- Run its `export_production.py` to regenerate `hardware/pcb/production/`.
  The exporter also updates the assembly-docs KiCanvas board asset.
- Read `DESIGN.md` before pad, mask, or zone changes. Zones contain saved fills;
  mask openings are explicit graphics, including a board-level opening under U1.
- Keep the seven documented clearance findings visible; do not suppress them.
- OSHW lettering uses editable 1.2 mm text with 0.20 mm strokes.
- Keep device BOM assemblies separate from generated PCB component BOM rows.

## CAD

- Keep the OLED ribbon clear of the battery and its insulation outside the cell.
  Update STEP and preview images with native CAD changes.
- Preserve hardware source assets unless an intentional reviewed change is
  required. Keep LFS payloads available and verify their content hashes when
  updating their pointer files.
