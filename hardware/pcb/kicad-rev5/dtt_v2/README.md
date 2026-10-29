# DTT v2 PCB (rev 5)

ESP32-S3 board for the DTT v2: 2.0 in touch screen, VL53L4CD time-of-flight
sensor, LSM6DSO + LIS3MDL 9DOF IMU, side PH6 accessory port. No LEDs, button
or headphone jack. 38 x 64 mm (rev 4 is 44 x 92 mm). LCSC numbers on every
part except the screen connector.

Status: routed, KiCad 9 DRC clean. Not yet reviewed or fabbed.

| Back | Front |
| --- | --- |
| ![Back](images/back.png) | ![Front](images/front.png) |

## Source

`build_dtt_v2.py` generates the schematic, libraries, project and placed board
from one netlist; `route_dtt_v2.py` routes it (about an hour). Both overwrite
the board, so once it is hand-edited in KiCad, stop running them.

## PH6 accessory port

| Pin | Signal |
| --- | --- |
| 1 | GND |
| 2 | VSYS (0.5 A PTC) |
| 3 | OUT1, 3.3 V high-side |
| 4 | OUT2, 3.3 V high-side |
| 5 | I2C SDA |
| 6 | I2C SCL |

Existing 3.5 mm accessories use an adapter: tip GND, ring 1 OUT1, ring 2 OUT2.

## I2C addresses

Touch 0x15, ToF 0x29, IMU 0x6A, magnetometer 0x1C.

## Screen

Bare 2.0 in 240x320 IPS panel with CST816D touch, the one inside Waveshare's
"2inch Capacitive Touch LCD" module. 21-pin 0.5 mm FPC, pin order from that
module's schematic:

| Pin | Signal | | Pin | Signal |
| --- | --- | --- | --- | --- |
| 1 | GND | | 12 | RS (DC) |
| 2 | LEDK | | 13 | CS |
| 3 | LEDA | | 14 | GND |
| 4 | GND | | 15 | TP_VDD (3.3 V) |
| 5, 6 | VCC (3.3 V) | | 16 | TP_RESET |
| 7 | GND | | 17 | TP_INT |
| 8 | RESET | | 18 | TP_SDA |
| 9 | SCL (SPI clock) | | 19 | TP_SCL |
| 10 | TE | | 20, 21 | GND |
| 11 | SDA (MOSI) | | | |

## Open items

- Check on a panel sample: LEDA/LEDK order, FPC contact side (J3 is
  top-contact for now), glass outline (36 x 52 mm assumed).
- Backlight is 3.3 V through 10 R, so not full brightness.
- SW1 reuses the rev 4 footprint with its tight locating holes.
