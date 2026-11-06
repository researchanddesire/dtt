"""Build the enclosed DTT case from ../DTT.FCStd.

The housing is filled out to a new outline, tapered toward the jack or
stepped to follow the PCB, and takes the PCB in a pocket down to its back
face, so the rear cover is a flat cap. A sliding switch cover drives S1. The
original four PCB screws pass up through the cap and PCB into the housing
bosses, with their heads sunk flush in the cap.

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
    "pcb_top_z": -3.5,
    "pcb_bottom_z": -5.1,
    "seam_z": -5.1,  # housing to rear cover: the PCB sits in a pocket in the housing and the cover is a flat cap
    "pcb_usb_y": 92.98,  # the PCB's USB-C edge, flush with the receptacle
    "usb_end_gap": 0.1,  # pocket to that edge, so a skin hides the PCB edge behind the plug recess
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
    # Lofted sides: upright from the seam to past S1's window and channel, then
    # each long side curves in on an arc, so the case slims away from the PCB.
    "lean": (0.0, 2.5),  # inset of each side at the top face (0 keeps them upright), z where the lean starts
    "top_z": 14.17,
    # Round along the top edge, built into the lofted sides, so it can be larger
    # than the USB-C end corners: those tighten as the round brings the outline
    # in, toward corner_min_r. It runs round the jack end too. The round stops
    # where it has turned round_stop degrees from upright, and a straight face
    # carries on at that slope to the top face, so it prints top face down
    # without support. Under it the walls are kept min_wall thick from inside.
    # The conformal outline's 1.5 mm step corners keep a plain edge_fillet and
    # the original sloped jack end instead.
    "top_round": 5.0,
    "round_stop": 45.0,
    "corner_min_r": 1.0,
    "min_wall": 1.6,
    "edge_fillet": 1.2,  # conformal outline only
    "bottom_chamfer": 0.8,
    # Sloped sensor end of the original housing: z = z0 + k * (y - y0).
    "slope": (9.774, 1.2, 1.368),
    "wall_overlap": 0.6,  # bond depth into the original wall
    "top_overlap": 2.0,  # in the top plate, past the original edge chamfer
    "top_band_z": 12.4,  # just under the top plate (underside at 12.6)
    "pcb_edge_gap": 0.3,  # PCB edge to the pocket wall
    # Rear cover (a flat cap under the PCB).
    "cover_thickness": 3.0,  # floor under the PCB
    "cover_pocket_inset": 0.9,  # pocket edge inside the PCB outline
    "cover_pocket_depth": 1.3,  # clears USB shell legs and jack pegs
    "cover_relief": 0.2,  # floor stays clear of the PCB except at the pads
    "cover_pad_d": 7.5,
    # Alternative rear cover that takes two suction cups straight on the back,
    # in keyholes that run sideways in opposite directions, so the case can't
    # slide off its cups whichever way it is pulled. Both slots rise 30 degrees
    # into their click ends, which sit on the centreline, so the cups end up
    # dead centre and the case's weight pushes them into their clicks. Flatter
    # slots don't fit between the jack's pegs and the screws. The cups have a stem with a
    # 15 x 3 mm head and an 8.5 x 2.5 mm groove, as in the snap backplate. The
    # heads sit in chambers under the PCB, between the jack's pegs (y 11.7) and
    # the headers' pins (y 80.1), where the PCB has nothing on its back but
    # vias, and the keyholes stay 2 mm clear of the screws. Each chamber has a
    # roof, so the PCB stays fully enclosed.
    "cup_cover_extra": 4.0,  # floor added to the cover: land, head, room and roof under the PCB
    "cup_keys": ((21.0, 22.8, 30.0), (21.0, 71.0, 150.0)),  # click end x, y, and the slide from the entry in degrees from +x
    "cup_slot": 12.0,  # entry to click end
    "cup_entry_d": 15.6,  # passes the 15 mm head
    "cup_slot_w": 8.9,  # free slot on the 8.5 mm groove
    "cup_snap": (8.6, 8.0, 1.5),  # click pocket diameter, mouth width and lead-in: the 8.5 groove squeezes through the mouth and clicks into the pocket
    "cup_land": 2.4,  # floor under the head, in the 2.5 mm groove
    "cup_head": (15.0, 3.0, 0.5),  # head diameter, thickness, room over it (the roof is bridged)
    "cup_roof": (0.9, 2.0, 0.5),  # roof over each chamber, up to the relief under the PCB; the wall its bridge lands on; clearance to the pegs and pins
    # The PCB's pegs and pins through to its back near the keyholes (x, y, hole
    # diameter, from the KiCad board): jack pegs, J4, S1 and USB-C shell legs.
    "cup_keepout": ((21.3, 4.7, 1.2), (21.3, 11.7, 1.2), (2.5, 80.8, 1.5), (5.0, 80.8, 1.5),
                    (40.7, 80.7, 0.9), (16.7, 86.0, 2.1), (25.3, 86.0, 2.1)),
    "cup_counterbore_d": 6.3,  # the screw heads stay at their usual depth
    "cup_proxy": (35.0, 14.0, 8.5, 2.5),  # cup diameter and depth (estimates), groove diameter and length
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
    "flange_margin": 1.0,  # flange past the window above it; the cap closes it below
    "flange_cover": 0.75,  # flange past each end of the window at either end of the travel; more thins the USB-end corner
    "grip_proud": 0.4,
    "window_z": (-4.95, 0.7),  # grip, bottom 0.15 above the seam
    "act_lead": 0.6,  # the actuator pocket is open underneath, so S1's lever drops into it, with this lead-in
    # Connector openings. The jack's hole is a plain round hole in the housing,
    # with 1.3 mm of wall under it: the PCB goes in jack end first, tilted, nose
    # into the hole. At USB-C a plug-sized opening, a room behind it for the
    # receptacle, and a recess round it for the plug's overmould.
    "jack_axis": (20.9, -0.7),
    "jack_d": 6.2,
    "usb_center": (20.95, -2.155),
    "usb_size": (9.2, 3.6),  # the receptacle face is 8.9 x 3.35, the plug 8.4 x 2.6
    "usb_r": 1.8,
    "usb_room": (16.2, 25.7, -0.18),  # x0, x1 and top z of the room for the receptacle, 0.3 clear
    "usb_recess": (13.0, 7.0, 1.0),  # width, height, depth; the overmould stops 0.6 short of the receptacle
    # Tongue on the cap's rim, in a groove in the housing, so the cap sits in
    # place before the screws go in.
    "groove": (0.75, 1.0, 1.9),  # inset from the outer face, width, depth
    "groove_y": (5.9, 89.1),
    "tongue": (0.6, 1.6, 0.3),  # width, height, end clearance; centred in the groove (0.2 a side fitted on print 1)
    # Flexure button: a black bar from the top plate ending in a round pad
    # right over S2, freed by a U slot, with a straight post under the pad down
    # to S2's plunger. Only the pad is blue.
    "button_pad": (36.51, 64.65, 3.5),  # centre x, y (S2's) and radius
    "button_bar": (18.69, 4.0),  # root x and width, on the pad's centreline
    "button_slot_w": 0.7,
    "button_post": (4.0, 1.0),  # diameter and bottom z: 1.2 over S2's plunger (top at -0.2)
    "button_clear": (29.9, 59.7, 41.0, 72.4),  # x0, y0, x1, y1: the original post and its offset stack, cleared
    # The R+D logo is tucked into the top left corner of the flat top, 1 mm in
    # from its edge: scale, then where the top left corner of its bounding box
    # goes (from 2.44, 90.29).
    "logo": (0.78, (-0.07, 90.67)),
    # Under the button, a U of walls round the slot holds a floor that stops
    # its travel, 1.6 mm clear of the OLED board's end.
    "button_tray": (32.7, 0.8, 9.57, 10.57),  # fences to x, wall thickness, floor z
    "plate_z": 12.57,  # top plate underside
    "inlay_z": (13.52, 14.17),  # same depth as the logo inlay
    # The screen's viewport, on its active area, with a 45 degree edge at the top face.
    "viewport": (21.0, 43.8, 23.2, 12.2, 0.5, 0.5),  # centre x, y, width, height, corner radius, chamfer
    "viewport_fill": (8.5, 38.2, 33.5, 52.9, 12.77),  # the old one: x0, y0, x1, y1, from z
    # Print-in-place snap clips for the OLED module: a beam either side of its
    # board, bridged between posts at its ends, with a lip that catches the
    # board's back and holds the glass on the plate.
    "oled_board": (7.25, 31.64, 34.75, 59.44, 9.57),  # x0, y0, x1, y1, back face z
    "clip_gap": 0.2,  # beams and end tabs to the board edges
    "clip_beam": (1.2, 8.77, 11.07),  # thickness, bottom z, top z (1.5 under the plate, so the bridge can sag)
    "clip_post": 2.0,  # post size in plan; the end tabs reach this far over the board corners
    "clip_lip": (0.7, 8.0, 0.1, 20.0),  # reach from the beam, length, how far it would lift the board at rest, catch face from flat (degrees)
    "clip_tab_right": 34.5,  # the right end tab at the button end stops here, clear of the button's slot
    # A rib under the plate where the ribbon would be if the module went in the
    # wrong way round (it runs from the glass to the board at the button end).
    "oled_key": (11.5, 33.2, 15.5, 37.2, 11.2),  # x0, y0, x1, y1, bottom z
    # Distance sensor: its mount moves left, which centres its lenses on the
    # case, and a rib beside its PCB stops it going in the wrong way round.
    "sensor_shift": -1.7,
    "sensor_mount": (5.0, 5.2, -2.0, 38.6, 24.2),  # box round the original mount: x0, y0, z0, x1, y1 (up to the plate)
    "sensor_window": (12.0, 8.5, 33.5, 18.7),  # box round its window in the plate
    "sensor_key": (9.5, 6.0, 0.6, 16.0, 8.0),  # rib x0, y0, z0, x1, y1, up to the plate
    "jack_body_clear": (17.26, 3.16, 24.84, 15.83, 2.0),  # J5's body and 0.3: x0, y0, x1, y1, top z; the moved mount stays clear of it
    # Battery: the cell drops in from the open back between two sprung beams
    # and clicks past a lip on each, which holds it up against the cross bars
    # over the bay. A block at the USB-C end and a gusset at the screen end
    # stop it along Y.
    "battery": (8.2, 54.7, 28.2, 89.7, 1.6, 8.6),  # cell x0, y0, x1, y1, z0, z1 (up against the cross bars)
    "battery_ring": (6.5, 72.5, 31.0, 89.6),  # the original rings' sides and lower bars, cut away
    "battery_beam": (0.8, 0.25, 0.5, 4.0),  # thickness, gap to the cell, bottom z, top z
    "battery_posts": ((6.45, 61.6, 63.3), (30.0, 61.15, 62.65)),  # screen-end posts: outer x, y0, y1 (the right one hangs from the button's floor)
    "battery_end": (6.5, 90.0, 30.0, 92.5),  # block at the USB-C end
    "battery_lip": (0.9, 8.0, 0.15),  # reach from the beam, length, gap under the cell
    "battery_gusset": (3.6, 53.0, 4.9, 54.3, 12.4),  # post x0, y0, x1, y1, and the gusset's foot to x
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


def side_inset(z):
    """How far each long side has leaned in at height z: nothing up to the
    start of the lean, then an arc that leaves the upright wall tangentially."""
    d, zv = P["lean"]
    if d <= 0 or z <= zv:
        return 0.0
    h = P["top_z"] - zv
    R = (h * h + d * d) / (2 * d)
    dz = min(z, P["top_z"]) - zv
    return R - math.sqrt(R * R - dz * dz)


def top_round():
    """Radius of the round built into the sides (none on the conformal outline)."""
    return P["top_round"] if P["outline"] == "taper" else 0.0


def stop_angle():
    """Where the top round hands over to the straight face, in radians from upright."""
    return math.radians(min(P["round_stop"], 90.0))


def round_inset(z, t=0.0):
    """How far the top round has brought the whole outline in at height z, on
    the surface t inside the outer one (its round has radius r - t, and the
    straight face above it is t inside the outer one)."""
    r = top_round()
    zc = P["top_z"] - r
    if r <= t or z <= zc:
        return t
    rho, a = r - t, stop_angle()
    za = zc + rho * math.sin(a)
    if z <= za or a > math.radians(89.9):
        dz = min(z - zc, rho)
        return r - math.sqrt(max(rho * rho - dz * dz, 0.0))
    return r - rho * math.cos(a) + math.tan(a) * (min(z, P["top_z"] - t) - za)


def outline_at(z, inset, around=0.0):
    """The plan outline with both long sides moved in by inset, then the whole
    outline moved in by around, as the top round does: the ends move in too and
    the convex corners tighten. Only the long sides move on the conformal
    outline."""
    if inset <= 1e-9 and around <= 1e-9:
        return plan_outline(z)
    saved = dict(P)
    try:
        if P["outline"] == "conformal":
            w, rs, rj = P["conformal"]
            P["conformal"] = (w - inset - around, rs, rj)
        else:
            x0, y0, x1, y1 = P["outer"]
            ys, d, rj = P["taper"]
            r = top_round()
            # Each corner tightens evenly as the outline comes in, from its own
            # radius to its radius less r at the top face, but not under corner_min_r.
            corner = lambda c: c - (c - max(c - r, P["corner_min_r"])) * min(around / r, 1.0) if r > 0 else c
            P["outer"] = (x0 + inset + around, y0 + around, x1 - inset - around, y1 - around)
            P["outer_r"] = corner(P["outer_r"])
            if d > 0:  # the side arcs keep their centres
                R = ((ys - y0) ** 2 + d * d) / (2 * d) - around
                d = R - math.sqrt(R * R - (ys - y0 - around) ** 2)
            P["taper"] = (ys, d, corner(rj))
        return plan_outline(z)
    finally:
        P.clear()
        P.update(saved)


def section_levels(t=0.0):
    """Heights of the loft sections, t below the outer faces: up through the
    lean and round the top round in equal steps of angle (curved), then up
    the straight face above the round to the top face (straight)."""
    r, zt = top_round(), P["top_z"]
    d, zv = P["lean"]
    zc = zt - r
    curved, straight = [], []
    if d > 0 and (r <= 0 or zv < zc):
        z1, n = (zc, 8) if r > 0 else (zt - t, 12)
        curved += [zv + (z1 - zv) * i / n for i in range(n)]
    if r > t:
        a = stop_angle()
        n = max(4, int(round(16 * a / (math.pi / 2))))
        curved += [zc + (r - t) * math.sin(a * i / n) for i in range(n + 1)]
        za = curved[-1]
        if zt - t > za + 1e-6:
            m = 4 if d > 0 else 1
            straight = [za + (zt - t - za) * i / m for i in range(m + 1)]
    elif curved:
        curved.append(zt - t)
    return curved, straight


def lofted_envelope(z0, t=0.0):
    """The case from z0 to the top face, or the surface t inside it: upright
    sides, then a loft through sections that lean in and round over the top,
    and a ruled one up the straight face above the round (smooth if the sides
    lean, which curves it)."""
    curved, straight = section_levels(t)
    zt = P["top_z"] - t
    za = curved[0] if curved else zt
    wire = lambda z: outline_at(z, side_inset(z), round_inset(z, t)).OuterWire
    s = outline_at(z0, 0.0, round_inset(z0, t)).extrude(V(0, 0, za - z0))
    if not curved:
        return s
    s = s.fuse(Part.makeLoft([wire(z) for z in curved], True, False))
    if straight:
        s = s.fuse(Part.makeLoft([wire(z) for z in straight], True, P["lean"][0] <= 0))
    return solid(s.removeSplitter())


def above_slope(shift):
    """Everything above the sensor-end slope, moved shift outwards along -Y."""
    z0, y0, k = P["slope"]
    y0 -= shift
    pts = [(y0 + (-20 - z0) / k, -20), (y0 + (40 - z0) / k, 40), (-40, 40), (-40, -20)]
    w = Part.makePolygon([V(-20, y, z) for (y, z) in pts] + [V(-20, pts[0][0], pts[0][1])])
    return Part.Face(w).extrude(V(80, 0, 0))


def outer_upper():
    """The outer form above the seam. The top round runs round the jack end
    too; without it the top edges get a plain fillet and the jack end keeps
    the original housing's sloped end, thickened."""
    y0 = P["outer"][1]
    zs, zt = P["seam_z"], P["top_z"]
    r = P["edge_fillet"]
    e = lofted_envelope(zs)
    if top_round() > 0:
        return e
    e = e.makeFillet(r, [ed for ed in e.Edges if ed.BoundBox.ZMin > zt - 1e-6])
    e = e.cut(above_slope(1.0 - y0))  # original end wall at y = 1
    try:
        slope = [f for f in e.Faces if f.Surface.TypeId == "Part::GeomPlane" and 0.5 < f.normalAt(0, 0).z < 0.99]
        e = e.makeFillet(r, slope[0].Edges)
    except Exception as ex:
        print("slope fillet skipped:", ex)
    return e


def solid(s):
    """The one solid in s. removeSplitter can leave stray vertices beside it
    in its compound, and the next boolean on that compound fails."""
    assert len(s.Solids) == 1, "expected one solid, got %d" % len(s.Solids)
    return s.Solids[0]


def fuse_checked(a, b):
    """a fused with b. On the original housing's faces OCC can fail or return
    an empty result, so check it, and retry on the bare solids."""
    def ok(s):
        return len(s.Solids) == 1 and s.Volume > max(a.Volume, b.Volume) - 1e-3
    try:
        s = a.fuse(b)
        if ok(s):
            return s
    except (Part.OCCError, ValueError):  # ValueError: a null result
        pass
    s = a.Solids[0].fuse(b.Solids[0])
    assert ok(s), "fuse failed"
    return s


def inner_form(d, z0):
    """The outer form with the top round from z0 up, d inside its faces."""
    return lofted_envelope(z0, d)


def round_backing(outer):
    """Where the top round comes closer than min_wall to the inside, the
    housing is filled out to min_wall behind it, in a band round the outline
    from the start of the round up. The fill stops 0.2 under the outer faces,
    which the housing already has, so the fuse meets no coincident faces."""
    r, t = top_round(), P["min_wall"]
    if r <= t:
        return None
    zc, zt = P["top_z"] - r, P["top_z"]
    f = plan_outline()
    ring = f.cut(offset_face(f, -(r + 2.0))).extrude(V(0, 0, zt + 1 - zc))
    ring.translate(V(0, 0, zc))
    return inner_form(0.2, zc - 1.0).cut(inner_form(t, zc - 1.0)).common(ring).common(outer).removeSplitter()


def usb_pocket_end():
    return P["pcb_usb_y"] + P["usb_end_gap"]


def connector_cuts():
    """The jack's round hole; at USB-C a room for the receptacle behind a
    plug-sized opening, and the recess for the plug's overmould."""
    jx, jz = P["jack_axis"]
    ux, uz = P["usb_center"]
    x0, x1, z1 = P["usb_room"]
    ye = usb_pocket_end()
    return [Part.makeCylinder(P["jack_d"] / 2, 6.0, V(jx, -3.5, jz), V(0, 1, 0)),
            box(x0, ye - 4.1, P["pcb_top_z"] - 0.1, x1, ye, z1),
            stadium_y(ux, uz, P["usb_size"][0], P["usb_size"][1], P["usb_r"], ye - 0.1, P["outer"][3] + 1),
            usb_recess()]


def usb_recess():
    ux, uz = P["usb_center"]
    w, h, d = P["usb_recess"]
    y1 = P["outer"][3]
    return stadium_y(ux, uz, w, h, h / 2 - 1e-3, y1 - d, y1 + 1)


def pcb_pocket(pcb):
    """The PCB's outline pcb_edge_gap out, but only usb_end_gap past its USB-C
    edge: the pocket in the housing and the relief in the cap."""
    f = Part.Face(pcb.makeOffset2D(P["pcb_edge_gap"]))
    return f.cut(rect(-50, usb_pocket_end(), 100, 200)).Faces[0]


def build_housing(H, board):
    pcb = outline(board)
    p0 = pcb.copy()
    p0.translate(V(0.08, 0.02, 0))  # original housing outline
    zs, zt = P["seam_z"], P["top_z"] + 1

    # Fill between the original housing and the outer rectangle. Inside the
    # original wall keep the housing as it is, except above its sloped end,
    # where the fill thickens the slope so it meets the larger outline.
    keep = ext(p0.makeOffset2D(-P["wall_overlap"]), zs - 1, P["top_band_z"])
    # The slope cut sits 0.3 mm inside the original slope so the two bond
    # instead of meeting on one plane.
    keep = keep.fuse(ext(p0.makeOffset2D(-P["top_overlap"]), P["top_band_z"], zt)).cut(above_slope(-0.3))
    outer = outer_upper()
    fill = outer.cut(keep)
    h = H.fuse(fill)
    backing = round_backing(outer)
    if backing is not None:
        h = fuse_checked(h, backing)
    h = h.common(box(-20, -20, zs, 70, 120, zt)).removeSplitter()
    h = solid(h.common(outer).removeSplitter())  # the round and the lean pass inside the original wall's top
    h = move_sensor_mount(h, H)

    (a0, a1) = P["sw_body"]
    pocket = ext(pcb_pocket(pcb).OuterWire, zs - 1, P["pcb_top_z"])
    cuts = [box(a0[0], a0[1], a0[2] - 1, a1[0], a1[1], a1[2]), pocket] + slider_cuts() + connector_cuts()
    h = solid(h.cut(cuts).removeSplitter())
    h = battery_bay(h)
    clear, add, slot = button_slot(H)
    h = solid(h.cut(clear).fuse(add).cut(slot).removeSplitter())
    h = viewport(h)
    h = solid(h.fuse(screen_clips()).removeSplitter())
    return h, pcb


def move_sensor_mount(h, H):
    """Move the distance sensor's mount and its window in the plate by
    sensor_shift along X, and add the rib that keys it. The mount is what
    hangs from the plate of the original housing H inside the sensor_mount
    box without reaching its sides: the screw bosses, the ledges under the
    sensor PCB's ends and edge, and the frame round its optical case. The
    walls by the diffuser and the post on the main PCB run out of the box and
    stay. (In the filled housing the pieces meet along the plate, so they are
    picked from H.)"""
    x0, y0, z0, x1, y1 = P["sensor_mount"]
    wx0, wy0, wx1, wy1 = P["sensor_window"]
    kx0, ky0, kz0, kx1, ky1 = P["sensor_key"]
    zu, zt = P["plate_z"], P["top_z"]
    d = V(P["sensor_shift"], 0, 0)
    e = 0.02
    sides = box(x0, y0, z0, x1, y1, zu).cut(box(x0 + e, y0 + e, z0 + e, x1 - e, y1 - e, zu + 1))
    pieces = [s for s in H.common(box(x0, y0, z0, x1, y1, zu)).Solids if s.common(sides).Volume < 1e-6]
    jack = box(*P["jack_body_clear"][:2], z0 - 1, *P["jack_body_clear"][2:])
    mount = [s.translated(d).cut(jack) for s in pieces]
    hole = box(wx0, wy0, zu - 0.5, wx1, wy1, zt + 1).cut(h).translated(d)
    h = h.cut(pieces).fuse(box(wx0, wy0, zu - 0.01, wx1, wy1, zt))
    h = solid(h.fuse(mount).removeSplitter())
    h = h.cut(hole).fuse(box(kx0, ky0, kz0, kx1, ky1, zu + 0.3))
    return solid(h.removeSplitter())


def battery_bay(h):
    """Cut away the original rings' sides and lower bars, keeping the cross
    bars over the bay, and hang the clips: a beam either side of the cell
    between a post at the screen end and a block at the USB-C end, each with a
    lip in its middle that the cell clicks past, and a gusset in front of the
    cell's screen end. Printed top face down, the beams are bridges, the
    lips' catch faces short flat overhangs and the gusset a 45 degree slope."""
    cx0, cy0, cx1, cy1, c0, c1 = P["battery"]
    t, g, z0, z1 = P["battery_beam"]
    reach, ll, lg = P["battery_lip"]
    (lx, ly0, ly1), (rx, ry0, ry1) = P["battery_posts"]
    ex0, ey0, ex1, ey1 = P["battery_end"]
    zp = P["plate_z"] + 0.3
    h = h.cut(box(*P["battery_ring"][:2], -1.0, *P["battery_ring"][2:], c1))
    floor = P["button_tray"][2]
    parts = [box(lx, ly0, z0, cx0 - g, ly1, zp),  # left post, from the plate
             box(cx1 + g, ry0, z0, rx, ry1, floor + 0.3),  # right post, from the button's floor
             box(ex0, ey0, z0, ex1, ey1, zp)]  # block at the USB-C end
    zc = c0 - lg  # catch face, under the cell
    for xi, out, ya in ((cx0 - g, -1, ly0), (cx1 + g, 1, ry0)):  # beam inner face, outward direction
        xo = xi + out * t
        parts.append(box(min(xi, xo), ya, z0, max(xi, xo), ey1, z1))
        ym = (max(ly1, ry1) + ey0) / 2
        prof = [V(xi + out * 0.01, ym - ll / 2, zc), V(xi - out * reach, ym - ll / 2, zc),
                V(xi + out * 0.01, ym - ll / 2, zc - reach - 0.01)]
        parts.append(Part.Face(Part.makePolygon(prof + prof[:1])).extrude(V(0, ll, 0)))
    gx0, gy0, gx1, gy1, gf = P["battery_gusset"]
    parts.append(box(gx0, gy0, z0, gx1, gy1, zp))
    tri = [V(gx1 - 0.1, gy0, c1), V(gf, gy0, z0 + 0.6), V(gf, gy0, z0), V(gx1 - 0.1, gy0, z0)]
    parts.append(Part.Face(Part.makePolygon(tri + tri[:1])).extrude(V(0, gy1 - gy0, 0)))
    return solid(h.fuse(parts).removeSplitter())


def viewport(h):
    """Fill the old viewport and cut the new one over the screen's active
    area, with a 45 degree edge round it at the top face."""
    cx, cy, w, ht, r, c = P["viewport"]
    x0, y0, x1, y1, zf = P["viewport_fill"]
    zt = P["top_z"]
    h = h.fuse(box(x0, y0, zf, x1, y1, zt))
    rr = lambda d, z: rounded_rect(cx - w / 2 - d, cy - ht / 2 - d, cx + w / 2 + d, cy + ht / 2 + d, r + d, z).OuterWire
    chamfer = Part.makeLoft([rr(0, zt - c), rr(c, zt)], True, True)
    cuts = [ext(rr(0, 0), zf - 0.1, zt - c + 0.01), chamfer, ext(rr(c, 0), zt - 0.01, zt + 1)]
    return solid(h.cut(cuts).removeSplitter())


def slider_geom():
    c = P["slider_clear"]
    xi = P["pcb_edge_x"] + P["pcb_edge_gap"] + 0.08  # flange inner face
    xf = xi + P["flange_t"]  # flange outer face
    xw = xf + c  # window wall inner face
    wz0, wz1 = P["window_z"]
    m = P["flange_margin"]
    gl, t = P["grip_len"], P["travel"]
    fl = gl + 2 * c + 2 * t + 2 * P["flange_cover"]  # covers the whole window at either end of the travel
    return dict(xi=xi, xf=xf, xw=xw, wz0=wz0, wz1=wz1, fz0=wz0, fz1=wz1 + m, gl=gl, fl=fl, c=c)


def slider_cuts():
    """Channel for the flange and the grip window, both in the housing, open
    down to the seam; the cap closes them."""
    g = slider_geom()
    ya, t, c = P["act_y"], P["travel"], g["c"]
    zs = P["seam_z"]
    chan = box(g["xi"] - 0.2, ya - g["fl"] / 2 - c, zs - 0.01, g["xw"], ya + t + g["fl"] / 2 + c, g["fz1"] + c)
    win = box(g["xw"] - 0.1, ya - g["gl"] / 2 - c, zs - 0.01, P["outer"][2] + 1,
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
    # Pocket for the actuator, open underneath with a lead-in, so the cover
    # sits in its channel first and S1's lever drops into it with the PCB.
    z0, z1 = P["act_z"]
    w = P["act_w"] + 0.4
    f, xa, xb = P["act_lead"], g["xi"] - 1, P["act_tip_x"] + 0.4
    s = s.cut(box(xa, ya - w / 2, g["fz0"] - 1, xb, ya + w / 2, z1 + 0.25))
    zb = g["fz0"]
    lead = [V(xa, ya - w / 2 - f - 0.5, zb - 0.5), V(xa, ya + w / 2 + f + 0.5, zb - 0.5),
            V(xa, ya + w / 2, zb + f), V(xa, ya - w / 2, zb + f)]
    s = s.cut(Part.Face(Part.makePolygon(lead + lead[:1])).extrude(V(xb - xa, 0, 0)))
    return s.removeSplitter()


def build_cover(pcb, extra=0.0):
    """Rear cover: a flat cap from the seam at the PCB's back face down, with
    a relief under the PCB, so it presses the PCB only at pads round the
    screws. With extra, its floor is that much thicker, with the screw heads at
    their usual depth in counterbores, and it takes the suction-cup keyholes."""
    zs = P["seam_z"]
    zt = P["pcb_bottom_z"]
    zb = zt - P["cover_thickness"]
    zf = zb  # where the screw heads sit
    zb -= extra
    cover = envelope(zb, zs)
    try:
        bottom = [e for e in cover.Edges if e.BoundBox.ZMax < zb + 1e-6]
        cover = cover.makeChamfer(P["bottom_chamfer"], bottom)
    except Exception as e:
        print("cover chamfer skipped:", e)
    shell = cover.copy()
    # Relief under the PCB and the central pocket.
    cover = cover.cut(ext(pcb_pocket(pcb).OuterWire, zt - P["cover_relief"], zs + 1))
    cover = cover.cut(ext(pcb.makeOffset2D(-P["cover_pocket_inset"]), zt - P["cover_pocket_depth"], zs + 1))
    pads = [zcyl(x, y, P["cover_pad_d"], zt - P["cover_pocket_depth"] - 0.1, zt) for (x, y) in P["screw_axes"]]
    if extra:
        pads += cup_roofs(zt - P["cover_relief"])
    cover = cover.fuse(pads).common(shell)
    cover = cover.cut(connector_cuts())
    holes = []
    for (x, y) in P["screw_axes"]:
        holes.append(zcyl(x, y, P["screw_clear_d"], zb - 1, zt + 1))
        r = P["csk_d"] / 2
        h = (r - P["screw_clear_d"] / 2) / math.tan(math.radians(P["csk_angle"] / 2))
        holes.append(Part.makeCone(r + 0.5 * math.tan(math.radians(P["csk_angle"] / 2)), P["screw_clear_d"] / 2,
                                   h + 0.5, V(x, y, zf - 0.5)))
        if extra:
            holes.append(zcyl(x, y, P["cup_counterbore_d"], zb - 1, zf))
    cover = cover.cut(holes)
    if extra:
        cover = cover.cut(cup_keyholes(zb))
    return cover.removeSplitter()


def cup_key(k):
    """Click end, unit slide direction (entry to click) and entry of a keyhole."""
    cx, cy, ang = k
    u = V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0)
    return V(cx, cy, 0), u, V(cx, cy, 0) - u * P["cup_slot"]


def band(p, q, r, z0, z1):
    """Prism r either side of the line from p to q in plan, from z0 to z1."""
    n = V(p.y - q.y, q.x - p.x, 0)
    n.normalize()
    n = n * r
    pts = [V(a.x + n.x * k, a.y + n.y * k, z0) for a, k in ((p, 1), (q, 1), (q, -1), (p, -1))]
    return Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, 0, z1 - z0))


def cup_keyholes(zb):
    """Keyholes in the cup cover's floor (rear face at zb): an entry hole the
    head passes, a slot for the stem's groove that narrows to a mouth and opens
    into a round pocket the stem clicks into, and over the land a chamber the
    head slides along, under the roof from cup_roofs()."""
    re, w = P["cup_entry_d"] / 2, P["cup_slot_w"] / 2
    dp, mouth, lead = P["cup_snap"]
    m = mouth / 2
    ym = math.sqrt((dp / 2) ** 2 - m ** 2)  # the mouth's offset from the pocket centre
    yl = ym + lead
    zl = zb + P["cup_land"]
    _, ht, hc = P["cup_head"]
    zc = zl + ht + hc
    s = P["cup_slot"]
    cuts = []
    for k in P["cup_keys"]:
        c, u, e = cup_key(k)
        # (along, across) from the click end, along running away from the entry
        pts = [(-s, -w), (-s, w), (-yl, w), (-ym, m), (0, m), (0, -m), (-ym, -m), (-yl, -w)]
        poly = [V(c.x + a * u.x - b * u.y, c.y + a * u.y + b * u.x, zb - 1) for a, b in pts]
        slot = Part.Face(Part.makePolygon(poly + poly[:1])).extrude(V(0, 0, zl - zb + 2))
        cuts += [zcyl(e.x, e.y, 2 * re, zb - 1, zc), zcyl(c.x, c.y, dp, zb - 1, zl + 1), slot,
                 zcyl(c.x, c.y, 2 * re, zl, zc), band(e, c, re, zl, zc)]
    return cuts


def stadium(k, r, z0, z1):
    """What a disc of radius r sweeps sliding from a keyhole's entry to its click, from z0 to z1."""
    c, _, e = cup_key(k)
    return zcyl(e.x, e.y, 2 * r, z0, z1).fuse([zcyl(c.x, c.y, 2 * r, z0, z1), band(e, c, r, z0, z1)])


def cup_roofs(zr):
    """Blocks that rise from the pocket floor to zr over each keyhole's head
    chamber, so the chamber is roofed over and the PCB stays enclosed. Printed
    rear face down, the roof is the only part of the keyhole that prints in
    the air: a bridge across the chamber. Its wall is wide enough for the
    bridge to land on solid, and it is cut back around the PCB's pegs and pins."""
    _, wall, clear = P["cup_roof"]
    z0 = P["pcb_bottom_z"] - P["cover_pocket_depth"] - 0.1
    pins = [zcyl(x, y, d + 2 * clear, z0 - 1, zr + 1) for x, y, d in P["cup_keepout"]]
    return [stadium(k, P["cup_entry_d"] / 2 + wall, z0, zr).cut(pins).removeSplitter() for k in P["cup_keys"]]


def suction_cup(x, y, zb):
    """Suction cup proxy clicked into a keyhole of the cup cover (rear face at
    zb): cup body toward the wall, stem, groove through the land, head in the
    chamber. The same proxy as the snap backplate's."""
    cd, depth, gd, gl = P["cup_proxy"]
    hd, ht, _ = P["cup_head"]
    zs = zb - 0.1  # stem shoulder, just off the rear face
    rim, z0 = zb - depth, zs - 3.0
    outside = Part.makeCone(cd / 2, hd / 2, z0 - rim, V(x, y, rim))
    inside = Part.makeCone(cd / 2 - 1.2, hd / 2 - 1.2, z0 - rim - 1.5, V(x, y, rim - 0.1))
    stem = zcyl(x, y, hd, z0 - 0.5, zs)
    groove = zcyl(x, y, gd, zs - 0.01, zs + gl + 0.01)
    head = zcyl(x, y, hd, zs + gl, zs + gl + ht)
    return outside.cut(inside).fuse([stem, groove, head]).removeSplitter()


def cup_cover_rear():
    return P["pcb_bottom_z"] - P["cover_thickness"] - P["cup_cover_extra"]


def cup_checks(cover, cups, board, screws):
    """Numbers worth reading after a change to the cup cover."""
    bb = cover.BoundBox
    print("CHECK cup cover valid %s, %d solid, %.1f x %.1f x %.1f mm, %.1f cm3" % (
        cover.isValid(), len(cover.Solids), bb.XLength, bb.YLength, bb.ZLength, cover.Volume / 1000))
    zb = cup_cover_rear()
    print("CHECK case %.2f mm thick with it, %.1f more than with the usual cover" % (
        P["top_z"] - zb, P["cup_cover_extra"]))
    rest = [c.common(cover).Volume for c in cups]
    for i, c in enumerate(cups):
        print("CHECK cup %d: %.2f mm3 in the cover at rest (the click), head %.2f mm under the PCB, %.2f mm from a screw" % (
            i + 1, rest[i], c.distToShape(board)[0], min(c.distToShape(s)[0] for s in screws)))
    dp, mouth, _ = P["cup_snap"]
    gd = P["cup_proxy"][2]
    print("CHECK clicks: the %.1f mm groove squeezes %.2f mm through the %.2f mm mouth into the %.2f mm pocket, %.2f mm "
          "loose there, which keeps %.0f degrees of its rim" % (gd, gd - mouth, mouth, dp, dp - gd,
                                                              360 - 2 * math.degrees(math.asin(mouth / dp))))
    (x0, y0, _), (x1, y1, _) = P["cup_keys"]
    d = math.hypot(x1 - x0, y1 - y0)
    print("CHECK cups %.1f mm apart, %.1f mm between the rims of %.0f mm cups" % (d, d - P["cup_proxy"][0], P["cup_proxy"][0]))
    holes = Part.makeCompound(cup_keyholes(zb))
    zr = P["pcb_bottom_z"] - P["cover_relief"]
    rs = cup_roofs(zr)
    roof = rs[0].fuse(rs[1:]).common(box(-50, -50, zr - P["cup_roof"][0], 100, 150, zr))
    print("CHECK roofs over the chambers: %.2f mm thick, %.1f%% solid, %.2f mm under the PCB" % (
        roof.BoundBox.ZLength, 100 * cover.common(roof).Volume / roof.Volume, P["cover_relief"]))
    roofs = rs[0].fuse(rs[1:])
    print("CHECK roofs to the PCB's pegs and pins %.2f mm" % min(
        roofs.distToShape(zcyl(x, y, d, zr - 2, zr + 1))[0] for x, y, d in P["cup_keepout"]))
    _, wall, clear = P["cup_roof"]
    chambers = [stadium(k, P["cup_entry_d"] / 2, zr - 2, zr) for k in P["cup_keys"]]
    print("CHECK roof bridges land on a %.1f mm wall, %.2f mm at its thinnest, beside a peg or pin" % (wall, min([wall] + [
        ch.distToShape(zcyl(x, y, d + 2 * clear, zr - 2, zr))[0] for ch in chambers for x, y, d in P["cup_keepout"]])))
    print("CHECK keyholes to the screw counterbores %.2f mm" % min(
        holes.distToShape(zcyl(x, y, P["cup_counterbore_d"], zb - 1, zb + P["cup_cover_extra"]))[0]
        for x, y in P["screw_axes"]))
    keys = [cup_key(k) for k in P["cup_keys"]]
    moves = [("up", V(0, 2, 0)), ("down", V(0, -2, 0)), ("left", V(-2, 0, 0)), ("right", V(2, 0, 0))]
    moves += [("along slot %d" % (i + 1), u * 2) for i, (_, u, _) in enumerate(keys)]
    for name, mv in moves:
        moved = cover.translated(mv)
        stuck = ["%d (%.0f mm3)" % (i + 1, v) for i, v in enumerate(c.common(moved).Volume for c in cups)
                 if v > rest[i] + 1.0]
        print("CHECK case pushed 2 mm %s on its cups: %s" % (
            name, "blocked by cup " + ", ".join(stuck) if stuck else "slides off along the slots"))
    # Twisting it about the point where the slots' normals cross starts both
    # cups along their slots at once. The straight slots have to stop it.
    (c1, u1, _), (c2, u2, _) = keys
    det = u1.x * u2.y - u1.y * u2.x
    if abs(det) > 1e-6:
        t = ((c2.x - c1.x) * u2.x + (c2.y - c1.y) * u2.y) / det
        pivot = c1 + V(-u1.y, u1.x, 0) * t
        for sgn in (1, -1):
            hit = None
            for a in range(2, 31, 2):
                moved = cover.copy()
                moved.rotate(pivot, V(0, 0, 1), sgn * a)
                stuck = [i + 1 for i, c in enumerate(cups) if c.common(moved).Volume > rest[i] + 1.0]
                if stuck:
                    hit = (a, stuck)
                    break
            print("CHECK case twisted %s about (%.1f, %.1f): %s" % (
                "anticlockwise" if sgn > 0 else "clockwise", pivot.x, pivot.y,
                "blocked by cup %s at %d deg" % (", ".join(map(str, hit[1])), hit[0]) if hit else "comes off"))


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
    """Tongues on the cap's rim along the two long sides, centred in grooves
    in the housing; they follow the sides' curve and locate the cap before the
    screws go in. The end walls are too thin beside the jack and USB-C for one."""
    a, w, h = P["groove"]
    e = 0.0
    if not groove:
        w, h, e = P["tongue"]
        a += (P["groove"][1] - w) / 2
    ya, yb = P["groove_y"]
    zs = P["seam_z"]
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
    """The original button is smaller and off to one side of S2, on an offset
    stack. Fill its slot and clear its tray and stack, then cut the U slot with
    the pad over S2, and stand a U of walls 0.05 outside it, fences along the
    two channels and an end wall behind the root, down to a floor that stops
    the bar 2 mm down. A straight post under the pad presses S2."""
    zu, zt = P["plate_z"], P["top_z"]
    px, py, pr = P["button_pad"]
    xr, bw = P["button_bar"]
    x1, t, f0, f1 = P["button_tray"]
    w = P["button_slot_w"]
    old = [s for s in H.slice(V(0, 0, 1), zt - 0.2)
           if s.BoundBox.XLength < 30 and s.BoundBox.isInside(V(25, 68.725, zt - 0.2))]
    assert len(old) == 1
    fill = ext(offset_face(Part.Face(old[0]), 0.1).OuterWire, zu, zt)
    # Original walls x 13.35-29.95, y 60.5-72.23, and their floor; the post and stack.
    cx0, cy0, cx1, cy1 = P["button_clear"]
    clear = [box(13.0, 60.0, f0 - 0.1, 29.95, 72.6, zu), box(cx0, cy0, 0.0, cx1, cy1, zu)]
    g = 0.05
    xe = xr - w / 2 - g - t  # end wall behind the round slot ends
    yb, yt = py - bw / 2 - w - g, py + bw / 2 + w + g  # fence faces on the slot side
    u = rect(xe, yb - t, x1, yb).fuse([rect(xe, yt, x1, yt + t), rect(xe, yb - t, xe + t, yt + t)])
    walls = ext(merge_faces(u).OuterWire, f1 - 0.05, zu + 0.25)
    floor = box(xe, yb - t, f0, x1 + 0.15, yt + t, f1)
    d, z0 = P["button_post"]
    post = zcyl(px, py, d, z0, zu + 0.3)
    slot = ext(button_slot_face(zu).OuterWire, zu, zt + 1)
    return clear, [fill, floor, walls, post], slot


def button_inlay(grow=0.05):
    """Blue on the round pad only, grown a hair into the slot so the cut never
    lands on its walls; the bar stays black."""
    px, py, pr = P["button_pad"]
    z0, z1 = P["inlay_z"]
    return disc(px, py, pr + grow, z0).extrude(V(0, 0, z1 + 1 - z0))


def logo_inlay(logo):
    """The original logo inlay (its top faces at the top face), scaled about
    the top left corner of its bounding box and moved to P["logo"], at the
    same depth."""
    s, (x, y) = P["logo"]
    zt = P["top_z"]
    x += side_inset(zt)  # stays the same distance from the left side when the sides lean
    tops = [f.copy() for f in logo.Faces if f.normalAt(0, 0).z > 0.99 and abs(f.CenterOfMass.z - zt) < 1e-3]
    bb = Part.makeCompound(tops).BoundBox
    depth = zt - logo.BoundBox.ZMin
    solids = []
    for f in tops:
        f.scale(s, V(bb.XMin, bb.YMax, zt))
        f.translate(V(x - bb.XMin, y - bb.YMax, 0))
        solids.append(f.extrude(V(0, 0, -depth)))
    return Part.makeCompound(solids)


def screen_clips():
    """A beam either side of the OLED board, bridged between two posts that
    hang from the plate at the board's ends; tabs stop the board along Y. The
    right beam's post at the button end stands beside the board, so the
    button's slot stays clear. A lip in the middle of each beam catches the
    board's back on a face clip_lip[3] degrees from flat, near self-locking,
    that would lift the board clip_lip[2] past its seat, so the beams stay
    sprung and press the glass onto the plate. Printed top face down, the
    beams are bridges and the lips short overhangs. A rib under the plate keys
    the module the right way round."""
    bx0, by0, bx1, by1, zb = P["oled_board"]
    g, s = P["clip_gap"], P["clip_post"]
    t, z0, z1 = P["clip_beam"]
    reach, ll, dz, ang = P["clip_lip"]
    k = math.tan(math.radians(ang))
    zp = P["plate_z"] + 0.33  # into the plate
    zr = zb + dz + g * k  # catch face at the beam
    za = zr - reach * k  # its inner edge
    ym = (by0 + by1) / 2
    ya, yb = by0 - g, by1 + g  # post faces toward the board
    parts = []
    for xi, out in ((bx0 - g, -1), (bx1 + g, 1)):  # beam inner face, outward direction
        xs = lambda d: xi + out * d  # d: distance outward from the inner face
        right = out > 0
        y_end = yb if right else yb + s  # the right beam ends at its post beside the board
        xlo, xhi = sorted((xs(0), xs(t)))
        parts.append(box(xlo, ya - s, z0, xhi, y_end, z1))
        plo, phi = sorted((xs(0), xs(s)))  # posts, outside the beam line
        tlo, thi = sorted((xs(0), xs(-s)))  # end tabs, over the board corners
        for y0, y1 in ((ya - s, ya), (y_end - s, y_end)):
            parts.append(box(plo, y0, z0, phi, y1, zp))
        for y0, y1 in ((ya - 1.0, ya), (yb, yb + 1.0)):
            x1 = min(thi, P["clip_tab_right"]) if right and y0 > ym else thi
            parts.append(box(tlo, y0, zb, x1, y1, zp))  # down to the board back, clear of the battery
        prof = [V(xs(0.01), ym - ll / 2, zr), V(xs(-reach), ym - ll / 2, za), V(xs(0.01), ym - ll / 2, za - reach)]
        parts.append(Part.Face(Part.makePolygon(prof + prof[:1])).extrude(V(0, ll, 0)))
    kx0, ky0, kx1, ky1, kz = P["oled_key"]
    parts.append(box(kx0, ky0, kz, kx1, ky1, zp))
    return parts[0].fuse(parts[1:]).removeSplitter()


def build_all(doc):
    logo0 = doc.getObject("Body").Shape
    H = doc.getObject("Part__Feature001").Shape.fuse(logo0).removeSplitter()  # fill the original logo pocket
    board = doc.getObject("BoardRev4").Shape

    housing, pcb = build_housing(H, board)
    slider = build_slider()
    cover = build_cover(pcb)
    cup_cover = build_cover(pcb, P["cup_cover_extra"])
    cover = solid(cover.fuse(tongue()).removeSplitter())
    cup_cover = solid(cup_cover.fuse(tongue()).removeSplitter())
    button = solid(housing.common(button_inlay()).removeSplitter())
    housing = solid(housing.cut(button_inlay()).removeSplitter())
    logo = logo_inlay(logo0)
    housing = solid(housing.cut(logo).removeSplitter())
    housing = solid(housing.cut(tongue(groove=True)).removeSplitter())
    print("housing", housing.isValid(), len(housing.Solids), round(housing.Volume, 1))
    print("slider", slider.isValid(), len(slider.Solids), round(slider.Volume, 1))
    print("cover", cover.isValid(), len(cover.Solids), round(cover.Volume, 1))
    print("cup cover", cup_cover.isValid(), len(cup_cover.Solids), round(cup_cover.Volume, 1))

    return dict(
        housing=housing,
        slider=slider,
        cover=cover,
        cup_cover=cup_cover,
        cups=[suction_cup(x, y, cup_cover_rear()) for x, y, _ in P["cup_keys"]],
        s1=build_s1(doc.getObject("Part__Feature002").Shape),
        button=button,
        logo=logo,
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
    )
