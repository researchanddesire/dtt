Certainly! Here's an expanded README.md for the Deep Throat Trainer (DTT) project:

---

```
██████╗ ████████╗████████╗
██╔══██╗╚══██╔══╝╚══██╔══╝
██║  ██║   ██║      ██║   
██║  ██║   ██║      ██║   
██████╔╝   ██║      ██║   
╚═════╝    ╚═╝      ╚═╝   
```

# Welcome to the Deep Throat Trainer (DTT) Project

## Overview

The Deep Throat Trainer (DTT) is an innovative adult toy designed improve deep throat abilities. Powered by an ESP32
chip and running code within the Arduino framework via PlatformIO, the DTT is a unique blend of technology and pleasure,
aiming to redefine adult entertainment.

## Features

- **Advanced ESP32 Chip:** Ensures fast, reliable performance.
- **PlatformIO Integration:** Facilitates easy development and deployment.
- **Customizable Settings:** Allows users to tailor experiences to their preferences on Bubble.io
- **WiFi Connectivity:** Enables updates and remote control functionalities.

## Getting Started

To get started with the DTT project, you'll need to set up your development environment. This includes installing
PlatformIO, cloning the repository, and understanding the basic architecture of the ESP32 chip.

### Prerequisites

- PlatformIO IDE or PlatformIO Core
- ESP32 development board
- Basic understanding of Arduino framework

`RAD_PUBLIC_KEY` is the legacy bearer credential used by DTT HTTP API calls.
Despite its historical name, it is not an ECDSA public key and is not used to
sign or verify firmware provenance. Official release provenance is verified
separately with the committed R+D P-256 public-key registry; private signing
keys are available only to the release CI environments.

### Installation

1. Clone the repository:
   ```bash
   git clone [repository URL]
   ```
2. Navigate to the project directory:
   ```bash
   cd DTT
   ```
3. Install dependencies using PlatformIO:
   ```bash
   pio lib install
   ```
4. Connect your ESP32 board to your computer.
5. Upload the code to the board using PlatformIO.
   ```bash
   pio run -e development -t upload -t monitor 
   ```
   The build uses `RAD_SERVER` exactly as configured. On the device,
   `localhost` is the trainer itself, so point `RAD_SERVER` at your computer's
   LAN address or the staging server before you flash.
6. To test the release pipeline, you can use the staging environment with an old version number
   ```bash
   export SW_VERSION=0 && pio run -e staging -t upload -t monitor 
   ```

### Testing

**Unit tests** (TrainingTypes library, no device needed):
```bash
pio test -e development --filter "test_training_types"
```

**Integration tests** (full device lifecycle, requires device + server):
```bash
pio test -e development --filter "test_integration" -v
```

Integration tests boot the full firmware on the ESP32 and run 41 tests across the complete device lifecycle: hardware init → notifications → pairing → preflight → settings fetch → calibration → training → grading → result upload → error recovery.

**Integration test prerequisites:**
1. Device connected via USB
2. `WIFI_SSID`/`WIFI_PASSWORD` set in `platformio.ini` `[env:development]`
3. `BYPASS_EEPROM` enabled in `platformio.ini` `[env:development]`
4. `RAD_SERVER` pointing to the staging server or your computer's LAN address (never `localhost`)
5. Staging server seeded (`rad-app/supabase/seed/042_dtt_integration_test.sql`)

Tests are human-in-the-loop — follow the `>>> ACTION REQUIRED` prompts in Serial output to press buttons and move the device when asked.

**Crash detection:**
If a test crashes, the device reboots. On the next boot, the test runner:
1. Detects the crash (`ESP_RST_PANIC`)
2. Prints `CRASH DETECTED FROM PREVIOUS RUN`
3. Reports a test failure
4. Halts (no infinite reboot loop)

To find what crashed, scroll up to see the last log line before `Guru Meditation Error`.

**Decoding backtraces:**
The crash output includes hex addresses. To decode them to file:line:
```bash
~/.platformio/packages/toolchain-xtensa-esp32/bin/xtensa-esp32-elf-addr2line \
  -e .pio/build/development/firmware.elf -f -C \
  <address1> <address2> ...
```
Replace `<address1> <address2> ...` with the addresses from your backtrace (e.g., `0x400d78b4 0x400d8d36`).

### Pre-commit hooks

We use pre-commit hooks to ensure that all code is formatted correctly and passes all tests before being committed. To
install the pre-commit hooks, run the following command:

```bash
pre-commit install
```

Note: If you don't have pre-commit installed, you can install it using pip:

```bash
pip install pre-commit
```

## Contributing

Fetch `origin`, branch feature work from `origin/staging`, and open the pull request back into `staging`. Reserve direct production hotfixes for branches created from `origin/main`; open those PRs into `main` and begin the PR title with the standalone word `hotfix` (case-insensitive).

Feature and hotfix PRs are squash-merged into one focused commit. Promotions from `staging` to `main` and hotfix synchronization from `main` to `staging` use merge commits so the long-lived branches retain shared ancestry.

## Usage

Once you have the DTT set up, you can start exploring its features. You can modify the code to customize the
functionality, update device settings, and experiment with different modes available in the software.

## Disclaimer

This project is intended for adult users only. By using or contributing to this project, you agree that you are of legal
age in your region.

---

This expanded README.md provides a comprehensive introduction to the project, covering essential aspects like overview,
features, getting started instructions, usage, contributing, support, license, and a disclaimer.
