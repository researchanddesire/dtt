"""Build the enclosed DTT case from ../DTT.FCStd.

The housing is filled out to a new outline, tapered toward the jack or
stepped to follow the PCB, a sliding switch cover drives S1, and a rear cover
tray holds the PCB from its top face down. The original four PCB screws pass
up through the tray and PCB into the housing bosses, with their heads sunk
flush in the tray.

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
    # Outer shape: full width at the USB-C end, then the sides curve in toward
    # the jack end on two large arcs ("taper"), or step in with the PCB's
    # three widths ("conformal").
    "outline": "taper",
    "outer": (-4.0, -0.6, 46.0, 94.6),  # x0, y0, x1, y1 of the full-width outline
    "outer_r": 4.0,  # USB-C end corners
    "taper": (75.0, 3.0, 6.0),  # sides start to curve in at this y, inset of each side at the jack end face, jack-end corner radius
    # The original housing outline, flush with the PCB: half-widths about x 21
    # of the jack, middle and USB-C sections, and its 45 degree steps and
    # jack-end corners as lines x - y = c (right side; the left mirrors it).
    "housing_steps": ((19.0, 21.0, 22.0), (16.0, -15.0), 35.99),
    "conformal": (3.0, 1.5, 3.0),  # side wall outside the original housing, step corner radius, jack-end corner radius
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
    "flange_margin": 1.0,  # flange past the window above and below
    "flange_cover": 0.75,  # flange past each end of the window at either end of the travel; more thins the USB-end corner
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
    "groove": (0.8, 1.0, 1.1),  # inset from the outer face, width, depth
    "groove_y": (5.9, 89.1),
    "tongue": (0.6, 0.6, 0.2),  # width, height, end clearance; centred in the groove (0.8 x 1.0 was too tight)
    # Flexure button: a black bar from the top plate ending in a round pad over
    # the original plunger post, freed by a U slot. Only the pad is blue.
    "button_pad": (33.82, 68.64, 3.7),  # centre x, y (the post's) and radius; covers the post (r 3.5)
    "button_bar": (16.0, 4.0),  # root x and width, on the pad's centreline
    "button_slot_w": 0.7,
    # The R+D logo moves to the top right corner, 3.5 mm in from the edges and
    # 3 mm clear of the button: scale, then where the top right corner of its
    # bounding box goes (from 22.19, 90.29).
    "logo": (0.9, (42.45, 91.10)),
    # Under the button, a U of walls round the slot holds a floor that stops
    # its travel, 5 mm clear of the OLED board edge where its ribbon folds round.
    "button_tray": (29.8, 0.8, 9.57, 10.57),  # fences to x, wall thickness, floor z
    "plate_z": 12.57,  # top plate underside
    "inlay_z": (13.52, 14.17),  # same depth as the logo inlay
    # Print-in-place snap clips for the OLED module: a beam either side of its
    # board, bridged between posts beyond its ends, with a lip that catches the
    # board's back and holds the glass on the plate.
    "oled_board": (7.25, 31.64, 34.75, 59.44, 9.57),  # x0, y0, x1, y1, back face z
    "clip_gap": 0.2,  # beams and end tabs to the board edges
    "clip_beam": (1.2, 8.77, 11.07),  # thickness, bottom z, top z (1.5 under the plate, so the bridge can sag)
    "clip_post": 2.0,  # post size in plan; the end tabs reach this far over the board corners
    "clip_lip": (0.6, 8.0, 0.3),  # reach from the beam, length, how far it would lift the board at rest
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


def rect(x0, y0, x1, y1, z=0.0):
    return Part.Face(Part.makePolygon([V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)]))


def disc(x, y, r, z=0.0):
    return Part.Face(Part.Wire(Part.makeCircle(r, V(x, y, z))))


def sector(x, y, r, a0, a1, z=0.0):
    """Pie slice from angle a0 to a1 (degrees, anticlockwise). Its arc is drawn
    as chords, so trim circles of radius r / 1.1 or less with it."""
    n = math.ceil((a1 - a0) / 30.0)
    pts = [V(x, y, z)] + [V(x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                            y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), z) for i in range(n + 1)]
    return Part.Face(Part.makePolygon(pts + pts[:1]))


def offset_face(face, d):
    """2D offset with the offset curves turned into B-splines, which STEP
    readers rebuild into a closed solid."""
    edges = [e.toNurbs().Edges[0] if e.Curve.TypeId == "Part::GeomOffsetCurve" else e
             for e in face.makeOffset2D(d).OuterWire.Edges]
    return Part.Face(Part.Wire(Part.__sortEdges__(edges)))


def merge_faces(shape):
    """One face from coplanar overlapping faces, without inner holes."""
    faces = Part.Shell(shape.Faces).removeSplitter().Faces
    assert len(faces) == 1
    return Part.Face(faces[0].OuterWire)


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


def taper_arcs():
    """The two side arcs: (centre x left, centre x right, centre y, radius)."""
    x0, y0, x1, _ = P["outer"]
    ys, d, _ = P["taper"]
    R = ((ys - y0) ** 2 + d * d) / (2 * d)  # meets the jack end face d in from the side
    return x0 + R, x1 - R, ys, R


def conformal_steps():
    """Right side of the conformal outline: centre x, the three side x values
    (jack, middle, USB-C sections) and the step lines x - y = c, all moved out
    by the wall."""
    x0, _, x1, _ = P["outer"]
    xc = (x0 + x1) / 2
    (hj, hm, hu), (cl, cu), cj = P["housing_steps"]
    w = P["conformal"][0]
    d = w * math.sqrt(2)  # a 45 degree line moved out by w
    return xc, (xc + hj + w, xc + hm + w, xc + hu + w), (cl + d, cu + d, cj + d)


def half_width(y):
    """Distance from the centreline to the case side at y (before the corners round it)."""
    x0, _, x1, _ = P["outer"]
    if P["outline"] == "conformal":
        xc, (xj, xm, xu), (cl, cu, cj) = conformal_steps()
        for x_lo, x_hi, c in ((xm, xu, cu), (xj, xm, cl), (-1e9, xj, cj)):
            if y >= x_hi - c:
                return x_hi - xc
            if y >= x_lo - c:
                return y + c - xc  # on the 45 degree step
    if P["taper"][1] <= 0 or y >= P["taper"][0]:
        return (x1 - x0) / 2
    cl, _, ys, R = taper_arcs()
    return (x1 - x0) / 2 - (R - math.sqrt(R * R - (ys - y) ** 2))


def filleted_polygon(pts, radii, z=0.0):
    """Closed polygon through pts (anticlockwise) with a tangent arc of
    radii[i] at each corner."""
    n = len(pts)
    pts = [V(x, y, z) for x, y in pts]
    corners = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        u1, u2 = (p1 - p0).normalize(), (p2 - p1).normalize()
        half = math.acos(max(-1.0, min(1.0, u1.dot(u2)))) / 2  # half the turn
        t = radii[i] * math.tan(half)
        mid = p1 + (u2 - u1).normalize() * (radii[i] / math.cos(half) - radii[i])
        corners.append((p1 - u1 * t, mid, p1 + u2 * t))
    edges = []
    for i, (a, m, b) in enumerate(corners):
        edges += [Part.Arc(a, m, b), Part.LineSegment(b, corners[(i + 1) % n][0])]
    return Part.Face(Part.Wire([e.toShape() for e in edges]))


def conformal_outline(z=0.0):
    """Case outline that follows the PCB: the original housing outline with
    its three widths and 45 degree steps, moved out by the wall along the
    sides, between the end faces."""
    _, y0, _, y1 = P["outer"]
    xc, (xj, xm, xu), (cl, cu, cj) = conformal_steps()
    _, rs, rj = P["conformal"]
    right = [(cj + y0, y0), (xj, xj - cj), (xj, xj - cl), (xm, xm - cl), (xm, xm - cu), (xu, xu - cu), (xu, y1)]
    left = [(2 * xc - x, y) for x, y in reversed(right)]
    radii = [rj, rj, rs, rs, rs, rs, P["outer_r"]]
    return filleted_polygon(right + left, radii + radii[::-1], z)


def plan_outline(z=0.0):
    """Case outline in plan."""
    if P["outline"] == "conformal":
        return conformal_outline(z)
    return taper_outline(z)


def taper_outline(z=0.0):
    """Straight sides from the USB-C end, then arcs that bring each side in
    toward the jack end, rounded into the jack end face."""
    x0, y0, x1, y1 = P["outer"]
    r = P["outer_r"]
    ys, d, rj = P["taper"]
    if d <= 0:
        return rounded_rect(x0, y0, x1, y1, r, z)
    cl, cr, _, R = taper_arcs()
    k = r * (1 - math.sqrt(0.5))
    pt = lambda x, y: V(x, y, z)
    on = lambda cx, cy, rr, a: pt(cx + rr * math.cos(a), cy + rr * math.sin(a))
    ends = {}
    for side, cx in ((-1, cl), (1, cr)):
        # Corner circle tangent to the jack end face and inside the side arc;
        # it meets the side arc on the line through both centres.
        fx = cx + side * math.sqrt((R - rj) ** 2 - (ys - y0 - rj) ** 2)
        fy = y0 + rj
        t = math.atan2(fy - ys, fx - cx) % (2 * math.pi)  # same angle from both centres
        ends[side] = (fx, fy, t)
    (fl, fyl, tl), (fr, fyr, tr) = ends[-1], ends[1]
    tr -= 2 * math.pi  # just below 0 on the right, just past pi on the left
    edges = [
        Part.LineSegment(pt(fl, y0), pt(fr, y0)),
        Part.Arc(pt(fr, y0), on(fr, fyr, rj, (tr - math.pi / 2) / 2), on(fr, fyr, rj, tr)),
        Part.Arc(on(fr, fyr, rj, tr), on(cr, ys, R, tr / 2), pt(x1, ys)),
        Part.LineSegment(pt(x1, ys), pt(x1, y1 - r)),
        Part.Arc(pt(x1, y1 - r), pt(x1 - k, y1 - k), pt(x1 - r, y1)),
        Part.LineSegment(pt(x1 - r, y1), pt(x0 + r, y1)),
        Part.Arc(pt(x0 + r, y1), pt(x0 + k, y1 - k), pt(x0, y1 - r)),
        Part.LineSegment(pt(x0, y1 - r), pt(x0, ys)),
        Part.Arc(pt(x0, ys), on(cl, ys, R, (math.pi + tl) / 2), on(fl, fyl, rj, tl)),
        Part.Arc(on(fl, fyl, rj, tl), on(fl, fyl, rj, (tl + 1.5 * math.pi) / 2), pt(fl, y0)),
    ]
    return Part.Face(Part.Wire([e.toShape() for e in edges]))


def envelope(z0, z1):
    s = plan_outline().extrude(V(0, 0, z1 - z0))
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
    clear, add, slot = button_slot(H)
    h = h.cut(clear).fuse(add).cut(slot).removeSplitter()
    h = h.fuse(screen_clips()).removeSplitter()
    return h, pcb


def slider_geom():
    c = P["slider_clear"]
    xi = P["pcb_edge_x"] + P["pcb_edge_gap"] + 0.08  # flange inner face
    xf = xi + P["flange_t"]  # flange outer face
    xw = xf + c  # window wall inner face
    wz0, wz1 = P["window_z"]
    m = P["flange_margin"]
    gl, t = P["grip_len"], P["travel"]
    fl = gl + 2 * c + 2 * t + 2 * P["flange_cover"]  # covers the whole window at either end of the travel
    return dict(xi=xi, xf=xf, xw=xw, wz0=wz0, wz1=wz1, fz0=wz0 - m, fz1=wz1 + m, gl=gl, fl=fl, c=c)


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


def tongue(groove=False):
    """Tongues on the rear cover rim along the two long sides, centred in grooves
    in the housing; they follow the sides' curve. The end walls are too thin
    beside the PCB for one."""
    a, w, h = P["groove"]
    e = 0.0
    if not groove:
        w, h, e = P["tongue"]
        a += (P["groove"][1] - w) / 2
    ya, yb = P["groove_y"]
    zs = P["pcb_top_z"]
    f = plan_outline()
    band = offset_face(f, -a).cut(offset_face(f, -a - w)).common(rect(-20, ya + e, 70, yb - e))
    t = band.extrude(V(0, 0, h + 0.01))
    t.translate(V(0, 0, zs - 0.01))
    gaps = [g.BoundBox for g in slider_cuts()]
    return t.cut([box(g.XMin, g.YMin - 0.6 - e, zs - 1, g.XMax + 2, g.YMax + 0.6 + e, zs + 3) for g in gaps])


def button_slot_face(z):
    """The U slot round the bar and the pad. Its two channels have round ends
    at the root, where the bar joins the plate."""
    px, py, pr = P["button_pad"]
    xr, bw = P["button_bar"]
    w, h = P["button_slot_w"], P["button_bar"][1] / 2
    outer = merge_faces(rect(xr, py - h - w, px, py + h + w, z).fuse(disc(px, py, pr + w, z)))
    inner = merge_faces(rect(xr - 1, py - h, px, py + h, z).fuse(disc(px, py, pr, z)))
    slot = outer.cut(inner)
    for yc in (py - h - w / 2, py + h + w / 2):
        slot = merge_faces(slot.fuse(disc(xr, yc, w / 2, z)))
    return slot


def button_slot(H):
    """The original button is smaller. Fill its slot and clear its tray, then
    cut the U slot and stand a U of walls 0.05 outside it, fences along the two
    channels and an end wall behind the root, down to a floor that stops the
    button 2 mm down."""
    zu, zt = P["plate_z"], P["top_z"]
    px, py, pr = P["button_pad"]
    xr, bw = P["button_bar"]
    x1, t, f0, f1 = P["button_tray"]
    w = P["button_slot_w"]
    old = [s for s in H.slice(V(0, 0, 1), zt - 0.2)
           if s.BoundBox.XLength < 30 and s.BoundBox.isInside(V(25, 68.725, zt - 0.2))]
    assert len(old) == 1
    fill = ext(offset_face(Part.Face(old[0]), 0.1).OuterWire, zu, zt)
    # Original walls x 13.35-29.95, y 60.5-72.23, and their floor.
    clear = box(13.0, 60.0, f0 - 0.1, 29.95, 72.6, zu)
    g = 0.05
    xe = xr - w / 2 - g - t  # end wall behind the round slot ends
    yb, yt = py - bw / 2 - w - g, py + bw / 2 + w + g  # fence faces on the slot side
    u = rect(xe, yb - t, x1, yb).fuse([rect(xe, yt, x1, yt + t), rect(xe, yb - t, xe + t, yt + t)])
    walls = ext(merge_faces(u).OuterWire, f1 - 0.05, zu + 0.25)
    floor = box(xe, yb - t, f0, 29.95, yt + t, f1)
    slot = ext(button_slot_face(zu).OuterWire, zu, zt + 1)
    return clear, [fill, floor, walls], slot


def button_inlay(grow=0.05):
    """Blue on the round pad only, grown a hair into the slot so the cut never
    lands on its walls; the bar stays black."""
    px, py, pr = P["button_pad"]
    z0, z1 = P["inlay_z"]
    return disc(px, py, pr + grow, z0).extrude(V(0, 0, z1 + 1 - z0))


def logo_inlay(logo):
    """The original logo inlay (its top faces at the top face), scaled about
    the top right corner of its bounding box and moved to P["logo"], at the
    same depth."""
    s, (x, y) = P["logo"]
    zt = P["top_z"]
    tops = [f.copy() for f in logo.Faces if f.normalAt(0, 0).z > 0.99 and abs(f.CenterOfMass.z - zt) < 1e-3]
    bb = Part.makeCompound(tops).BoundBox
    depth = zt - logo.BoundBox.ZMin
    solids = []
    for f in tops:
        f.scale(s, V(bb.XMax, bb.YMax, zt))
        f.translate(V(x - bb.XMax, y - bb.YMax, 0))
        solids.append(f.extrude(V(0, 0, -depth)))
    return Part.makeCompound(solids)


def screen_clips():
    """A beam either side of the OLED board, bridged between two posts that
    hang from the plate beyond the board's ends; tabs on the posts stop the
    board along Y. A lip in the middle of each beam catches the board's back
    with a 45 degree face that would lift the board clip_lip[2] past its seat,
    so the beams stay sprung and press the glass onto the plate. Printed top
    face down, the beams are bridges and the lips' faces are 45 degree slopes,
    so nothing needs support."""
    bx0, by0, bx1, by1, zb = P["oled_board"]
    g, s = P["clip_gap"], P["clip_post"]
    t, z0, z1 = P["clip_beam"]
    reach, ll, dz = P["clip_lip"]
    zp = P["plate_z"] + 0.33  # into the plate
    zr = zb + dz + g  # catch face at the beam
    ym = (by0 + by1) / 2
    ya, yb = by0 - g, by1 + g  # post faces toward the board
    parts = []
    for xi, out in ((bx0 - g, -1), (bx1 + g, 1)):  # beam inner face, outward direction
        xs = lambda d: xi + out * d  # d: distance outward from the inner face
        xlo, xhi = sorted((xs(0), xs(t)))
        parts.append(box(xlo, ya - s, z0, xhi, yb + s, z1))
        plo, phi = sorted((xs(0), xs(s)))  # posts, outside the beam line
        tlo, thi = sorted((xs(0), xs(-s)))  # end tabs, over the board corners
        for y0, y1 in ((ya - s, ya), (yb, yb + s)):
            parts.append(box(plo, y0, z0, phi, y1, zp))
        for y0, y1 in ((ya - 1.0, ya), (yb, yb + 1.0)):
            parts.append(box(tlo, y0, zb, thi, y1, zp))  # down to the board back, clear of the battery
        lip = Part.Face(Part.makePolygon([V(xs(0.01), ym - ll / 2, zr), V(xs(-reach), ym - ll / 2, zr - reach),
                                          V(xs(0.01), ym - ll / 2, zr - 2 * reach), V(xs(0.01), ym - ll / 2, zr)]))
        parts.append(lip.extrude(V(0, ll, 0)))
    return parts[0].fuse(parts[1:]).removeSplitter()


def build_all(doc):
    logo0 = doc.getObject("Body").Shape
    H = doc.getObject("Part__Feature001").Shape.fuse(logo0).removeSplitter()  # fill the original logo pocket
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
    logo = logo_inlay(logo0)
    housing = housing.cut(logo).removeSplitter()
    housing = housing.cut(tongue(groove=True)).removeSplitter()
    print("housing", housing.isValid(), len(housing.Solids), round(housing.Volume, 1))
    print("slider", slider.isValid(), len(slider.Solids), round(slider.Volume, 1))
    print("cover", cover.isValid(), len(cover.Solids), round(cover.Volume, 1))

    return dict(
        housing=housing,
        slider=slider,
        cover=cover,
        s1=build_s1(doc.getObject("Part__Feature002").Shape),
        button=button,
        logo=logo,
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
    )
