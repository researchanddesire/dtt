# DT Trainer

ESP32 firmware and hardware for the V1 (4 MiB) and V2 (16 MiB) DT Trainer.
Firmware: MPL-2.0. Hardware: CERN-OHL-S v2. User guides:
[CC BY-SA 4.0](https://github.com/researchanddesire/simple-docs/blob/main/LICENSE).

## Hardware

- [FreeCAD assembly](hardware/cad/)
- [KiCad PCB](hardware/pcb/kicad-rev4/217A_dttrainer_rev4/)
- [PCB production files](hardware/pcb/production/)
- [Assembly guide](assembly-docs/assembly-guide.mdx)

## Documentation

[User guides](docs/) mirror [Simple Docs](https://github.com/researchanddesire/simple-docs/tree/main/content/dtt).
The daily sync can also run with `python software/scripts/sync_user_docs.py`.
[Firmware and engineering docs](developer-docs/docs/) are maintained here.

## Build

Software lives in [`software/`](software/): the PlatformIO firmware project in
[`software/firmware/`](software/firmware/), development and CI tooling in
[`software/scripts/`](software/scripts/), and local development settings in
[`software/dev/`](software/dev/). Use Python 3.12 and PlatformIO Core 6.2.0:

```sh
python -m pip install platformio==6.2.0
cd software/firmware
pio run -e staging-v1 -e staging-v2 -e production-v1 -e production-v2
```

Select the environment matching the board. Builds do not flash a device.
Development builds (`development`, `development-v1`, `development-v2`) target a
local dashboard on port 3000 (or the origin in the ignored
`software/dev/local.settings.json`). Release builds read the dashboard API credential
from the `RAD_PUBLIC_KEY` environment variable; without it they use the
`DEV_KEY_123` placeholder. Never commit the credential. Flash explicitly:

```sh
pio run -e development-v1 -t upload
```

Keep deployed partition offsets and stored device identity intact.
See [AGENTS.md](AGENTS.md), [software/firmware/README.md](software/firmware/README.md), and
[CI](.github/workflows/) for checks.
