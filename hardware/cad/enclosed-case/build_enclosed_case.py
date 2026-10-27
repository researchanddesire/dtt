"""Build the enclosed DTT case from ../DTT.FCStd.

The housing grows a wall around the PCB edge, a sliding switch cover drives S1,
and a rear cover closes the back of the PCB. Four countersunk M3 screws pass
through the rear cover and PCB into heat-set inserts in the housing bosses.

Run with FreeCAD 1.1+ (GUI under xvfb keeps the colours in the saved file):
    xvfb-run freecad build_enclosed_case.py
    freecadcmd build_enclosed_case.py      # geometry only
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
    "pcb_top_z": -3.5,
    "pcb_bottom_z": -5.1,
    "housing_bottom_z": -3.632,
    "screw_axes": [(3.0, 76.0), (39.0, 76.0), (3.3, 27.5), (38.7, 27.5)],
    # Walls around the PCB edge.
    "wall": 1.6,  # added outside the original housing outline
    "wall_overlap": 0.6,  # bond depth into the original 1.5 mm wall
    "pcb_edge_gap": 0.3,  # PCB edge to skirt
    # Rear cover.
    "cover_thickness": 3.0,
    "cover_pocket_inset": 0.9,  # pocket edge inside the PCB outline
    "cover_pocket_depth": 1.3,  # clears USB shell legs and jack pegs
    "cover_relief": 0.2,  # cover stays clear of the PCB except at the pads
    "cover_pad_d": 7.5,
    "screw_clear_d": 3.4,
    "csk_d": 6.4,  # ISO 10642 / DIN 7991 M3 head, 90 degrees
    # Heat-set inserts (M3 x 4, 4.0 mm hole).
    "insert_hole_d": 4.0,
    "insert_hole_depth": 5.0,
    "boss_d": 6.4,
    "boss_top_z": 2.5,
    # S1 (JS102011JAQN). Actuator position from the KiCad F.Fab drawing.
    "sw_body": ((36.7, 79.1, -3.5), (43.3, 88.9, 0.6)),  # clearance box
    "act_y": 82.39,  # actuator centre, drawn position (pcb y 69.59)
    "act_w": 1.5,
    "act_tip_x": 45.06,
    "act_z": (-2.4, 0.2),
    "travel": 3.2,  # generous; S1's own detents set the end positions
    # Switch cover (slider) and its pod on the housing wall.
    "pcb_edge_x": 42.92,
    "slider_clear": 0.15,
    "flange_t": 1.0,
    "grip_len": 5.0,
    "flange_margin": 1.0,
    "grip_proud": 0.4,
    "window_z": (-2.9, 0.7),
    "pod_outer_x": 46.2,
    "pod_y": (76.9, 91.0),
    "pod_top_z": 2.6,
    "pod_r": 2.0,
    # Connector openings.
    "jack_axis": (20.9, -0.7),
    "jack_d": 6.2,
    "usb_center": (20.95, -2.155),
    "usb_size": (12.6, 6.8),
    "usb_r": 3.0,
    # Fasteners shown in the assembly.
    "screw_len": 8.0,
    "insert_od": 4.0,  # drawn at hole size; the knurl melts into the boss
    "insert_len": 4.0,
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


def build_housing(H, board):
    pcb = outline(board)
    p0 = pcb.copy()
    p0.translate(V(0.08, 0.02, 0))  # original housing outline
    W = P["wall"]
    zt = H.BoundBox.ZMax + 1
    zb = P["pcb_bottom_z"]
    zh = P["housing_bottom_z"]

    # Upper wall: copies of the housing scaled in plan so the outer wall
    # moves out by W (and W / 2 to bridge the joint). The top edge, chamfers
    # and corner shapes come from the housing itself.
    bb = p0.BoundBox
    cx, cy = bb.Center.x, bb.Center.y
    inner = p0.makeOffset2D(-P["wall_overlap"])
    band = ext(p0.makeOffset2D(W + 2), P["pcb_top_z"], zt).cut(ext(inner, P["pcb_top_z"] - 1, zt))

    def plan_scale(w):
        m = App.Matrix()
        m.move(V(-cx, -cy, 0))
        m.scale(1 + w / (bb.XLength / 2), 1 + w / (bb.YLength / 2), 1)
        m.move(V(cx, cy, 0))
        return m

    upper = [H.transformGeometry(plan_scale(w)).common(band) for w in (W, W / 2)]
    p1 = p0.transformGeometry(plan_scale(W))
    # Skirt and cover sit 0.05 inside the wall above: coincident faces leave
    # cracks in the STL.
    p1s = p0.transformGeometry(plan_scale(W - 0.05))

    # Skirt around the PCB edge, down to the rear cover.
    skirt = ext(p1s, zb, P["pcb_top_z"] + 0.2).cut(ext(pcb.makeOffset2D(P["pcb_edge_gap"]), zb - 1, P["pcb_top_z"] + 0.3))

    # Pod that carries the switch cover.
    x0 = P["pcb_edge_x"] - 2.5
    pz = P["pod_top_z"]
    y0, y1 = P["pod_y"]
    pod = rounded_rect(x0, y0, P["pod_outer_x"], y1, P["pod_r"]).extrude(V(0, 0, pz - zb))
    pod.translate(V(0, 0, zb))
    try:
        top = [e for e in pod.Edges if abs(e.BoundBox.ZMin - pz) < 1e-6 and abs(e.BoundBox.ZMax - pz) < 1e-6]
        pod = pod.makeChamfer(1.2, top)
    except Exception as e:
        print("pod chamfer skipped:", e)
    pod = pod.cut(ext(inner, zb - 1, zt))

    # Larger bosses for heat-set inserts.
    bosses = []
    for (x, y) in P["screw_axes"]:
        b = zcyl(x, y, P["boss_d"], P["pcb_top_z"], P["boss_top_z"])
        cone = Part.makeCone(P["boss_d"] / 2, 2.5, 1.5, V(x, y, P["boss_top_z"]))
        bosses.append(b.fuse(cone))

    h = H.fuse(upper + [skirt, pod] + bosses).removeSplitter()

    # Cuts.
    cuts = []
    cuts.append(ext(pcb.makeOffset2D(P["pcb_edge_gap"]), zb - 2, P["pcb_top_z"]))  # PCB pocket
    (a0, a1) = P["sw_body"]
    cuts.append(box(a0[0], a0[1], a0[2], a1[0], a1[1], a1[2]))
    cuts += slider_cuts()
    jx, jz = P["jack_axis"]
    cuts.append(Part.makeCylinder(P["jack_d"] / 2, 5.0, V(jx, -3.5, jz), V(0, 1, 0)))
    ux, uz = P["usb_center"]
    cuts.append(stadium_y(ux, uz, P["usb_size"][0], P["usb_size"][1], P["usb_r"], 91.0, 97.0))
    for (x, y) in P["screw_axes"]:
        cuts.append(zcyl(x, y, P["insert_hole_d"], P["pcb_top_z"] - 0.5, P["pcb_top_z"] + P["insert_hole_depth"]))
    h = h.cut(cuts).removeSplitter()
    return h, p1s, pcb


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
    g = slider_geom()
    ya, t, c = P["act_y"], P["travel"], g["c"]
    zb = P["pcb_bottom_z"]
    chan = box(g["xi"] - 0.2, ya - g["fl"] / 2 - c, zb - 0.5, g["xw"], ya + t + g["fl"] / 2 + c, g["fz1"] + c)
    win = box(g["xw"] - 0.1, ya - g["gl"] / 2 - c, g["wz0"] - c, P["pod_outer_x"] + 1, ya + t + g["gl"] / 2 + c, g["wz1"] + c)
    return [chan, win]


def build_slider():
    g = slider_geom()
    ya = P["act_y"]
    xo = P["pod_outer_x"] + P["grip_proud"]
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


def build_cover(p1, pcb):
    zt = P["pcb_bottom_z"]
    zb = zt - P["cover_thickness"]
    cover = ext(p1, zb, zt)
    # Pod footprint closes the bottom of the slider channel.
    y0, y1 = P["pod_y"]
    pod = rounded_rect(P["pcb_edge_x"] - 2.5, y0, P["pod_outer_x"], y1, P["pod_r"]).extrude(V(0, 0, zt - zb))
    pod.translate(V(0, 0, zb))
    cover = cover.fuse(pod)
    # Relief under the PCB and the central pocket.
    cover = cover.cut(ext(pcb.makeOffset2D(P["pcb_edge_gap"]), zt - P["cover_relief"], zt + 1))
    cover = cover.cut(ext(pcb.makeOffset2D(-P["cover_pocket_inset"]), zt - P["cover_pocket_depth"], zt + 1))
    pads = [zcyl(x, y, P["cover_pad_d"], zt - P["cover_pocket_depth"] - 0.1, zt) for (x, y) in P["screw_axes"]]
    cover = cover.fuse(pads).common(ext(p1, zb, zt).fuse(pod))
    ux, uz = P["usb_center"]
    cover = cover.cut(stadium_y(ux, uz, P["usb_size"][0], P["usb_size"][1], P["usb_r"], 91.0, 97.0))
    holes = []
    for (x, y) in P["screw_axes"]:
        holes.append(zcyl(x, y, P["screw_clear_d"], zb - 1, zt + 1))
        d = P["csk_d"]
        holes.append(Part.makeCone(d / 2 + 0.5, P["screw_clear_d"] / 2, d / 2 + 0.5 - P["screw_clear_d"] / 2, V(x, y, zb - 0.5)))
    cover = cover.cut(holes)
    return cover.removeSplitter()


def build_s1(model):
    """S1 with its actuator where the KiCad F.Fab drawing puts it."""
    body = model.common(box(30, 70, -10, P["pcb_edge_x"], 100, 10))
    w = P["act_w"]
    act = box(P["pcb_edge_x"] - 0.01, P["act_y"] - w / 2, -1.9, 44.97, P["act_y"] + w / 2, -0.3)
    return body.fuse(act).removeSplitter()


def build_screw(x, y):
    zb = P["pcb_bottom_z"] - P["cover_thickness"]
    dk, k = 6.0, 1.5
    head = Part.makeCone(dk / 2, 1.5, k, V(x, y, zb + 0.2))
    shank = zcyl(x, y, 3.0, zb + 0.2 + k - 0.01, zb + 0.2 + P["screw_len"])
    s = head.fuse(shank)
    hexagon = Part.makePolygon([V(x + 1.155 * math.cos(math.pi * i / 3), y + 1.155 * math.sin(math.pi * i / 3), zb)
                                for i in range(7)])
    return s.cut(Part.Face(hexagon).extrude(V(0, 0, 1.4)))  # 2 mm hex socket


def build_insert(x, y):
    z0 = P["pcb_top_z"]
    o = zcyl(x, y, P["insert_od"], z0, z0 + P["insert_len"])
    return o.cut(zcyl(x, y, 3.0, z0 - 1, z0 + P["insert_len"] + 1))


def build_all(doc):
    H = doc.getObject("Part__Feature001").Shape
    board = doc.getObject("BoardRev4").Shape

    housing, p1, pcb = build_housing(H, board)
    slider = build_slider()
    cover = build_cover(p1, pcb)
    print("housing", housing.isValid(), len(housing.Solids), round(housing.Volume, 1))
    print("slider", slider.isValid(), len(slider.Solids), round(slider.Volume, 1))
    print("cover", cover.isValid(), len(cover.Solids), round(cover.Volume, 1))

    return dict(
        housing=housing,
        slider=slider,
        cover=cover,
        s1=build_s1(doc.getObject("Part__Feature002").Shape),
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
        inserts=[build_insert(x, y) for (x, y) in P["screw_axes"]],
    )
