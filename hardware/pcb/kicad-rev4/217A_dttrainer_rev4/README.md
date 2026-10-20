# DTT rev4 PCB

Open `217A_dttrainer_rev4.kicad_pro` in KiCad 7+. The project includes a six-sheet
schematic and local libraries. See [DESIGN.md](DESIGN.md) for layout notes.

[Production files](../../production/) include Gerbers, drills, BOMs, placement,
and schematic PDF. Regenerate them and the KiCanvas preview with:

```sh
python export_production.py
```

CI runs `python export_production.py --check` to catch stale exports.
