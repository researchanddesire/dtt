# Testing

DTT has two test suites, both run through PlatformIO.

## Unit tests

`test/test_training_types/` covers the `TrainingTypes` library — pure logic, no hardware or network. It exercises the repetition, endurance, bounce, and freeform segment classes.

```bash
pio test -e development --filter "test_training_types"
```

## Integration tests

`test/test_integration/` boots the full firmware on a real device and walks the complete lifecycle (hardware init, pairing, settings fetch, calibration, a full training session, and WiFi disconnect/reconnect). These tests are human-in-the-loop: the tester is prompted over Serial to press the button or move the device.

```bash
pio test -e development --filter "test_integration" -v
```

Prerequisites: a device connected over USB, `WIFI_SSID`/`WIFI_PASSWORD` set in `[env:development]`, `BYPASS_EEPROM` enabled, and `RAD_SERVER` pointing at a reachable staging server.

See [`test/README.md`](https://github.com/researchanddesire/DT_Trainer-OSS/blob/main/test/README.md) in the repository root.
