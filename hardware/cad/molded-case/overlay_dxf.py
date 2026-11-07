"""Overlay drawing for the converter: python3 overlay_dxf.py (after the build).

Reads parts/Overlay-Layers.json and writes parts/Overlay.dxf, mm, top view,
one layer per die cut and print colour. Black prints everywhere else.
"""
import json
import os

import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
COL = {"CUT_OUTLINE": 1, "CUT_HOLES": 1, "PRINT_CLEAR": 4, "PRINT_WHITE": 8, "PRINT_BLUE": 5, "RECESS": 9, "DIFFUSER_LAYER": 3, "NO_ADHESIVE": 6}

data = json.load(open(os.path.join(HERE, "parts", "Overlay-Layers.json")))
doc = ezdxf.new(units=ezdxf.units.MM)
for name, loops in data.items():
    doc.layers.add(name, color=COL.get(name, 7))
    for pts in loops:
        doc.modelspace().add_lwpolyline(pts, close=True, dxfattribs={"layer": name})
doc.saveas(os.path.join(HERE, "parts", "Overlay.dxf"))
print("wrote parts/Overlay.dxf")
