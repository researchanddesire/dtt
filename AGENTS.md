# Public DTT repository

Firmware/software uses MPL-2.0 and hardware uses CERN-OHL-S v2; retain LICENSE,
LICENSES, and third-party notices.

## Layout

- `software/` is the PlatformIO firmware project. Run `pio` there and follow
  `software/AGENTS.md` for firmware, release, and hardware-validation rules.
- `hardware/` holds the CAD assembly, PCB source, and manufacturing outputs.
- `docs/` (user guides), `developer-docs/` (engineering), and `assembly-docs/`
  (build guide) document the device.
- `.github/` holds CI for the whole repository, with its scripts in
  `.github/scripts/`.

## Public repository safety

- Release builds read the dashboard API credential from the `RAD_PUBLIC_KEY`
  environment variable. Never commit it, local settings, test result dumps,
  or compiled images.
- CI scans source and history with gitleaks; keep the credential rule in
  `.gitleaks.toml`.
- Do not change physical flash sizes or partition offsets for deployed hardware.

Preserve assembly-docs, developer-docs, hardware, and their source assets unless
an intentional reviewed change is required. Keep LFS payloads available and
verify their content hashes when updating their pointer files.

## PCB source and manufacturing

- Edit `hardware/pcb/kicad-rev4/217A_dttrainer_rev4/` as the rev4 KiCad source.
- Run its `export_production.py` to regenerate `hardware/pcb/production/`.
  The exporter also updates the assembly-docs KiCanvas board asset.
- Read `DESIGN.md` before pad, mask, or zone changes. Zones contain saved fills;
  mask openings are explicit graphics, including a board-level opening under U1.
- Keep the seven documented clearance findings visible; do not suppress them.
- OSHW lettering uses editable 1.2 mm text with 0.20 mm strokes.
- Keep device BOM assemblies separate from generated PCB component BOM rows.

## Documentation and CAD

- `docs/` mirrors `simple-docs/content/dtt`; edit user-guide content upstream.
- Use `scripts/sync_user_docs.py` to refresh it. Engineering pages belong in
  `developer-docs/docs/`.
- Write concise descriptions of the design as it is. Omit change narratives
  and confidence/status properties from CAD models and product documentation.
- Keep the OLED ribbon clear of the battery and its insulation outside the cell.
  Update STEP and preview images with native CAD changes.
