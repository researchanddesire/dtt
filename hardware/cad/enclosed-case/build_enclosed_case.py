"""Build the enclosed DTT case from ../DTT.FCStd.

The housing is built from scratch as a short ordered list of features (see
build_housing): the outer shape, tapered toward the jack or stepped to follow
the PCB, less the inside, which is the PCB's outline up to the plate, so the
PCB sits in a pocket down to its back face and the rear cover is a flat cap.
A sliding switch cover drives S1. The original four PCB screws pass up through
the cap and PCB into the housing bosses, with their heads sunk flush in the
cap. Only the parts inside (PCB, screen, sensor, battery, diffuser, logo) come
from DTT.FCStd; nothing of the original housing is used.

Run with FreeCAD 1.1+ (GUI under xvfb keeps the colours in the saved file):
    xvfb-run -a freecad make_assembly.FCMacro
    DTT_CASE=stepped xvfb-run -a freecad make_assembly.FCMacro
Coordinates follow DTT.FCStd: X = pcb_x - 127.583333, Y = 151.9861 - pcb_y,
PCB top at Z = -3.5, PCB bottom at Z = -5.1.
"""

import math
import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "DTT.FCStd")
STEPPED = os.environ.get("DTT_CASE") == "stepped"  # the stepped version, built into stepped/
OUT = os.path.join(HERE, "stepped") if STEPPED else HERE
OUT_FCSTD = os.path.join(OUT, "DTT-Enclosed-Stepped.FCStd" if STEPPED else "DTT-Enclosed.FCStd")
OUT_STEP = OUT_FCSTD[:-6] + ".step"
PARTS = os.path.join(OUT, "parts")

V = App.Vector

PARAMS = {
    # Stack (verified from DTT.FCStd and the KiCad board).
    "pcb_top_z": -3.5,
    "pcb_bottom_z": -5.1,
    "seam_z": -5.1,  # housing to rear cover: the PCB sits in a pocket in the housing and the cover is a flat cap
    "pcb_usb_y": 92.98,  # the PCB's USB-C edge; the receptacle's face is 0.2 behind it
    "usb_end_gap": 0.1,  # pocket to that edge
    "screw_axes": [(3.0, 76.0), (39.0, 76.0), (3.3, 27.5), (38.7, 27.5)],
    # Outer shape: full width at the USB-C end, then the sides curve in toward
    # the jack end on two large arcs ("taper"), or step in with the PCB's
    # three widths ("conformal").
    "outline": "conformal" if STEPPED else "taper",
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
    # Round along the top edge, all the way round: a chamfer on the top edge
    # and a fillet of top_round on the chamfer's lower edge, so the round stops
    # 45 degrees from upright and a straight face carries on at that slope to
    # the top face. It prints top face down without support. Under it the walls
    # are kept round_wall thick from inside. With leaning sides the round is
    # lofted instead, its corners tightening toward corner_min_r as it comes
    # in. The conformal outline's 1.5 mm step corners keep a plain edge_fillet
    # and the original sloped jack end.
    "top_round": 5.0,
    "round_stop": 45.0,
    "corner_min_r": 1.0,
    "edge_fillet": 1.2,  # conformal outline only
    "bottom_chamfer": 0.8,
    # Sloped jack end of the original housing (conformal outline only): z = z0 + k * (y - y0).
    "slope": (9.774, 1.2, 1.368),
    "pcb_edge_gap": 0.3,  # PCB edge to the wall of the inside, all the way up
    "pocket_corner_r": 1.0,  # the inside's corners at the USB-C end
    "round_wall": 1.2,  # the inside stays this far in from the outer faces, so the top round keeps a wall
    "plate_z": 12.57,  # top plate underside
    # A boss round each PCB screw, run out sideways into the nearest side wall.
    "boss": (6.5, 6.5),  # diameter, pilot hole end z (the screws end at 4.6)
    # Pilot holes as in the original bosses: 2.65 with four ribs reaching in
    # to 2.30 for the screw's thread to form in, plain below the ribs, with a
    # cone lead-in.
    "pilot": (2.65, 2.30, -0.33),  # hole, across the ribs, z where the ribs start
    "pilot_rib": (0.30, 0.35),  # rib width between the centres of its round sides, their radius
    "pilot_lead": (3.85, -3.33, -1.33),  # cone diameter at that z, z where it meets the hole
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
    # S1 (JS102011JAQN). Its lever as the KiCad F.Fab drawing has it, taken as
    # the jack end of its 2.0 travel, the tip 2.05 off the PCB's edge.
    "act_y": 82.39,  # lever centre as drawn (pcb y 69.59)
    "act_w": 1.5,
    "act_tip_x": 44.97,
    "act_z": (-1.9, -0.3),
    "travel": 2.0,
    # Switch cover: a plate with a ridged grip in the middle of one face and a
    # socket for the lever in the other, centred on the lever, so it is the
    # same either way up and either way round. The plate covers the window by
    # 0.7 at each end of the travel.
    "switch_cover": (12.4, 4.8, 1.1),  # the plate: length, height, thickness
    "switch_grip": (5.0, 4.0, 0.4, 0.6),  # length, height, how far it stands proud of the case side, edge radius
    "switch_ridges": (1.5, 0.6, 0.35),  # three grooves across the grip: pitch, width, depth
    "switch_socket": (1.9, 2.4, 0.4),  # along the travel (0.2 each side of the lever), up (0.4 each side), past the lever's tip
    "pcb_edge_x": 42.92,
    # The plate runs in a channel in the housing, open at the seam so that it
    # goes in with the PCB: 0.2 a side, 0.3 above and at each end of its
    # travel. The grip comes out through a window as high as the plate; a tab
    # on the cap closes the window under it and carries the plate's lower
    # edge.
    "slider_clear": (0.2, 0.3),  # each face; above, below and at the ends
    # 45 degree lead-ins on the channel's mouth bring the plate in as the PCB
    # goes in, from hard against S1: on the outer wall at the seam, and under
    # each inner wall. The outer one stops short of the channel's USB-C end,
    # where the case's corner thins the wall. The USB-end wall's end has the
    # same lead-in, for a plate that leans in beside S1.
    "channel_lead": (0.4, 0.6, 2.0),  # outer, inner, the outer one's distance from the USB-C end
    # Inner walls of the channel: the boss beside S1 at its jack end, a wall
    # from 0.3 above the PCB at its USB-C end (S1 ends 0.5 before it), and
    # between them a wall that hangs from the plate to 0.3 above S1.
    "track": (1.5, 0.5, 88.9),  # wall thickness, bottom z over S1, where the USB-end wall starts
    # Connector openings. The jack's hole is a plain round hole in the housing:
    # the PCB goes in jack end first, tilted, nose into the hole.
    "jack_axis": (20.9, -0.7),
    "jack_d": 6.2,
    # USB-C (J1, HRO TYPE-C-31-M-12, from the KiCad board and its drawing): the
    # receptacle stands 3.26 on the PCB, its opening's centre 1.67 up. A plug
    # is fully in when its overmould is about 0.45 from the receptacle's face,
    # so nothing may stop the overmould in front of the PCB's edge. The recess
    # for the overmould goes right back to that edge, as the original
    # housing's end face did. Above the PCB a surround closes the recess, with
    # a notch round the receptacle, as in the original housing.
    "usb_center": (21.0, -1.83),  # the port's axis
    "usb_shell": (8.94, 3.26),  # the receptacle's shell: width, height off the PCB
    "usb_model_shift": (0.05, -0.19, 0.33),  # DTT.FCStd draws the receptacle sunk into the PCB and flush with its edge
    "usb_notch": (0.4, 0.3, 1.1),  # notch round the shell: clearance beside (the PCB has 0.3 of play) and above it, 45 degree top corners
    "usb_surround": (8.0, 1.0, 0.3),  # half-width, thickness back from the PCB's edge, clearance above the PCB
    # A rounded rectangle round the port: 0.25 above and below the largest
    # overmould USB allows (12.35 x 6.5) and 0.5 beside it, as the PCB's play
    # in its pocket can put the port 0.4 to one side. Its corners take boxy
    # overmoulds with corners of 1.0 or more. Its lower edge is in the cap.
    "usb_recess": (13.4, 7.0, 1.62, 1.5),  # width, height, depth (back to the PCB's edge), corner radius
    # The boss beside S1 is cut back from the switch's jack end, as in the
    # original housing, so the PCB seats when it sits toward the jack end of
    # its pocket.
    "s1_relief": (78.84, 0.5),  # the boss's face toward S1 (0.6 from the switch), up to this z
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
    "button_post": (4.0, 1.0),  # diameter and bottom z: 1.2 over S2's plunger (top at -0.2), as the original post
    # Under the button, a U of walls round the slot holds a floor that stops
    # the bar 2 mm down, 1.6 mm clear of the OLED board's end.
    "button_tray": (32.7, 0.8, 9.57, 10.57),  # fences' end x, wall thickness, floor bottom and top z
    # The R+D logo is tucked into the top left corner of the flat top, 1 mm in
    # from its edge: scale, then where the top left corner of its bounding box
    # goes (from 2.44, 90.29).
    "logo": (0.78, (-0.07, 90.67)),
    "inlay_z": (13.52, 14.17),  # same depth as the logo inlay
    # The screen's viewport, on its active area (21.74 x 10.86, nearer the
    # header end of the glass than the old window), with a 45 degree edge at
    # the top face.
    "viewport": (21.0, 44.0, 23.4, 12.4, 0.5, 0.5),  # centre x, y, width, height, corner radius, chamfer
    # The screen module (GME12864-11, 0.96 in OLED): its face sits flat on the
    # plate and its board's back is oled_stack below. The header's four solder
    # points stand on the board's front, nearly as tall as the screen, so the
    # plate has a pocket over them.
    "oled_board": (7.25, 31.64, 34.75, 59.44),  # x0, y0, x1, y1
    "oled_stack": 3.0,  # screen face to the board's back
    "oled_pins": (21.28, 33.92, 7.62, 2.75),  # solder points: row centre x, y, row length, tips above the board's back (1.6 past a 1.15 board)
    "pin_pocket": (1.9, 1.5, 0.6),  # the pocket: past the row's ends, either side of it, depth into the plate
    # Print-in-place snap clips for the OLED module: a spring strip either side
    # of its board, bridged between blocks at its ends that run out into the
    # side wall, with a lip that catches the board's back and holds the screen
    # on the plate. Behind each strip a wall fills out to the side wall, past a
    # slot that lets the strip bend out and stops it bending too far.
    "clip_gap": 0.2,  # strips and end tabs to the board edges
    "clip_beam": (1.2, 8.2, 11.07),  # strip thickness, bottom z, top z (1.5 under the plate, so the bridge can sag)
    "clip_post": 2.0,  # end block length; the end tabs reach this far over the board corners
    "clip_lip": (0.9, 8.0, 0.2, 20.0),  # reach from the strip, length, catch face clear of the board's back, catch face from flat (degrees)
    "clip_backing": 0.95,  # slot behind each strip: it bends 0.7 to let the board in, and the wall behind stops it
    # Distance sensor (GP2Y0A51SK0F), moved left by sensor_shift, which centres
    # its lenses on the case. It seats as in the original housing: its optical
    # case in a window through the plate and a pad under it, and the two
    # mounting ears of its case each against a post, with a pin in the ear's
    # hole.
    "sensor_shift": -1.7,
    "sensor_case": (13.10, 9.617, 32.30, 17.617, 3.67),  # optical case before the shift: x0, y0, x1, y1; top z of its PCB
    "sensor_fit": (0.28, 0.1),  # window round the case, a side, in x and y
    "sensor_pad": (2.9, 1.5, 10.07, 0.6),  # pad past the case in x and y, its underside z; the window's 45 degree lead-in
    "sensor_holes": ((11.0, 16.917, -1, 1), (34.4, 10.317, 1, -1)),  # the ears' holes before the shift; which way is outward in x and y
    "sensor_post": (3.3, 3.77, 1.8, 0.4, 0.5),  # post diameter, shoulder z (0.1 off the ears); pin diameter, straight length, 45 degree tip
    # Each post's root flares into the plate on its outward side: a fillet of
    # this radius from this z, kept to a block reaching this far out from the
    # post's axis, with this fillet where the block meets the post.
    "sensor_flare": (7.67, 3.0, 4.0, 1.0),
    # Flexure snaps that hook under the sensor's PCB, as in the original
    # housing: one at each end, moved with the sensor, and one on its edge
    # toward the jack, left where it was so it clears the jack. Each: the way
    # its hook points, the beam's inner face (x before the shift, or y), the
    # middle of its width, its thickness and width, and how its root flares
    # out 1.5 into the plate, as in the original: 0 not at all, 1 on both
    # sides, 2 on both sides and its back.
    "sensor_snaps": (("+x", 8.6, 12.942, 2.0, 4.0, 2),
                     ("-x", 36.9, 13.924, 1.6, 2.398, 0),
                     ("+y", 7.617, 27.6, 2.0, 4.0, 1)),
    # Battery tray, as in the original housing: two rings under the plate
    # that the cell slides into from the screen side, up to a flat stop on
    # the end wall, level with the USB-C surround.
    "battery_tray": ((73.2, 75.7), (83.95, 88.95)),  # each ring's y0, y1
    "battery_ring": (5.7, 30.7, 0.07),  # the rings' outer x0, x1 and their underside
    "battery_opening": (8.2, 28.2, 1.07, 8.57),  # x0, x1, z0, z1: 20 x 7.5 for the 702035 cell
    "battery_stop": (91.98, 2.5),  # y of its face, bottom z
    "battery_model_shift": (2.03, -0.85),  # y, z: moves DTT.FCStd's cell to 0.25 off the stop and the middle of its rings
}
P = PARAMS


def ext(wire, z0, z1):
    w = wire.copy()
    w.translate(V(0, 0, z0 - w.BoundBox.ZMin))
    return Part.Face(w).extrude(V(0, 0, z1 - z0))


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rounded_rect(x0, y0, x1, y1, r, z=0.0):
    """Rectangle with corners of radius r; with r at half the height (or
    width) its ends are full half circles."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    k = r * (1 - math.sqrt(0.5))
    sides = [(V(x0 + r, y0, z), V(x1 - r, y0, z)), (V(x1, y0 + r, z), V(x1, y1 - r, z)),
             (V(x1 - r, y1, z), V(x0 + r, y1, z)), (V(x0, y1 - r, z), V(x0, y0 + r, z))]
    arcs = [(V(x1 - r, y0, z), V(x1 - k, y0 + k, z), V(x1, y0 + r, z)),
            (V(x1, y1 - r, z), V(x1 - k, y1 - k, z), V(x1 - r, y1, z)),
            (V(x0 + r, y1, z), V(x0 + k, y1 - k, z), V(x0, y1 - r, z)),
            (V(x0, y0 + r, z), V(x0 + k, y0 + k, z), V(x0 + r, y0, z))]
    edges = []
    for (a, b), arc in zip(sides, arcs):
        if (b - a).Length > 1e-6:  # no zero-length sides
            edges.append(Part.LineSegment(a, b))
        edges.append(Part.Arc(*arc))
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
    """The PCB's outline at z 0, rebuilt with true arcs. The board's model
    draws its rounded corners as runs of short facets, which every wall
    offset from it would copy as slivers of face. Its straight sides (all at
    multiples of 45 degrees) are kept, and each run of facets between two of
    them becomes the tangent arc it stands for."""
    faces = [f for f in board.Faces if abs(f.normalAt(0, 0).z) > 0.9 and f.CenterOfMass.z < -5.0]
    pts = [V(v.X, v.Y, 0) for v in faces[0].OuterWire.OrderedVertexes]
    n = len(pts)

    def straight(a, b):
        d = b - a
        ang = math.degrees(math.atan2(d.y, d.x)) % 45.0
        return d.Length > 0.3 and min(ang, 45.0 - ang) < 0.5

    sides = [(pts[i], pts[(i + 1) % n]) for i in range(n) if straight(pts[i], pts[(i + 1) % n])]
    corners, radii = [], []
    for (a0, a1), (b0, b1) in zip(sides[-1:] + sides[:-1], sides):
        da, db = a1 - a0, b1 - b0
        den = da.x * db.y - da.y * db.x
        assert abs(den) > 1e-9, "two straight sides in line"
        t = ((b0.x - a0.x) * db.y - (b0.y - a0.y) * db.x) / den
        c = a0 + da * t  # the sharp corner
        turn = math.acos(max(-1.0, min(1.0, da.dot(db) / (da.Length * db.Length))))
        corners.append((c.x, c.y))
        radii.append((c - a1).Length / math.tan(turn / 2))
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1]))
    if area < 0:  # anticlockwise, so faces made from it face +Z
        corners, radii = corners[::-1], radii[::-1]
    return filleted_polygon(corners, radii).OuterWire


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


def rounded_envelope(z0, t=0.0):
    """The case from z0 to the top face with its top round, or the surface t
    inside it: the plan outline (t in) extruded, a chamfer round its top edge
    and a fillet on the chamfer's lower edge."""
    r, zt = top_round() - t, P["top_z"] - t
    f = plan_outline(z0) if t <= 0 else Part.Face(plan_outline(z0).makeOffset2D(-t))
    s = f.extrude(V(0, 0, zt - z0))
    c = r * (2 - math.sqrt(2))
    s = s.makeChamfer(c, [e for e in s.Edges if e.BoundBox.ZMin > zt - 1e-6])
    low = [e for e in s.Edges if abs(e.BoundBox.ZMin - (zt - c)) < 1e-6 and abs(e.BoundBox.ZMax - (zt - c)) < 1e-6]
    return solid(s.makeFillet(r, low))


def lofted_envelope(z0, t=0.0):
    """The case from z0 to the top face, or the surface t inside it. Upright
    sides with the top round are a plain chamfer and fillet. Leaning sides are
    lofted: upright, then a loft through sections that lean in and round over
    the top, and a ruled one up the straight face above the round (smooth if
    the sides lean, which curves it)."""
    if top_round() > t and P["lean"][0] <= 0 and abs(P["round_stop"] - 45.0) < 1e-9:
        return rounded_envelope(z0, t)
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


def above_slope(t=0.0):
    """Everything above the jack-end slope, or above the surface t inside it.
    The slope is the original housing's, moved out with the end wall (the
    original's is at y = 1)."""
    z0, y0, k = P["slope"]
    y0 -= 1.0 - P["outer"][1] - t * math.hypot(1.0, k) / k
    pts = [(y0 + (-20 - z0) / k, -20), (y0 + (40 - z0) / k, 40), (-40, 40), (-40, -20)]
    w = Part.makePolygon([V(-20, y, z) for (y, z) in pts] + [V(-20, pts[0][0], pts[0][1])])
    return Part.Face(w).extrude(V(80, 0, 0))


def outer_upper():
    """The outer form above the seam. The top round runs round the jack end
    too; without it the top edges get a plain fillet and the jack end keeps
    the original housing's sloped end, thickened."""
    zs, zt = P["seam_z"], P["top_z"]
    r = P["edge_fillet"]
    e = lofted_envelope(zs)
    if top_round() > 0:
        return e
    e = e.makeFillet(r, [ed for ed in e.Edges if ed.BoundBox.ZMin > zt - 1e-6])
    e = e.cut(above_slope())
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


def usb_pocket_end():
    return P["pcb_usb_y"] + P["usb_end_gap"]


def pcb_pocket(pcb):
    """The PCB's outline pcb_edge_gap out, but only usb_end_gap past its USB-C
    edge, and squared off at that end past the PCB's round corners (to
    pocket_corner_r), so the switch channel beside S1 runs into it instead of
    leaving a thin wall between them: the inside of the housing in plan, and
    the relief in the cap."""
    f = Part.Face(pcb.makeOffset2D(P["pcb_edge_gap"]))
    bb, ye = f.BoundBox, usb_pocket_end()
    f = merge_faces(f.fuse(rounded_rect(bb.XMin, ye - 8.0, bb.XMax, ye, P["pocket_corner_r"])))
    return f.cut(rect(-50, ye, 100, 200)).Faces[0]


# The housing's features, in build order. Solids kept inside run out past the
# walls; they are trimmed to the inside, so they merge into the walls and
# never reach the outer faces.

def inside(pcb, diffuser):
    """The inside: the PCB pocket's outline from under the seam up to the
    plate, kept round_wall in from the outer faces (under the top round its
    edges follow the round in, and the conformal outline's jack end follows
    its slope), with a pocket in the plate for the screen header's solder
    points and the opening under the diffuser."""
    zs, zp = P["seam_z"], P["plate_z"]
    pocket = ext(pcb_pocket(pcb).OuterWire, zs - 1, zp).common(lofted_envelope(zs - 1, P["round_wall"]))
    if top_round() <= 0:
        pocket = pocket.cut(above_slope(P["round_wall"]))
    cx, cy, row, _ = P["oled_pins"]
    ex, ey, depth = P["pin_pocket"]
    pins = box(cx - row / 2 - ex, cy - ey, zp - 0.1, cx + row / 2 + ex, cy + ey, zp + depth)
    zd = diffuser.BoundBox.ZMin
    base = [f for f in diffuser.Faces if f.normalAt(0, 0).z < -0.99 and abs(f.CenterOfMass.z - zd) < 1e-6]
    light = ext(base[0].OuterWire, zp - 0.1, zd)
    return solid(pocket.fuse([pins, light]).removeSplitter())


def screw_bosses():
    """A boss round each PCB screw, from the PCB's top up into the plate, run
    out sideways into the nearest side wall."""
    d = P["boss"][0]
    z0, z1 = P["pcb_top_z"], P["plate_z"] + 0.5
    x0, _, x1, _ = P["outer"]
    parts = []
    for x, y in P["screw_axes"]:
        xw = x0 - 5 if x < (x0 + x1) / 2 else x1 + 5
        parts += [zcyl(x, y, d, z0, z1), box(min(x, xw), y - d / 2, z0, max(x, xw), y + d / 2, z1)]
    return parts[0].fuse(parts[1:]).removeSplitter()


def pilot_section(x, y, z):
    """A pilot hole's section where it has ribs, as in the original bosses:
    each of the four ribs is an arc round the axis between two round sides,
    which meet it tangentially."""
    d, dr, _ = P["pilot"]
    w, rs = P["pilot_rib"]
    R, r = d / 2, dr / 2
    rc = r + rs  # the round sides' centres
    ac = math.atan2(w / 2, math.sqrt(rc * rc - w * w / 4))  # their angle off the rib's middle
    ae = ac + math.acos((R * R + rc * rc - rs * rs) / (2 * R * rc))  # where they meet the hole

    def pt(rad, a):
        return V(x + rad * math.cos(a), y + rad * math.sin(a), z)

    def side(k, sgn):
        a = k * math.pi / 2 + sgn * ac
        c, t, e = pt(rc, a), pt(r, a), pt(R, k * math.pi / 2 + sgn * ae)
        at, ae_ = math.atan2(t.y - c.y, t.x - c.x), math.atan2(e.y - c.y, e.x - c.x)
        am = at + math.remainder(ae_ - at, 2 * math.pi) / 2
        return t, V(c.x + rs * math.cos(am), c.y + rs * math.sin(am), z), e

    edges = []
    for k in range(4):
        tm, mm, em = side(k, -1)
        tp, mp, ep = side(k, 1)
        en = side(k + 1, -1)
        a = k * math.pi / 2
        edges += [Part.Arc(tm, pt(r, a), tp).toShape(), Part.Arc(tp, mp, ep).toShape(),
                  Part.Arc(ep, pt(R, a + math.pi / 4), en[2]).toShape(), Part.Arc(en[2], en[1], en[0]).toShape()]
    return Part.Face(Part.Wire(edges))


def screw_pilots():
    """Pilot holes up the bosses for the self-tapping screws, as in the
    original bosses: ribbed, plain below the ribs, and a cone lead-in."""
    d, _, zr = P["pilot"]
    dl, zl, zh = P["pilot_lead"]
    z0, ze = P["pcb_top_z"] - 1, P["boss"][1]
    rl = d / 2 + (dl - d) / 2 * (zh - z0) / (zh - zl)  # the cone carried on down to z0
    out = []
    for x, y in P["screw_axes"]:
        out += [pilot_section(x, y, zr).extrude(V(0, 0, ze - zr)), zcyl(x, y, d, z0, zr),
                Part.makeCone(rl, d / 2, zh - z0, V(x, y, z0))]
    return out


def sensor_window():
    """x0, y0, x1, y1 of the window round the sensor's optical case, moved by sensor_shift."""
    x0, y0, x1, y1, _ = P["sensor_case"]
    fx, fy = P["sensor_fit"]
    s = P["sensor_shift"]
    return x0 + s - fx, y0 - fy, x1 + s + fx, y1 + fy


def sensor_pad():
    """A pad under the plate round the sensor's window, as in the original
    housing, so the window grips the optical case over 3.5 mm above a 45
    degree lead-in. The window itself is cut afterwards."""
    x0, y0, x1, y1 = P["sensor_case"][:4]
    px, py, zp, c = P["sensor_pad"]
    s = P["sensor_shift"]
    wx0, wy0, wx1, wy1 = sensor_window()
    lead = Part.makeLoft([rect(wx0 - c - 1, wy0 - c - 1, wx1 + c + 1, wy1 + c + 1, zp - 1).OuterWire,
                          rect(wx0, wy0, wx1, wy1, zp + c).OuterWire], True, True)
    return box(x0 + s - px, y0 - py, zp, x1 + s + px, y1 + py, P["plate_z"] + 0.5).cut(lead)


def sensor_posts(ystop):
    """The sensor's seat, as in the original housing: a post from the plate
    down onto each mounting ear of the sensor's case, ending in a pin that
    enters the ear's hole. Each post's root flares into the plate on its
    outward side; a flare stops at ystop, the diffuser's edge."""
    d, zs, dp, lp, lc = P["sensor_post"]
    zf, rf, reach, rc = P["sensor_flare"]
    z1 = P["plate_z"] + 0.5
    s = P["sensor_shift"]
    r = d / 2
    m = rf * (1 - math.sqrt(0.5))
    far = reach * 1.5 + 1
    posts = []
    for x, y, sx, sy in P["sensor_holes"]:
        x += s
        post = zcyl(x, y, d, zs, z1).fuse([zcyl(x, y, dp, zs - lp, zs),
                                           Part.makeCone(dp / 2 - lc, dp / 2, lc, V(x, y, zs - lp - lc))])
        # the flare: a fillet of radius rf round the post, from zf up
        pts = [V(x, y, zf), V(x + r, y, zf), V(x + r + rf, y, zf + rf), V(x + far, y, zf + rf), V(x + far, y, z1), V(x, y, z1)]
        prof = [Part.LineSegment(pts[0], pts[1]), Part.Arc(pts[1], V(x + r + m, y, zf + rf - m), pts[2])]
        prof += [Part.LineSegment(pts[i], pts[(i + 1) % 6]) for i in range(2, 6)]
        flare = Part.Face(Part.Wire([e.toShape() for e in prof])).revolve(V(x, y, 0), V(0, 0, 1), 360)
        # kept to a block on the post's outward side, filleted into the post
        xa, xb = sorted((x, x + sx * reach))
        ya, yb = sorted((y - sy * r, y + sy * reach))
        dy = math.sqrt((r + rc) ** 2 - rc ** 2)
        cx, cy = x - sx * rc, y + sy * dy
        web = Part.Face(Part.makePolygon([V(x, y, zf), V(cx, cy, zf), V(x, cy, zf), V(x, y, zf)])).cut(disc(cx, cy, rc, zf))
        block = box(xa, ya, zf, xb, min(yb, ystop), z1).fuse(web.Faces[0].extrude(V(0, 0, z1 - zf)))
        posts.append(post.fuse(block.common(flare)))
    return posts[0].fuse(posts[1:]).removeSplitter()


def sensor_cuts():
    """The sensor's window, through the pad and the plate."""
    x0, y0, x1, y1 = sensor_window()
    return [box(x0, y0, P["sensor_pad"][2] - 1, x1, y1, P["top_z"] + 1)]


def battery_tray():
    """The original housing's two battery rings, hung from the plate, and a
    stop for the cell's USB-C end on the end wall."""
    rx0, rx1, rz = P["battery_ring"]
    x0, x1, z0, z1 = P["battery_opening"]
    ys, zb = P["battery_stop"]
    zp = P["plate_z"] + 0.5
    rings = [box(rx0, ya, rz, rx1, yb, zp) for ya, yb in P["battery_tray"]]
    opening = box(x0, P["battery_tray"][0][0] - 1, z0, x1, P["battery_tray"][-1][1] + 1, z1)
    stop = box(x0, ys, zb, x1, P["outer"][3] + 5, zp)
    return rings[0].fuse(rings[1:]).cut(opening).fuse(stop).removeSplitter()


def usb_surround():
    """A wall above the PCB at the USB-C end, back over the PCB's edge, that
    closes the plug recess round the receptacle. It runs up into the battery
    stop and out into the end wall, which its top meets at 45 degrees where it
    stands clear of the stop; the receptacle's notch is cut afterwards."""
    ux, _ = P["usb_center"]
    hw, t, c = P["usb_surround"]
    y0, y1 = P["pcb_usb_y"] - t, P["outer"][3] + 5
    z0, z1 = P["pcb_top_z"] + c, P["battery_stop"][1] + 0.5
    pts = [V(ux - hw, y0, z0), V(ux - hw, y1, z0), V(ux - hw, y1, z1 + y1 - y0), V(ux - hw, y0, z1)]
    return Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(2 * hw, 0, 0))


def button_post():
    """The post under the button's pad, down to just over S2's plunger."""
    px, py, _ = P["button_pad"]
    d, z0 = P["button_post"]
    return zcyl(px, py, d, z0, P["plate_z"] + 0.5)


def switch_track():
    """The switch channel's inner walls, run out into the side wall; the
    channel is cut through them afterwards. Over S1 the wall hangs from the
    plate; past S1's USB-C end it comes down to just above the PCB."""
    g = slider_geom()
    tw, z0, yu = P["track"]
    x0, x1 = g["xin"] - tw, P["outer"][2] + 5
    zp = P["plate_z"] + 0.5
    over = box(x0, g["y0"] - 1, z0, x1, g["y1"] + 1, zp)
    low = box(x0, yu, P["pcb_top_z"] + g["cz"], x1, g["y1"] + 1, zp)
    return over.fuse(low).removeSplitter()


def button_stop():
    """Under the button's bar, a U of walls just outside its slot (a fence
    along each side and an end wall behind its root) holds a floor that stops
    the bar 2 mm down."""
    _, py, _ = P["button_pad"]
    xr, bw = P["button_bar"]
    x1, t, f0, f1 = P["button_tray"]
    w, g = P["button_slot_w"], 0.05
    xe = xr - w / 2 - g - t
    yb, yt = py - bw / 2 - w - g, py + bw / 2 + w + g
    z1 = P["plate_z"] + 0.5
    walls = [box(xe, yb - t, f1 - 0.05, x1, yb, z1), box(xe, yt, f1 - 0.05, x1, yt + t, z1),
             box(xe, yb - t, f1 - 0.05, xe + t, yt + t, z1)]
    return box(xe, yb - t, f0, x1 + 0.15, yt + t, f1).fuse(walls).removeSplitter()


def sensor_snaps():
    """Flexure snaps hanging from the plate that hook under the sensor's PCB,
    as in the original housing. Each beam ends in a hook reaching 1.0 in from
    its inner face: a 45 degree catch 0.1 to 0.3 under the PCB, a flat 0.2, a
    tip, and a 45 degree lead-in, so it prints without support and the PCB
    pushes it aside on the way in."""
    zp = P["sensor_case"][4] - 1.5  # the PCB's underside
    z1, zf = P["plate_z"] + 0.5, P["plate_z"]
    s = P["sensor_shift"]
    snaps = []
    for d, f, m, t, w, flare in P["sensor_snaps"]:
        # the hook's profile across the beam: u from the inner face toward the PCB
        prof = [(-t, z1), (-t, zp - 2.8), (0.2, zp - 2.8), (1.0, zp - 2.0), (1.0, zp - 0.3),
                (0.8, zp - 0.3), (0.0, zp + 0.5), (0.0, z1)]
        sec = Part.Face(Part.makePolygon([V(u, -w / 2, z) for u, z in prof + prof[:1]]))
        snap = sec.extrude(V(0, w, 0))
        if flare == 1:
            r = [(-w / 2, zf - 1.5), (w / 2, zf - 1.5), (w / 2 + 1.5, zf), (w / 2 + 1.5, z1),
                 (-w / 2 - 1.5, z1), (-w / 2 - 1.5, zf)]
            root = Part.Face(Part.makePolygon([V(-t, v, z) for v, z in r + r[:1]]))
            snap = snap.fuse(root.extrude(V(t, 0, 0)))
        elif flare == 2:
            root = Part.makeLoft([rect(-t, -w / 2, 0, w / 2, zf - 1.5).OuterWire,
                                  rect(-t - 1.5, -w / 2 - 1.5, 0, w / 2 + 1.5, zf).OuterWire], True, True)
            snap = snap.fuse([root, box(-t - 1.5, -w / 2 - 1.5, zf, 0, w / 2 + 1.5, z1)])
        if d == "+x":
            snap.translate(V(f + s, m, 0))
        elif d == "-x":
            snap.rotate(V(0, 0, 0), V(0, 0, 1), 180)
            snap.translate(V(f + s, m, 0))
        else:
            snap.rotate(V(0, 0, 0), V(0, 0, 1), 90)
            snap.translate(V(m, f, 0))
        snaps.append(snap)
    return snaps[0].fuse(snaps[1:]).removeSplitter()


def viewport():
    """The screen's viewport over its active area, with a 45 degree edge round
    it at the top face."""
    cx, cy, w, ht, r, c = P["viewport"]
    zt = P["top_z"]
    rr = lambda d, z: rounded_rect(cx - w / 2 - d, cy - ht / 2 - d, cx + w / 2 + d, cy + ht / 2 + d, r + d, z).OuterWire
    chamfer = Part.makeLoft([rr(0, zt - c), rr(c + 1, zt + 1)], True, True)  # carries on past the top face
    return [ext(rr(0, 0), P["plate_z"] - 0.1, zt - c + 0.01), chamfer]


def button_slot():
    """The U slot that frees the button's bar and pad from the plate."""
    return ext(button_slot_face(0.0).OuterWire, P["plate_z"] - 0.1, P["top_z"] + 1)


def connector_cuts():
    """The jack's round hole; at USB-C the receptacle's notch in the surround
    and the recess for the plug's overmould."""
    jx, jz = P["jack_axis"]
    return [Part.makeCylinder(P["jack_d"] / 2, 6.0, V(jx, -3.5, jz), V(0, 1, 0)), usb_notch(), usb_recess()]


def usb_notch():
    """The receptacle's notch: open toward the PCB, with 45 degree top
    corners, through the surround."""
    ux, _ = P["usb_center"]
    w, h = P["usb_shell"]
    cx, cz, k = P["usb_notch"]
    x0, x1 = ux - w / 2 - cx, ux + w / 2 + cx
    z0, z1 = P["pcb_top_z"], P["pcb_top_z"] + h + cz
    y0, y1 = P["pcb_usb_y"] - P["usb_surround"][1] - 1, P["outer"][3] + 1
    pts = [V(x0, y0, z0), V(x1, y0, z0), V(x1, y0, z1 - k), V(x1 - k, y0, z1), V(x0 + k, y0, z1), V(x0, y0, z1 - k)]
    return Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, y1 - y0, 0))


def usb_recess():
    """The recess for the plug's overmould, in the housing and the cap. Its
    lower corners turn into 45 degree faces, like the top round, so they print
    without support and meet the seam in a firm edge."""
    ux, uz = P["usb_center"]
    w, h, d, r = P["usb_recess"]
    y0, y1 = P["outer"][3] - d, P["outer"][3] + 1
    k = r / math.sqrt(2)
    zb = uz - h / 2
    xt, zt = w / 2 - r + k, zb + r - k  # where the lower corners reach 45 degrees
    xb = xt - (zt - zb)
    pts = [V(ux - xt, y0, zt), V(ux - xb, y0, zb), V(ux + xb, y0, zb), V(ux + xt, y0, zt)]
    flats = Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, y1 - y0, 0))
    return stadium_y(ux, uz, w, h, r, y0, y1).fuse(flats).removeSplitter()


def s1_relief():
    """The boss beside S1, cut back from the switch's jack end."""
    y0, z1 = P["s1_relief"]
    x0 = max(x for x, _ in P["screw_axes"]) - P["boss"][0] / 2 - 1
    return box(x0, y0, P["pcb_top_z"] - 1, slider_geom()["xi"], y0 + 2.0, z1)


def build_housing(board, diffuser):
    """The housing, from nothing but the outline and the parts that go in it:
    the outer shape less the inside, with the solids kept inside, then the
    holes. Returns the housing, the PCB's outline and the features in order as
    (name, operation, shape), each trimmed to what it adds or removes."""
    pcb = outline(board)
    outer = outer_upper()
    room = inside(pcb, diffuser)
    kept = [("Screw bosses", screw_bosses()),
            ("Screen clips", screen_clips()),
            ("Sensor pad", sensor_pad()),
            ("Sensor posts", sensor_posts(diffuser.BoundBox.YMin)),
            ("Sensor snaps", sensor_snaps()),
            ("Battery tray and stop", battery_tray()),
            ("Button post", button_post()),
            ("Button travel stop", button_stop()),
            ("Switch track", switch_track()),
            ("USB-C surround", usb_surround())]
    holes = [("Screw pilot holes", screw_pilots()),
             ("Sensor window", sensor_cuts()),
             ("Diffuser", [diffuser]),
             ("Screen viewport", viewport()),
             ("Button slot", [button_slot()]),
             ("Jack hole, USB-C notch and recess", connector_cuts()),
             ("Switch channel and window", slider_cuts()),
             ("S1 relief", [s1_relief()]),
             ("Cap groove", [tongue(groove=True)])]
    h = solid(outer.cut(room.cut([s for _, s in kept])).removeSplitter())
    h = solid(h.cut([s for _, ss in holes for s in ss]).removeSplitter())
    feats = [("Outer shape", "base", outer), ("Inside", "cut", room)]
    feats += [(n, "add", s.common(room)) for n, s in kept]
    feats += [(n, "cut", ss[0].fuse(ss[1:]).common(outer) if len(ss) > 1 else ss[0].common(outer)) for n, ss in holes]
    return h, pcb, feats


def slider_geom():
    """Where the switch cover's plate sits and how far it runs: its faces, its
    channel and the grip's window."""
    pl, ph, pt = P["switch_cover"]
    nl = P["switch_grip"][0]
    cx, cz = P["slider_clear"]
    xi = P["pcb_edge_x"] + P["pcb_edge_gap"] + 0.08  # plate inner face, clear of S1 wherever the PCB sits
    xf = xi + pt
    play = (P["switch_socket"][0] - P["act_w"]) / 2
    # The plate's centre from end to end of the travel, with the lever's play
    # in the socket and the PCB's in its pocket.
    ya = P["act_y"] - play - P["pcb_edge_gap"]
    yb = P["act_y"] + P["travel"] + play + P["usb_end_gap"]
    zc = sum(P["act_z"]) / 2
    return dict(xi=xi, xf=xf, xin=xi - cx, xw=xf + cx, cz=cz, zc=zc, z0=zc - ph / 2, z1=zc + ph / 2,
                y0=ya - pl / 2 - cz, y1=yb + pl / 2 + cz, wy0=ya - nl / 2 - cx, wy1=yb + nl / 2 + cx)


def slider_cuts():
    """The channel for the plate, from the seam up; the grip's window, open
    down to the seam and as high as the plate; and the lead-ins on the
    channel's mouth and on the end of the USB-end inner wall."""
    g = slider_geom()
    zs = P["seam_z"]
    chan = box(g["xin"], g["y0"], zs - 1, g["xw"], g["y1"], g["z1"] + g["cz"])
    win = box(g["xw"] - 0.1, g["wy0"], zs - 1, P["outer"][2] + 1, g["wy1"], g["z1"])
    ko, ki, short = P["channel_lead"]
    xw, xin = g["xw"], g["xin"]
    pts = [V(xw - 1, g["y0"], zs - 1), V(xw + ko + 1, g["y0"], zs - 1), V(xw - 1, g["y0"], zs + ko + 1)]
    leads = [Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, g["y1"] - short - g["y0"], 0))]
    _, zt, yu = P["track"]
    yr = P["s1_relief"][0]
    for ya, yb, zb in ((g["y0"], yr, P["pcb_top_z"]), (yr, yu, zt), (yu, g["y1"], P["pcb_top_z"] + g["cz"])):
        pts = [V(xin - ki - 1, ya, zb - 1), V(xin + 1, ya, zb - 1), V(xin + 1, ya, zb + ki + 1)]
        leads.append(Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, yb - ya, 0)))
    pts = [V(xin - ki, yu, P["pcb_top_z"]), V(xin + 0.1, yu, P["pcb_top_z"]), V(xin + 0.1, yu + ki + 0.1, P["pcb_top_z"])]
    leads.append(Part.Face(Part.makePolygon(pts + pts[:1])).extrude(V(0, 0, zt + ki - P["pcb_top_z"])))
    return [chan, win] + leads


def switch_tab():
    """A tab on the cap that closes the grip's window from the seam up to the
    plate's lower edge, and reaches in under the plate, 0.3 lower there. It
    clears the window's ends and the PCB's edge wherever the cap and the PCB
    sit in their play."""
    g = slider_geom()
    zs = P["seam_z"]
    cx, cz = P["slider_clear"]
    ya, yb, xo = g["wy0"] + cz + cx, g["wy1"] - cz - cx, P["outer"][2]
    under = box(g["xi"] + 0.35, ya, zs - 0.01, xo, yb, g["z0"] - cz)
    sill = box(g["xw"] + cx, ya, zs - 0.01, xo, yb, g["z0"])  # clear of the plate wherever the cap sits on its tongues
    return under.fuse(sill)


def build_slider():
    """The switch cover, on S1's lever at its jack end: the plate, the grip on
    its outer face and the lever's socket in its inner face."""
    g = slider_geom()
    pl, ph, pt = P["switch_cover"]
    gl, gh, proud, r = P["switch_grip"]
    pitch, rw, rd = P["switch_ridges"]
    sw, sh, sd = P["switch_socket"]
    ya, zc = P["act_y"], g["zc"]
    xo = P["outer"][2] + proud
    plate = box(g["xi"], ya - pl / 2, zc - ph / 2, g["xf"], ya + pl / 2, zc + ph / 2)
    plate = plate.makeChamfer(0.2, plate.Edges)
    grip = box(g["xi"] + 0.5, ya - gl / 2, zc - gh / 2, xo, ya + gl / 2, zc + gh / 2)
    grip = grip.makeFillet(r, [e for e in grip.Edges if e.BoundBox.XMin > xo - 1e-6])
    s = plate.fuse(grip)
    for k in (-1, 0, 1):
        s = s.cut(box(xo - rd, ya + k * pitch - rw / 2, zc - gh, xo + 1, ya + k * pitch + rw / 2, zc + gh))
    s = s.cut(box(g["xi"] - 1, ya - sw / 2, zc - sh / 2, P["act_tip_x"] + sd, ya + sw / 2, zc + sh / 2))
    return solid(s.removeSplitter())


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
    cover = cover.cut(usb_recess())  # the plug recess's lower edge
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
    z0, z1 = P["act_z"]
    act = box(P["pcb_edge_x"] - 0.01, P["act_y"] - w / 2, z0, P["act_tip_x"], P["act_y"] + w / 2, z1)
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
    return t.cut([box(g.XMin, g.YMin - 0.7 - e, zs - 1, g.XMax + 2, g.YMax + 0.7 + e, zs + 3) for g in gaps])  # ends on the side arcs


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


def button_inlay():
    """Blue on the round pad only, exactly the pad, except that the black bar
    runs on into it to a square end, where its edges meet the pad's round:
    so the bar has no sharp corners where it meets the blue."""
    px, py, pr = P["button_pad"]
    h = P["button_bar"][1] / 2
    xj = px - math.sqrt(pr * pr - h * h)
    z0, z1 = P["inlay_z"]
    f = disc(px, py, pr, z0).cut(rect(xj - pr, py - h, xj, py + h, z0))
    return f.extrude(V(0, 0, z1 + 1 - z0))


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
    """A spring strip either side of the OLED board, bridged between two end
    blocks that run out into the side wall; tabs on the blocks stop the board
    along Y. Between the blocks a wall fills out to the side wall too, behind
    a slot that lets the strip bend out to let the board in and stops it short
    of bending too far. The right strip's block at the button end stands
    beside the board, with no tab, so the button's slot stays clear and
    nothing stands free. A lip in the middle of each
    strip closes over the board's back. Its catch face is clip_lip[3] degrees
    from flat and stands clip_lip[2] clear of the board, which prints as one
    0.30 mm layer, so the strip always springs back over the board and the
    screen stops against the lips when pressed from the front. Printed top
    face down, the strips are bridges and the lips short overhangs."""
    bx0, by0, bx1, by1 = P["oled_board"]
    zb = P["plate_z"] - P["oled_stack"]  # the board's back
    g, s = P["clip_gap"], P["clip_post"]
    t, z0, z1 = P["clip_beam"]
    reach, ll, clear, ang = P["clip_lip"]
    slot = P["clip_backing"]
    xwl, xwr = P["outer"][0] - 5, P["outer"][2] + 5  # out into the side walls; trimmed to the inside
    k = math.tan(math.radians(ang))
    zp = P["plate_z"] + 0.33  # into the plate
    zr = zb - clear + g * k  # catch face at the strip
    za = zr - reach * k  # its inner edge
    ym = (by0 + by1) / 2
    ya, yb = by0 - g, by1 + g  # end block faces toward the board
    parts = []
    for xi, out, xw in ((bx0 - g, -1, xwl), (bx1 + g, 1, xwr)):  # strip inner face, outward direction, side wall
        xs = lambda d: xi + out * d  # d: distance outward from the inner face
        right = out > 0
        y_end = yb if right else yb + s  # the right strip ends at its block beside the board
        xlo, xhi = sorted((xs(0), xs(t)))
        parts.append(box(xlo, ya - s, z0, xhi, y_end, z1))
        plo, phi = sorted((xs(0), xw))  # end blocks, out into the side wall
        wlo, whi = sorted((xs(t + slot), xw))  # the wall behind the slot
        tlo, thi = sorted((xs(0), xs(-s)))  # end tabs, over the board corners
        for y0, y1 in ((ya - s, ya), (y_end - s, y_end)):
            parts.append(box(plo, y0, z0, phi, y1, zp))
        parts.append(box(wlo, ya - 0.01, z0, whi, y_end - s + 0.01, zp))
        for y0, y1 in ((ya - 1.0, ya), (yb, yb + 1.0)):
            if not (right and y0 > ym):
                parts.append(box(tlo, y0, zb, thi, y1, zp))  # down to the board back
        prof = [V(xs(0.01), ym - ll / 2, zr), V(xs(-reach), ym - ll / 2, za), V(xs(0.01), ym - ll / 2, za - reach)]
        parts.append(Part.Face(Part.makePolygon(prof + prof[:1])).extrude(V(0, ll, 0)))
    return parts[0].fuse(parts[1:]).removeSplitter()


OLED_PARTS = ("Part__Feature005", "OLEDPCB", "OLEDHolePlating", "OLEDHeader", "OLEDHeaderPins", "OLEDFlex",
              "OLEDRearICs", "OLEDTraces")


def build_oled(doc):
    """The screen module as it is, where the source model has a thicker glass
    and no solder: how far its parts move to put the screen's face on the
    plate, with the glass as thick as oled_stack leaves over the board and
    the header's solder points standing on the board's front, their tips
    oled_pins[3] above its back. The two shapes are where the source model
    has them, before the move."""
    cx, cy, row, h = P["oled_pins"]
    pcb = doc.getObject("OLEDPCB").Shape.BoundBox
    g = doc.getObject("Part__Feature005").Shape.BoundBox
    glass = box(g.XMin, g.YMin, pcb.ZMax, g.XMax, g.YMax, pcb.ZMin + P["oled_stack"])
    z0 = pcb.ZMax - 0.01
    solder = [Part.makeCone(0.9, 0.35, pcb.ZMin + h - z0, V(cx + (i - 1.5) * row / 3, cy, z0)) for i in range(4)]
    pins = doc.getObject("OLEDHeaderPins").Shape.fuse(solder).removeSplitter()
    return P["plate_z"] - P["oled_stack"] - pcb.ZMin, {"Part__Feature005": glass, "OLEDHeaderPins": pins}


def build_all(doc):
    board = doc.getObject("BoardRev4").Shape
    diffuser = doc.getObject("IntegratedDiffuser").Shape.copy()  # booleans can loosen their tools' tolerances
    housing, pcb, features = build_housing(board, diffuser)
    slider = build_slider()
    cover = build_cover(pcb)
    cup_cover = build_cover(pcb, P["cup_cover_extra"])
    cover = solid(cover.fuse([tongue(), switch_tab()]).removeSplitter())
    cup_cover = solid(cup_cover.fuse([tongue(), switch_tab()]).removeSplitter())
    # The blue inlays: the button's round pad, and the R+D logo moved to the
    # top left corner (the original logo body gives its outline).
    button = solid(housing.common(button_inlay()).removeSplitter())
    housing = solid(housing.cut(button_inlay()).removeSplitter())
    logo = logo_inlay(doc.getObject("Body").Shape)
    housing = solid(housing.cut(logo).removeSplitter())
    features += [("Button inlay (blue)", "cut", button), ("Logo inlay (blue)", "cut", logo)]
    print("housing", housing.isValid(), len(housing.Solids), round(housing.Volume, 1))
    print("slider", slider.isValid(), len(slider.Solids), round(slider.Volume, 1))
    print("cover", cover.isValid(), len(cover.Solids), round(cover.Volume, 1))
    print("cup cover", cup_cover.isValid(), len(cup_cover.Solids), round(cup_cover.Volume, 1))

    return dict(
        housing=housing,
        features=features,
        slider=slider,
        cover=cover,
        cup_cover=cup_cover,
        cups=[suction_cup(x, y, cup_cover_rear()) for x, y, _ in P["cup_keys"]],
        s1=build_s1(doc.getObject("Part__Feature002").Shape),
        button=button,
        logo=logo,
        screws=[build_screw(x, y) for (x, y) in P["screw_axes"]],
    )
