"""Build the enclosed DTT case from ../DTT.FCStd.

The housing is filled out to one rounded rectangle, a sliding switch cover
drives S1, and a rear cover tray holds the PCB from its top face down. The
original four PCB screws pass up through the tray and PCB into the housing
bosses, with their heads sunk flush in the tray.

Run with FreeCAD 1.1+ (GUI under xvfb keeps the colours in the saved file):
    xvfb-run -a freecad make_assembly.FCMacro
Coordinates follow DTT.FCStd: X = pcb_x - 127.583333, Y = 151.9861 - pcb_y,
PCB top at Z = -3.5, PCB bottom at Z = -5.1.
"""

import math
import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "DTT.FCStd")
OUT_FCSTD = os.path.join(HERE, "DTT-Enclosed.FCStd")
OUT_STEP = os.path.join(HERE, "DTT-Enclosed.step")
PARTS = os.path.join(HERE, "parts")

V = App.Vector

PARAMS = {
    # Stack (verified from DTT.FCStd and the KiCad board).
    "pcb_top_z": -3.5,  # also the seam between housing and rear cover
    "pcb_bottom_z": -5.1,
    "screw_axes": [(3.0, 76.0), (39.0, 76.0), (3.3, 27.5), (38.7, 27.5)],
    # Outer shape: one rounded rectangle, the same width all the way along.
    "outer": (-4.0, -0.6, 46.0, 94.6),
    "outer_r": 4.0,
    "top_z": 14.17,
    "top_fillet": 1.2,
    "bottom_chamfer": 0.8,
    # Sloped sensor end of the original housing: z = z0 + k * (y - y0).
    "slope": (9.774, 1.2, 1.368),
    "wall_overlap": 0.6,  # bond depth into the original wall
    "top_overlap": 2.0,  # in the top plate, past the original edge chamfer
    "top_band_z": 12.4,  # just under the top plate (underside at 12.6)
    "pcb_edge_gap": 0.3,  # PCB edge to rear cover wall
    # Rear cover (a tray that holds the PCB).
    "cover_thickness": 3.0,  # floor under the PCB
    "cover_pocket_inset": 0.9,  # pocket edge inside the PCB outline
    "cover_pocket_depth": 1.3,  # clears USB shell legs and jack pegs
    "cover_relief": 0.2,  # floor stays clear of the PCB except at the pads
    "cover_pad_d": 7.5,
    # Original short self-tapping PCB screws (0408LTFB, #4 x 1/2" Torx flat
    # head), sunk flush in 82 degree countersinks.
    "screw_clear_d": 3.2,
    "csk_d": 5.9,  # #4 flat head is 5.7 max
    "csk_angle": 82.0,
    "screw_len": 12.7,  # overall, head included
    "screw_d": 2.8,
    # S1 (JS102011JAQN). Actuator position from the KiCad F.Fab drawing.
    "sw_body": ((36.7, 79.1, -3.5), (43.3, 88.9, 0.6)),  # clearance box
    "act_y": 82.39,  # actuator centre, drawn position (pcb y 69.59)
    "act_w": 1.5,
    "act_tip_x": 45.06,
    "act_z": (-2.4, 0.2),
    "travel": 3.2,  # generous; S1's own detents set the end positions
    # Switch cover (slider). The window opens down to the seam.
    "pcb_edge_x": 42.92,
    "slider_clear": 0.15,
    "flange_t": 1.0,
    "grip_len": 5.0,
    "flange_margin": 1.0,
    "grip_proud": 0.4,
    "window_z": (-3.35, 0.7),  # grip, bottom 0.15 above the seam
    # Connector openings.
    "jack_axis": (20.9, -0.7),
    "jack_d": 6.2,
    "usb_center": (20.95, -2.155),
    "usb_size": (12.6, 6.8),
    "usb_r": 3.0,
    "usb_recess": (16.0, 10.0, 1.2),  # oval pocket around USB-C: width, height, depth
    # Tab on the rear cover that splits the jack hole across its middle.
    "jack_tab_w": 10.2,
    "jack_tab_y1": 0.6,  # inner face, short of the PCB pocket
    "tab_clear": 0.1,
    # Tongue on the rear cover rim, in a groove in the housing.
    "tongue": (0.9, 0.8, 1.0),  # inset from the outer face, width, height
    "tongue_y": (6.0, 89.0),
    "tongue_clear": 0.1,
    # Blue inlay on the flexure button (a touch point), inside its slot.
    "button_left": (17.806, 65.004, 3.0),  # centre x, y, radius
    "button_right": (33.414, 68.725, 3.5),
    "button_bar_y": (66.725, 70.725),
    "inlay_z": (13.52, 14.17),  # same depth as the logo inlay
}
P = PARAMS


def ext(wire, z0, z1):
    w = wire.copy()
    w.translate(V(0, 0, z0 - w.BoundBox.ZMin))
    return Part.Face(w).extrude(V(0, 0, z1 - z0))


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rounded_rect(x0, y0, x1, y1, r, z=0.0):
    r = min(r, (x1 - x0) / 2 - 1e-3, (y1 - y0) / 2 - 1e-3)
    k = r * (1 - math.sqrt(0.5))
    edges = [
        Part.LineSegment(V(x0 + r, y0, z), V(x1 - r, y0, z)),
        Part.Arc(V(x1 - r, y0, z), V(x1 - k, y0 + k, z), V(x1, y0 + r, z)),
        Part.LineSegment(V(x1, y0 + r, z), V(x1, y1 - r, z)),
        Part.Arc(V(x1, y1 - r, z), V(x1 - k, y1 - k, z), V(x1 - r, y1, z)),
        Part.LineSegment(V(x1 - r, y1, z), V(x0 + r, y1, z)),
        Part.Arc(V(x0 + r, y1, z), V(x0 + k, y1 - k, z), V(x0, y1 - r, z)),
        Part.LineSegment(V(x0, y1 - r, z), V(x0, y0 + r, z)),
        Part.Arc(V(x0, y0 + r, z), V(x0 + k, y0 + k, z), V(x0 + r, y0, z)),
    ]
    return Part.Face(Part.Wire([e.toShape() for e in edges]))


def zcyl(x, y, d, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(x, y, z0))


def stadium_y(cx, cz, w, h, r, y0, y1):
    """Rounded rectangle in the XZ plane, extruded along +Y."""
    f = rounded_rect(cx - w / 2, cz - h / 2, cx + w / 2, cz + h / 2, r)
    f.rotate(V(0, 0, 0), V(1, 0, 0), 90)  # XY -> XZ (y becomes z)
    f.translate(V(0, y1, 0))
    return f.extrude(V(0, y0 - y1, 0))


def outline(board):
    faces = [f for f in board.Faces if abs(f.normalAt(0, 0).z) > 0.9 and f.CenterOfMass.z < -5.0]
    w = faces[0].OuterWire.copy()
    w.translate(V(0, 0, -w.BoundBox.ZMin))
    return w


def envelope(z0, z1):
    x0, y0, x1, y1 = P["outer"]
    s = rounded_rect(x0, y0, x1, y1, P["outer_r"]).extrude(V(0, 0, z1 - z0))
    s.translate(V(0, 0, z0))
    return s


def above_slope(shift):
    """Everything above the sensor-end slope, moved shift outwards along -Y."""
    z0, y0, k = P["slope"]
    y0 -= shift
    pts = [(y0 + (-20 - z0) / k, -20), (y0 + (40 - z0) / k, 40), (-40, 40), (-40, -20)]
    w = Part.makePolygon([V(-20, y, z) for (y, z) in pts] + [V(-20, pts[0][0], pts[0][1])])
    return Part.Face(w).extrude(V(80, 0, 0))


def outer_upper():
    y0 = P["outer"][1]
    zs, zt = P["pcb_top_z"], P["top_z"]
    r = P["top_fillet"]
    e = envelope(zs, zt)
    e = e.makeFillet(r, [ed for ed in e.Edges if ed.BoundBox.ZMin > zt - 1e-6])
    e = e.cut(above_slope(1.0 - y0))  # original end wall at y = 1
    try:
        slope = [f for f in e.Faces if 0.5 < f.normalAt(0, 0).z < 0.99]
        e = e.makeFillet(r, slope[0].Edges)
    except Exception as ex:
        print("slope fillet skipped:", ex)
    return e


def connector_cuts():
    jx, jz = P["jack_axis"]
    ux, uz = P["usb_center"]
    return [Part.makeCylinder(P["jack_d"] / 2, 6.0, V(jx, -3.5, jz), V(0, 1, 0)),
            stadium_y(ux, uz, P["usb_size"][0], P["usb_size"][1], P["usb_r"], 91.0, 97.0),
            usb_recess()]


def usb_recess():
    ux, uz = P["usb_center"]
    w, h, d = P["usb_recess"]
    y1 = P["outer"][3]
    return stadium_y(ux, uz, w, h, h / 2 - 1e-3, y1 - d, y1 + 1)


def jack_tab(grow=0.0):
    jx, jz = P["jack_axis"]
    w = P["jack_tab_w"] / 2 + grow
    return box(jx - w, P["outer"][1] - 1, P["pcb_top_z"] - 0.01, jx + w, P["jack_tab_y1"] + grow, jz + grow)


def build_housing(H, board):
    pcb = outline(board)
    p0 = pcb.copy()
    p0.translate(V(0.08, 0.02, 0))  # original housing outline
    zs, zt = P["pcb_top_z"], P["top_z"] + 1

    # Fill between the original housing and the outer rectangle. Inside the
    # original wall keep the housing as it is, except above its sloped end,
    # where the fill thickens the slope so it meets the larger outline.
    keep = ext(p0.makeOffset2D(-P["wall_overlap"]), zs - 1, P["top_band_z"])
    # The slope cut sits 0.3 mm inside the original slope so the two bond
    # instead of meeting on one plane.
    keep = keep.fuse(ext(p0.makeOffset2D(-P["top_overlap"]), P["top_band_z"], zt)).cut(above_slope(-0.3))
    fill = outer_upper().cut(keep)
    h = H.fuse(fill).common(box(-20, -20, zs, 70, 120, zt)).removeSplitter()

    (a0, a1) = P["sw_body"]
    cuts = [box(a0[0], a0[1], a0[2] - 1, a1[0], a1[1], a1[2])] + slider_cuts() + connector_cuts()
    h = h.cut(cuts).removeSplitter()
    return h, pcb


def slider_geom():
    c = P["slider_clear"]
    xi = P["pcb_edge_x"] + P["pcb_edge_gap"] + 0.08  # flange inner face
    xf = xi + P["flange_t"]  # flange outer face
    xw = xf + c  # window wall inner face
    wz0, wz1 = P["window_z"]
    m = P["flange_margin"]
    return dict(xi=xi, xf=xf, xw=xw, wz0=wz0, wz1=wz1, fz0=wz0 - m, fz1=wz1 + m,
                gl=P["grip_len"], fl=P["grip_len"] + 2 * m, c=c)


def slider_cuts():
    """Channel for the flange (housing and rear cover) and the grip window."""
    g = slider_geom()
    ya, t, c = P["act_y"], P["travel"], g["c"]
    chan = box(g["xi"] - 0.2, ya - g["fl"] / 2 - c, g["fz0"] - c, g["xw"], ya + t + g["fl"] / 2 + c, g["fz1"] + c)
    win = box(g["xw"] - 0.1, ya - g["gl"] / 2 - c, P["pcb_top_z"] - 0.01, P["outer"][2] + 1,
              ya + t + g["gl"] / 2 + c, g["wz1"] + c)
    return [chan, win]


def build_slider():
    g = slider_geom()
    ya = P["act_y"]
    xo = P["outer"][2] + P["grip_proud"]
    flange = box(g["xi"], ya - g["fl"] / 2, g["fz0"], g["xf"], ya + g["fl"] / 2, g["fz1"])
    grip = box(g["xf"] - 0.01, ya - g["gl"] / 2, g["wz0"], xo, ya + g["gl"] / 2, g["wz1"])
    try:
        outer = [e for e in grip.Edges if abs(e.BoundBox.XMin - xo) < 1e-6 and abs(e.BoundBox.XMax - xo) < 1e-6]
        grip = grip.makeFillet(0.6, outer)
    except Exception as e:
        print("grip fillet skipped:", e)
    s = flange.fuse(grip)
    # Finger ridges across the grip face.
    for dy in (-1.5, 0.0, 1.5):
        s = s.cut(box(xo - 0.35, ya + dy - 0.3, g["wz0"] - 1, xo + 1, ya + dy + 0.3, g["wz1"] + 1))
    # Pocket for the actuator.
    z0, z1 = P["act_z"]
    w = P["act_w"] + 0.4
    s = s.cut(box(g["xi"] - 1, ya - w / 2, z0 - 0.25, P["act_tip_x"] + 0.4, ya + w / 2, z1 + 0.25))
    return s.removeSplitter()


def build_cover(pcb):
    """Rear cover: a tray from the seam at the PCB top down past the PCB back."""
    zs = P["pcb_top_z"]
    zt = P["pcb_bottom_z"]
    zb = zt - P["cover_thickness"]
    cover = envelope(zb, zs)
    try:
        bottom = [e for e in cover.Edges if e.BoundBox.ZMax < zb + 1e-6]
        cover = cover.makeChamfer(P["bottom_chamfer"], bottom)
    except Exception as e:
        print("cover chamfer skipped:", e)
    shell = cover.copy()
    # PCB pocket, relief under the PCB and the central pocket.
    cover = cover.cut(ext(pcb.makeOffset2D(P["pcb_edge_gap"]), zt - P["cover_relief"], zs + 1))
    cover = cover.cut(ext(pcb.makeOffset2D(-P["cover_pocket_inset"]), zt - P["cover_pocket_depth"], zs + 1))
    pads = [zcyl(x, y, P["cover_pad_d"], zt - P["cover_pocket_depth"] - 0.1, zt) for (x, y) in P["screw_axes"]]
    cover = cover.fuse(pads).common(shell)
    cover = cover.cut(slider_cuts()[:1] + connector_cuts())
    holes = []
    for (x, y) in P["screw_axes"]:
        holes.append(zcyl(x, y, P["screw_clear_d"], zb - 1, zt + 1))
        r = P["csk_d"] / 2
        h = (r - P["screw_clear_d"] / 2) / math.tan(math.radians(P["csk_angle"] / 2))
        holes.append(Part.makeCone(r + 0.5 * math.tan(math.radians(P["csk_angle"] / 2)), P["screw_clear_d"] / 2,
                                   h + 0.5, V(x, y, zb - 0.5)))
    cover = cover.cut(holes)
    return cover.removeSplitter()


def build_s1(model):
    """S1 with its actuator where the KiCad F.Fab drawing puts it."""
    body = model.common(box(30, 70, -10, P["pcb_edge_x"], 100, 10))
    w = P["act_w"]
    act = box(P["pcb_edge_x"] - 0.01, P["act_y"] - w / 2, -1.9, 44.97, P["act_y"] + w / 2, -0.3)
    return body.fuse(act).removeSplitter()


def build_screw(x, y):
    """Flat-head Torx self-tapping screw, head flush with the rear cover."""
    zb = P["pcb_bottom_z"] - P["cover_thickness"]
    dk = P["csk_d"] - 0.2
    k = (dk - P["screw_d"]) / 2 / math.tan(math.radians(P["csk_angle"] / 2))
    head = Part.makeCone(dk / 2, P["screw_d"] / 2, k, V(x, y, zb))
    shank = zcyl(x, y, P["screw_d"], zb + k - 0.01, zb + P["screw_len"] - 0.6)
    tip = Part.makeCone(P["screw_d"] / 2, 0.6, 0.6, V(x, y, zb + P["screw_len"] - 0.6))
    s = head.fuse([shank, tip])
    # T10 Torx recess (2.74 mm across the lobes), drawn as a core and six lobes.
    zr0, zr1 = zb - 0.1, zb + 1.0
    recess = zcyl(x, y, 1.9, zr0, zr1).fuse(
        [zcyl(x + 1.03 * math.cos(math.pi * i / 3), y + 1.03 * math.sin(math.pi * i / 3), 0.68, zr0, zr1)
         for i in range(6)])
    return s.cut(recess).removeSplitter()


def tongue(grow=0.0):
    """Tongues on the rear cover rim along the two long sides, in grooves in the
    housing. The end walls are too thin beside the PCB for one."""
    x0, y0, x1, y1 = P["outer"]
    a, w, h = P["tongue"]
    ya, yb = P["tongue_y"]
    zs = P["pcb_top_z"]
    t = [box(x0 + a - grow, ya - grow, zs - 0.01, x0 + a + w + grow, yb + grow, zs + h + grow),
         box(x1 - a - w - grow, ya - grow, zs - 0.01, x1 - a + grow, yb + grow, zs + h + grow)]
    gaps = [g.BoundBox for g in slider_cuts()]
    return Part.makeCompound(t).fuse([]).cut(
        [box(g.XMin, g.YMin - 0.6, zs - 1, g.XMax + 2, g.YMax + 0.6, zs + 3) for g in gaps])


def button_inlay(grow=0.2):
    """Button outline, grown into the slot so the cut never lands on its walls."""
    (lx, ly, lr), (rx, ry, rr) = P["button_left"], P["button_right"]
    b0, b1 = P["button_bar_y"]
    z0, z1 = P["inlay_z"]
    return zcyl(lx, ly, 2 * (lr + grow), z0, z1 + 1).fuse(
        [zcyl(rx, ry, 2 * (rr + grow), z0, z1 + 1), box(lx, b0 - grow, z0, rx, b1 + grow, z1 + 1)]).removeSplitter()


def build_all(doc):
    H = doc.getObject("Part__Feature001").Shape
    board = doc.getObject("BoardRev4").Shape

    housing, pcb = build_housing(H, board)
    slider = build_slider()
    cover = build_cover(pcb)
    # The part of the end wall below the jack axis moves to the rear cover.
    cover = cover.fuse(housing.common(jack_tab())).removeSplitter()
    housing = housing.cut(jack_tab(P["tab_clear"])).removeSplitter()
    cover = cover.fuse(tongue()).removeSplitter()
    button = housing.common(button_inlay()).removeSplitter()
    housing = housing.cut(button_inlay()).removeSplitter()
    housing = housing.cut(tongue(P["tongue_clear"])).removeSplitter()
    print("housing", housing.isValid(), len(housing.Solids), round(housing.Volume, 1))
    print("slider", slider.isValid(), len(slider.Solids), round(slider.Volume, 1))
    print("cover", cover.isValid(), len(cover.Solids), round(cover.Volume, 1))

    return dict(
        housing=housing,
        slider=slider,
        cover=cover,
        s1=build_s1(doc.getObject("Part__Feature002").Shape),
        button=button,
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
    )
