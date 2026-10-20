# DTT rev4 production files

Exported from the [KiCad project](../kicad-rev4/217A_dttrainer_rev4/217A_dttrainer_rev4.kicad_pro).

| File | Contents |
| --- | --- |
| [Trainer_gerber.zip](Trainer_gerber.zip) | Fabrication layers and drills. |
| [gerbers/](gerbers/) | Unpacked fabrication files. |
| [assembly-bom.csv](assembly-bom.csv) | 64 populated components, grouped by part. |
| [pick-and-place.csv](pick-and-place.csv) | Populated positions in mm, rotations in degrees. |
| [pcb-bom.csv](pcb-bom.csv) | All 69 positions, including DNPs. |
| [schematic.pdf](schematic.pdf) | Six-sheet schematic. |

Regenerate with `python ../kicad-rev4/217A_dttrainer_rev4/export_production.py`.
Gerbers, drills, and placement use the same auxiliary origin. Layout constraints
are in [DESIGN.md](../kicad-rev4/217A_dttrainer_rev4/DESIGN.md).
