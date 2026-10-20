# DTT rev4 layout notes

- 69 component positions; 64 populated. C1, J3, J4, R10, and U4 are DNP.
- R25: 1 kOhm between ground and 3.3 V.
- S1: pin 1 OFF, pin 2 VBAT, pin 3 switched supply (`Net_5`).
- OSHW lettering: 1.2 mm text, 0.20 mm strokes.
- Export origin: KiCad auxiliary origin `(126.5871, 151.0311)` mm;
  exported X right and Y up.

Zones contain saved fills. Refilling changes copper geometry.
Mask apertures are footprint graphics; update them when resizing pads.
The extra back-mask opening under U1 is a board graphic and must move with U1.
Keep the ESP32 antenna keepout and check geometry after footprint substitutions.

## Clearance findings

| Location | Clearance | Rule |
| --- | --- | --- |
| IO17 via to IO32 back trace | 0.1512 mm | 0.1524 mm |
| Six S1 locating-hole/copper pairs | 0.1147–0.1333 mm | 0.2500 mm |
