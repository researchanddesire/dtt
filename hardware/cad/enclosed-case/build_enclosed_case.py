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
    # Blue inlay on the flexure button (a touch point). The button is cut free
    # of the top plate by a slot round a ball, a shaft and a head, and bends at
    # the plate between the start of the top channel and the end of the arc.
    "button_left": (17.45, 64.4, 3.5),  # ball: centre x, y, radius
    "button_bar_y": (66.025, 71.425),  # shaft edges
    "button_channel_w": (0.8, 0.7),  # slot below and above the shaft
    "button_slot": (22.542, 188.0, 0.7),  # top channel start x, arc end (degrees), arc and ring width
    "button_ball2": (12.55, 63.7, 3.5),  # second ball, on the case behind the first
    "button_shaft_x0": 14.6,  # centre of the shaft's round end
    "button_blend": 4.5,  # fillet from the shaft end into the second ball
    # Head: a soft rim at the back and a dome to the tip.
    "head_rim": (30.1, 64.2, 72.6, 2.5),  # back x, bottom y, top y, corner radius
    "head_dome": (32.6, 6.0),  # dome start x and length; the tip is on the shaft axis
    # Under the button, walls round the slot hold a floor that stops its travel.
    "button_tray": (13.35, 29.8, 0.8, 9.57, 10.57),  # fences from x, to x, wall thickness, floor z
    "plate_z": 12.57,  # top plate underside
    "oled_clear": (59.75, 11.0),  # tray stays clear of the OLED board below this y and z
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
    clear, add, slot = button_slot(H)
    h = h.cut(clear).fuse(add).cut(slot).removeSplitter()
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
    in the housing. The end walls are too thin beside the PCB for one."""
    x0, y0, x1, y1 = P["outer"]
    a, w, h = P["groove"]
    e = 0.0
    if not groove:
        w, h, e = P["tongue"]
        a += (P["groove"][1] - w) / 2
    ya, yb = P["groove_y"]
    zs = P["pcb_top_z"]
    t = [box(x0 + a, ya + e, zs - 0.01, x0 + a + w, yb - e, zs + h),
         box(x1 - a - w, ya + e, zs - 0.01, x1 - a, yb - e, zs + h)]
    gaps = [g.BoundBox for g in slider_cuts()]
    return Part.makeCompound(t).fuse([]).cut(
        [box(g.XMin, g.YMin - 0.6 - e, zs - 1, g.XMax + 2, g.YMax + 0.6 + e, zs + 3) for g in gaps])


def button_head(z, grow=0.0):
    """Outline of the button head at height z, grown outwards by grow. The dome
    is two quarter ellipses that meet at the tip, on the shaft axis, so the top
    and the bottom of the head can stand out from the shaft by different amounts."""
    xc, yb, yt, rc = P["head_rim"]
    xe, a = P["head_dome"]
    ym = sum(P["button_bar_y"]) / 2
    parts = [rect(xc, yb + rc, xe, yt - rc, z), disc(xc + rc, yb + rc, rc, z), disc(xc + rc, yt - rc, rc, z)]
    if xe > xc + rc:
        parts.append(rect(xc + rc, yb, xe, yt, z))
    for y0, y1, b in ((ym, yt + 1, yt - ym), (yb - 1, ym, ym - yb)):
        assert a > b  # the ellipse's major axis runs along X
        dome = Part.Face(Part.Wire(Part.Ellipse(V(xe, ym, z), a, b).toShape()))
        parts.append(dome.common(rect(xe, y0, xe + a + 1, y1, z)))
    head = merge_faces(parts[0].fuse(parts[1:]))
    return offset_face(head, grow) if grow else head


def button_slot_face(z):
    """The slot that frees the button: an arc round the ball from behind it,
    channels below and above the shaft, and a ring round the head."""
    lx, ly, lr = P["button_left"]
    b0, b1 = P["button_bar_y"]
    cb, ct = P["button_channel_w"]
    xt, a_end, w = P["button_slot"]
    xc, _, _, rc = P["head_rim"]
    aj = math.degrees(math.asin((b0 - ly) / lr))  # where the ball meets the shaft
    ro, rm = lr + w, lr + w / 2
    arc = disc(lx, ly, ro, z).cut(disc(lx, ly, lr, z)).common(sector(lx, ly, 2 * ro, a_end, 360 + aj, z))
    arc = arc.cut(rect(lx, b0, lx + ro, b0 + ro, z))
    end = disc(lx + rm * math.cos(math.radians(a_end)), ly + rm * math.sin(math.radians(a_end)), w / 2, z)
    xh = xc + rc  # the channels run into the head, which trims them
    below = rect(lx, b0 - cb, xh, b0, z).cut(disc(lx, ly, lr, z))
    above = rect(xt + ct / 2, b1, xh, b1 + ct, z).fuse(disc(xt + ct / 2, b1 + ct / 2, ct / 2, z))
    head = button_head(z)
    slot = offset_face(head, w).cut([head, rect(xc - w - 0.2, b0, xh, b1, z)])
    # One piece at a time: in a single boolean the shaft edge, which the arc and
    # the lower channel share, leaves a broken face.
    for f in (below.cut(head), above.cut(head), arc, end):
        slot = merge_faces(slot.fuse(f))
    return slot


def button_slot(H):
    """The original button is smaller. Fill its slot and clear its tray walls,
    then cut the slot again round the new icon and stand new walls 0.05 outside
    it: an arc round the ball and fences along the two channels, down to a
    floor that stops the button 2 mm down."""
    zu, zt = P["plate_z"], P["top_z"]
    x0, x1, t, f0, f1 = P["button_tray"]
    lx, ly, lr = P["button_left"]
    b0, b1 = P["button_bar_y"]
    cb, ct = P["button_channel_w"]
    _, a_end, w = P["button_slot"]
    old = [s for s in H.slice(V(0, 0, 1), zt - 0.2)
           if s.BoundBox.XLength < 30 and s.BoundBox.isInside(V(25, 68.725, zt - 0.2))]
    assert len(old) == 1
    fill = ext(offset_face(Part.Face(old[0]), 0.1).OuterWire, zu, zt)
    clear = box(13.0, 60.0, f1 - 0.07, 29.95, 72.6, zu)  # original walls: x 13.35-29.95, y 60.5-72.23
    g, z = 0.05, f1
    r0, r1 = lr + w + g, lr + w + g + t
    yb, yt = b0 - cb - g, b1 + ct + g  # fence faces on the slot side
    lower = merge_faces(disc(lx, ly, r1, z).fuse(rect(lx, yb - t, x1, yb, z)))
    for f in (disc(lx, ly, r0, z), rect(lx, yb, lx + r1, yb + r1, z), button_head(z, w + g)):
        lower = lower.cut(f)
    lower = lower.common(sector(lx, ly, 2 * (x1 - lx), a_end, 450, z))
    upper = rect(x0, yt, x1, yt + t, z).cut(button_head(z, w + g))
    # Into the plate, whose underside steps up 0.2 mm over the OLED (y < 60).
    oled = box(x0 - 2, ly - r1 - 1, f0 - 1, x1 + 2, P["oled_clear"][0], P["oled_clear"][1])
    walls = [ext(merge_faces(f).OuterWire, f1 - 0.05, zu + 0.25).cut(oled) for f in (lower, upper)]
    floor = ext(merge_faces(disc(lx, ly, r1, z).fuse(rect(x0, yb - t, x1 + 0.15, yt + t, z))).OuterWire, f0, f1)
    floor = floor.cut(oled)
    slot = ext(button_slot_face(zu).OuterWire, zu, zt + 1)
    return clear, [fill, floor] + walls, slot


def button_inlay(grow=0.05):
    """Button icon: head, shaft and two balls. The first ball, the shaft bottom
    and the head follow the slot, grown a hair into it so the cut never lands on
    its walls. The second ball sits on the case behind the first, so the slot arc
    between them reads as the crease, and a fillet runs the shaft end into it."""
    lx, ly, lr = P["button_left"]
    bx, by, br = P["button_ball2"]
    b0, b1 = P["button_bar_y"]
    xs, ys, hs = P["button_shaft_x0"], (b0 + b1) / 2, (b1 - b0) / 2 + grow
    rf = P["button_blend"]
    xc = P["head_rim"][0]
    z0, z1 = P["inlay_z"]

    def tri(*pts):
        return Part.Face(Part.makePolygon([V(x, y, z0) for x, y in pts + pts[:1]]))

    # Fillet circle touching the shaft end and the second ball from behind.
    r1, r2 = hs + rf, br + rf
    dx, dy = bx - xs, by - ys
    d = math.hypot(dx, dy)
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(r1 * r1 - a * a)
    fx, fy = xs + (a * dx + h * dy) / d, ys + (a * dy - h * dx) / d
    icon = merge_faces(disc(lx, ly, lr + grow, z0).fuse([
        disc(bx, by, br, z0),
        button_head(z0, grow),
        disc(xs, ys, hs, z0),
        rect(xs, b0 - grow, xc + 1, b1 + grow, z0),
        tri((xs, ys), (bx, by), (lx, ly)),  # closes the pinhole between the three
        tri((xs, ys), (bx, by), (fx, fy)).cut(disc(fx, fy, rf, z0)),
    ]))
    return icon.extrude(V(0, 0, z1 + 1 - z0))


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
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
    )
