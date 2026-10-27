# Enclosed case

The DTT case at one constant width, with a blue switch cover that slides S1
and a rear cover tray that holds the PCB from its top face down. The original
four PCB screws hold it together, with their heads flush in the rear cover.
It replaces the loop backing.

![Front](images/Enclosed-Front.png)
![Rear](images/Enclosed-Rear.png)
![Exploded](images/Enclosed-Exploded.png)
![Switch side](images/Enclosed-Switch-Side.png)
![Sections](images/Enclosed-Sections.png)
![Switch cover](images/Part-SwitchCover.png)
![Rear cover](images/Part-RearCover.png)

## Print

| Part | File | Colour | Orientation |
| --- | --- | --- | --- |
| Housing | `parts/Housing-Black.stl` (+ `Housing-Diffuser-White.stl` in white, `Housing-Logo-Blue.stl` in blue) | black | top face down |
| Rear cover | `parts/Rear-Cover-Black.stl` | black | outer face down |
| Switch cover | `parts/Switch-Cover-Blue.stl` | blue | flange face down |

## Hardware

| Qty | Part |
| --- | --- |
| 4 | The original PCB screws, 0408LTFB (#4 × 1/2" pan head, self-tapping) |

## Assemble

1. With the housing upside down, drop the switch cover into its slot from
   inside, grip outwards.
2. Fit the PCB so the S1 actuator enters the pocket in the switch cover.
3. Fit the rear cover and drive the four screws into the original bosses.
   Snug them; do not strip the bosses.

Size: 50.0 × 95.2 × 22.3 mm.

## Source

- `build_enclosed_case.py` builds the parts from `../DTT.FCStd`. Dimensions are
  in `PARAMS`.
- `make_assembly.FCMacro` writes `DTT-Enclosed.FCStd`, `DTT-Enclosed.step`,
  `parts/` and `images/`: `xvfb-run -a freecad make_assembly.FCMacro`.
- The PCB is unchanged; the screws use its existing 3.6 mm holes.

## Check on a test print

- S1 actuator position and travel. The cover follows the KiCad F.Fab drawing
  (actuator at Y 82.4, 1.5 mm wide) and allows 3.2 mm of travel. The old CAD
  switch model put the actuator 5 mm further along, so check the real part.
- The switch cover slides freely (0.15 mm clearance) and stays in the window.
- The screw heads sit flush in their 5.4 mm counterbores. They reach 9.6 mm
  into the bosses; a #4 × 5/8" also fits if that feels short.
- USB-C and 3.5 mm plugs seat fully through the 1.6 mm thicker end walls.

The CAD checks are geometric only. Clamp force, thread hold and drop
strength need a physical test.
