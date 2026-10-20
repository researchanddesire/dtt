# Hardware Overview

This page summarizes the Deepthroat Trainer hardware platform for developers working on firmware, accessories, and integrations.

## Components

The Deepthroat Trainer features:

- **USB-C charging port** for charging and (on supported units) data/flashing
- **3.5mm accessory port** (4-conductor TRRS) for connecting vibrating accessories
- **Power switch** for on/off control
- **128x64 OLED display** for real-time feedback
- **RGB LED strip** (3 LEDs) for position feedback
- **Front button** for interaction and control
- **Ultrasonic distance sensor** for position tracking

## Distance sensor specifications

| Specification | Value |
|---------------|-------|
| Maximum range | 22.5 cm (~9 inches) |
| Dead zone | 1.7 cm (~0.67 inches) |
| Effective range | 20.8 cm (~8.2 inches) |
| Minimum stroke | 0.8 cm (~0.3 inches) |

!!! info
    For full sensor behavior (sampling, buffering, clamping, calibration), see the [Distance Sensor](/dtt/hardware/distance-sensor/) reference.

## Related hardware references

- [Accessory Port](/dtt/hardware/accessory-port/) — TRRS pinout, PWM electrical spec, driver circuits, and sample code.
- [Distance Sensor](/dtt/hardware/distance-sensor/) — ultrasonic range, averaging, and clamping details.
