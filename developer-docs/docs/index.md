---
title: DT Trainer Developer Documentation
---

# Deep Throat Trainer — Developer Documentation

PlatformIO firmware for the ESP32-based Deep Throat Trainer. The PlatformIO
project is `software/firmware/`; development and release tooling is in
`software/scripts/`, and local development settings are in `software/dev/`.

## Build

```bash
cd software/firmware
pio run -e development
```

Release builds read the dashboard API credential from `RAD_PUBLIC_KEY`.

## Topics

- [Architecture](architecture.md) — state machine and services overview
- [Testing](testing.md) — native integration tests

User guides: [docs.researchanddesire.com/dtt](https://docs.researchanddesire.com/dtt/).
