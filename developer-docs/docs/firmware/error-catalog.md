# Error Catalog (Internal)

This reference documents internal, engineering, and validation error codes emitted by the firmware. For user-facing error explanations and recovery steps, see the [user Error Codes guide](https://docs.researchanddesire.com/dtt/technical/error-codes/).

## Internal status codes

### "69 0" (and similar numeric codes)

Internal status codes surfaced when the device attempts to upload calibration or session data but can't reach the server. Codes like **"69 0"** are internal status codes — when offline, they don't prevent training; they simply indicate that data couldn't be uploaded at that moment.

## Segment validation errors

### "Invalid Range"

**Cause:** The segment parameters resolve to an invalid training range.

**Notes:**
- Typically indicates a configuration issue in the template.
- Verify start and end positions are valid and within the sensor's clamped range.

### "Small window"

**Cause:** The target window is too small for reliable tracking.

**Notes:**
- The minimum effective window depends on sensor resolution.
- Increase the target window size in the template.

## System errors

### "Segment is nullptr" / "ERROR"

**Cause:** Internal error — the firmware couldn't load segment data (null segment pointer).

**Recovery:**
1. Press the button to reset.
2. Power cycle the device.
3. Verify the template has valid segments.
4. Re-download settings from the dashboard.

!!! warning
    If this error persists, capture the Trainer ID and reproduction steps for support.

## Provisioning errors

These only appear during initial device setup (factory/repair):

### "Failed to get trainer ID"

**Cause:** Provisioning server communication failed.

**Notes:**
- Requires a working internet connection to the provisioning server.
- Re-provisioning is also required after a flash with "Erase device" enabled — see [Firmware Flashing](/dtt/firmware/flashing/).

## Related references

- [Firmware Flashing](/dtt/firmware/flashing/) — erase/re-provisioning behavior.
- [Device States](/dtt/firmware/device-states/) — error state screens.
