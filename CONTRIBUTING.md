# Contributing to the Deepthroat Trainer

## Daily development

Software lives in `software/`. Branch firmware and software work from **`staging`** and open the pull request back into `staging`. `staging` is promoted to `main` by a same-repository pull request. Only urgent production fixes target `main` directly, from a branch named `fix/<issue>` started from `main`.

Changes outside `software/` (documentation, hardware, BOMs) may open their pull request straight into `main`. Documentation in `assembly-docs/`, `docs/` and `developer-docs/` syncs from `main`, so documentation-only changes target `main`. The `PR target policy` check enforces these rules. Feature and fix pull requests are squash-merged into one focused commit.

## Documentation

- User guides in `docs/` mirror [`simple-docs`](https://github.com/researchanddesire/simple-docs/tree/main/content/dtt) and are published at [docs.researchanddesire.com/dtt](https://docs.researchanddesire.com/dtt/). Edit them in `simple-docs`; a daily sync copies them here.
- The assembly guide and BOM in `assembly-docs/` are published at [ohai.researchanddesire.com/dtt](https://ohai.researchanddesire.com/dtt) within minutes of reaching `main`.
- Engineering pages live in `developer-docs/docs/`. Edit them in the same pull request as firmware changes when behavior changes.
- Cross-product developer docs and the developer site [dev.researchanddesire.com/dtt](https://dev.researchanddesire.com/dtt/) are maintained in [`dev-docs`](https://github.com/researchanddesire/dev-docs).

## Build setup

The PlatformIO project is `software/firmware/`, tooling is in `software/scripts/`, and local development settings are in `software/dev/`. Use Python 3.12 and PlatformIO Core 6.2.0:

```bash
python -m pip install platformio==6.2.0
cp software/dev/local.settings.example.json software/dev/local.settings.json   # optional: set "server"
cd software/firmware
pio run -e development-v1                                                      # V1 (4 MB); development-v2 for V2 (16 MB)
pio run -e development-v1 -t upload                                            # flashing is always explicit
```

Development builds talk to the dashboard origin in the ignored `software/dev/local.settings.json`, or `http://127.0.0.1:3000` without it. Outside CI a loopback origin is replaced with this machine's private LAN address so the device can reach it. Release environments (`staging-v1`, `staging-v2`, `production-v1`, `production-v2`) read the dashboard API credential from the `RAD_PUBLIC_KEY` environment variable and fall back to the `DEV_KEY_123` placeholder. Never commit the credential.

## Pull requests

- Run `pio test -e test_native` and `pio check --skip-packages --fail-on-defect high -e development -f src` in `software/firmware/` when touching firmware. [`pull_request_action.yml`](.github/workflows/pull_request_action.yml) lists the full set of checks.
- Firmware pull requests also build every hardware variant and run on R+D's shared hardware test rig; `Build validation` and `Hardware validation` must pass.
- Update `developer-docs/` if you change APIs, device states, or integration behavior.
- Follow existing code style (`software/.clang-format`).
- Never commit credentials, `local.settings.json`, test result dumps, or compiled images. CI scans source and history with gitleaks.
- Keep the physical flash size, partition offsets, and stored device identity of deployed hardware intact.
- Don't edit the firmware version. It is allocated when firmware merges into `main`, and official firmware is signed and published by R+D's release workflow, never from a pull request or fork.

## Hardware

- PCB: edit the KiCad source in `hardware/pcb/kicad-rev4/217A_dttrainer_rev4/` and run its `export_production.py` to regenerate `hardware/pcb/production/` and the assembly guide's board viewer. Read its `DESIGN.md` before pad, mask, or zone changes. CI runs `export_production.py --check`.
- CAD: `hardware/cad/DTT.FCStd` is the editable FreeCAD 1.1+ assembly. Update `DTT.step` and the preview images with native CAD changes.

## Hardware BOMs

`hardware/bom.csv` follows the [BOM standard](https://dev.researchanddesire.com/meta/bom-standard/) — fixed columns, closed category codes, `–` for empty cells. The PCB is one assembly row; its components belong in the generated [`hardware/pcb/production/pcb-bom.csv`](hardware/pcb/production/pcb-bom.csv). The assembly guide reads `assembly-docs/_bom/bom.csv`: regenerate `assembly-docs/_bom/bom.json` in the same commit as any change to it, or the assembly site import fails. If you can't, say so in the pull request.

## Security

Report suspected vulnerabilities privately to support@researchanddesire.com, not in public issues. See [SECURITY.md](SECURITY.md).

## Licenses

See [LICENSE](LICENSE). Firmware and software are **MPL 2.0**; hardware designs in `hardware/cad` and `hardware/pcb` are **CERN-OHL-S v2**; user guides are [CC BY-SA 4.0](https://github.com/researchanddesire/simple-docs/blob/main/LICENSE).
