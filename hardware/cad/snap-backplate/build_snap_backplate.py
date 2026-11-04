"""Build the DTT slide-in backplate around the enclosed case.

Run from the repository root under the FreeCAD GUI (needed for colours and previews):
    freecad hardware/cad/snap-backplate/build_snap_backplate.py
or headless with xvfb-run. It opens hardware/cad/enclosed-case/DTT-Enclosed.FCStd read-only, adds
the backplate and saves the result beside this script as DTT-Snap-Backplate-Concept.FCStd, with
STEP/STL exports in hardware/production-exports/cad/snap-backplate/. DTT-Enclosed.FCStd itself is
not modified. Edit PARAMS below and re-run to change the design.

The enclosed case is full width at its USB-C end and curves in toward the jack end, so the sleeve's
section follows its sides: side walls with lips over the case's top round, and a hood with the same lip over
its jack end. The case rests on a ledge along the foot of each side wall, and the lever's teeth catch its
USB-C end face either side of the USB-C recess.

Design language: the track and the plate are one form. The part is the intersection of
a plan outline (the case outline grown by the wall; in the Double Double version it flares into two
cup wings with large radii) and a side elevation (a flat top from the hood at the jack end along the
module, then one S-shaped swoop down into the wings ahead of the side switch). The outer top edge carries
one continuous fillet and the module cavity is cut out of that form. The latch is a release lever
that is part of the plate outline: two slots run from under the module out through the top edge,
the flex zone is thinned from the front, and the full-thickness press tab carries grip grooves.
Printed-in stops limit the lever both ways: fingers under the tab and chamfered rails over its edges.
The print is black; the touch point, the front of the press tab, is a 0.6 mm blue inlay kept as a
separate body for two-colour printing. The grip grooves cut through it, so their bottoms are black.
The standard version has two cups in line, the upper one on a fixed tongue inside a U-shaped lever.
Instead of the cups, an optional one-piece wall bracket carries the keyhole studs. It screws or
sticks to the wall, and the plate hangs on it.

The Side Cups version is the standard one with both keyholes turned sideways, in opposite directions:
the lower cup slides in from the left, the upper one from the right. No slide of the plate frees both
cups, so pulling the case up and out cannot drag the plate off them. The tongue is too narrow for a
sideways keyhole, so the upper cup sits under the case below the lever root. The cups click into the
plate first, and then the plate goes onto the wall. It has no wall bracket, since rigid studs cannot
enter two opposite slots.

The same run builds a Double Double version for the OSSM Double Double toy mount. Its plate runs on
past the jack end to a boss. A printed hex flange screw with the OSSM 24 mm thread sits in a hex pocket
from the rear, so it cannot turn, and the Double Double threads onto it from the front. A fourth cup
sits right under the toy: its stem clicks into a slot in the screw head, and the pocket closes the
slot once the screw is in.

Device coordinates: X across the module, Y along it (USB-C end at +Y), Z out of the front face. The
case's rear face is Z -8.1. The wall is at -Z; the part prints rear face down.
"""
import math, os, sys
import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
CAD = os.path.join(ROOT, 'hardware', 'cad')
MODULE = os.path.join(CAD, 'enclosed-case', 'DTT-Enclosed.FCStd')
HERE = os.path.join(CAD, 'snap-backplate')
IMAGES = os.path.join(HERE, 'images')
OUT = os.path.join(ROOT, 'hardware', 'production-exports', 'cad', 'snap-backplate')
TAG = 'SnapBackplate'
sys.path.insert(0, os.path.dirname(MODULE))
import build_enclosed_case as ENC   # the case's own dimensions, for the fit checks

# name: (value, basis)
PARAMS = {
    # module: the enclosed case, measured from the solids in DTT-Enclosed.FCStd
    'BodyRearZ': (-8.1, 'verified: rear cover outer face, flat, with the screws flush'),
    'BodyX0': (-4.0, 'verified: case side at the USB-C end; toward the jack end the sides follow ENC.plan_outline'),
    'BodyX1': (46.0, 'verified: case side at the USB-C end; the switch cover grip stands 0.4 proud at Y 79.9-88.1'),
    'TopFilletR': (ENC.top_round() or ENC.P['edge_fillet'], 'verified: round along the top edges and the jack end, from the case builder; it turns into a 45 deg face at its 45 deg point'),
    'DeviceCx': (21.0, 'verified: case centreline'),
    'DeviceBottomY': (-0.6, 'verified: jack end face'),
    'DeviceTopY': (94.6, 'verified: USB-C end face'),
    'HousingTopZ': (14.17, 'verified: front face'),
    # plate outline: a body flush with the track; the Double Double version flares into two wings that carry
    # its upper cups
    'PlateT': (6.0, 'design: 2 mm over the reference proxy, so the stop fingers stay 1.7 mm thick under the 3.7 mm press the teeth need'),
    'DeviceTopInset': (17.0, 'reference proxy: plate top to housing top end'),
    'WingWeb': (6.0, 'design: plate web around the upper keyholes, wide enough not to snap when the plate is pushed onto the cups'),
    'FlareR': (14.0, 'design: concave blend from the body into each wing'),
    'CornerR': (6.2, 'design: convex plan corners at the top; at the jack end the plate follows the case corners, so the wall stays 2 mm'),
    # sleeve: side elevation and edges
    'RestGap': (1.0, 'design: plate front to the case rear, the height of the side ledges; the cup heads sit 0.6 below the plate front'),
    'WallClear': (0.2, 'design: clearance to the housing sides'),
    'RailT': (2.0, 'design: side wall thickness'),
    'WallTopAbove': (1.2, 'design: wall top above the case front face'),
    'SwoopY0': (44.0, 'design: wall top starts to fall here; the lips run to here'),
    'SwoopY1': (77.0, 'design: wall reaches the plate here, clear of the upper keyhole entries (Y 78.8) and the switch cover grip (Y 79.9)'),
    'EdgeR': (1.0, 'design: fillet along the whole outer top edge of the sleeve and wings, half the 2 mm wall so its top stays square'),
    'BedChamfer': (0.6, 'design: rear outer edge, against elephant foot'),
    'InnerChamfer': (1.0, 'design: 45 deg fillet-chamfer at the inner foot of the walls'),
    'LipPastTangent': (0.4, 'design: the lips (sides and jack end) reach this far in past the 45 deg point of the case\'s top round, over its 45 deg face'),
    'JackOpenX0': (14.0, 'design: opening in the hood for the 3.5 mm plug'),
    'JackOpenX1': (28.0, 'design'),
    'JackOpenR': (3.0, 'design: bottom corners of the plug opening'),
    'JackEdgeR': (1.0, 'design: rounded edges of the plug opening'),
    'InnerEdgeR': (0.5, 'design: rounded inner top edges of the walls and the hood'),
    'LipChamfer': (0.6, 'design: 45 deg chamfer along the top of the lip tips, part of the section (OCC cannot round them)'),
    'SlotEdgeR': (0.4, 'design: rounded front edges of the lever slots'),
    'KeyEdgeR': (0.8, 'design: rounded front edges of the keyholes'),
    'LedgeReach': (3.8, 'design (Lucy: rails under the case sides): ledge from each side wall in under the case to X -0.2 and 42.2, 0.25 short of the screw countersinks'),
    'LedgeY1': (78.0, 'design: ledge end, with a 45 deg lead-in, short of the Double Double upper keyhole entries (Y 79.3 at the wall)'),
    # release lever: part of the plate outline between two slots; teeth snap behind the case
    'LatchX0': (8.0, 'design: lever left edge'),
    'LatchX1': (34.0, 'design: lever right edge'),
    'LatchRootY': (62.0, 'design: lever root (slot ends), under the module'),
    'LatchSlot': (1.5, 'design: slot width either side of the lever; slots run out through the top edge'),
    'LatchReliefD': (2.5, 'design: round stress-relief ends of the slots at the root'),
    'LatchT': (2.0, 'design: flex zone thickness, thinned from the FRONT so it prints flat on the bed'),
    'LatchRootRamp': (6.0, 'design: run of the thinning ramps at both ends of the flex zone'),
    'LatchFlexEndY': (87.6, 'design: flex zone ends; the press tab with the teeth is full thickness'),
    'ToothXL': (9.5, 'design: left tooth X 9.5-13.5, clear of the USB-C recess in the case end'),
    'ToothXR': (28.5, 'design: right tooth X 28.5-32.5, clear of the USB-C recess'),
    'ToothW': (4.0, 'design: each tooth'),
    'ToothEdgeR': (0.5, 'design: rounded side edges of the teeth'),
    'ToothRise': (3.0, 'design (Lucy: more proud): tooth top above the case rear; catches 2.2 mm of the USB-C end face above its 0.8 chamfer, 0.4 clear of the recess'),
    'ToothClear': (0.2, 'design: tooth stop face to the module end'),
    'ToothFlat': (1.0, 'design'),
    'RampAngle': (30.0, 'design: lead-in ramp, degrees from the plate'),
    # over-travel stop: a fixed finger from the plate crosses each slot on the bed into a pocket in the
    # lever's rear; the pocket roof is bridged over the finger and bottoms out on it when pressed too far
    'StopY0': (94.2, 'design: fingers start just past the flex zone (the lever is full thickness from Y 93.6)'),
    'StopW': (4.0, 'design: finger width along Y'),
    'StopLand': (0.6, 'design: square lever edge at the slot above the 45 deg pocket roof, clear of the slot edge round; one 0.6 mm line'),
    'StopGap': (3.7, 'design: finger top to pocket roof, measured along Z: the press travel at the fingers'),
    'StopPen': (0.9, 'design: finger overlap into the lever, beside the teeth'),
    'StopClear': (0.5, 'design: clearance around the fingers, wide enough that elephant foot does not fuse them'),
    'PullY0': (99.6, 'design: pull-out rails beside the press tab, from just past the press-stop pockets (Y 98.7) out to the top edge'),
    'PullPen': (0.9, 'design: rail reach over the lever edge'),
    'PullLand': (0.6, 'design: rail thickness at its tip, flush with the front; one 0.6 mm line'),
    'PullGap': (1.0, 'design: rail underside to the lever, measured along Z: the outward travel at the tab edges'),
    'GripN': (4.0, 'design: grip grooves across the press tab'),
    'GripPitch': (2.0, 'design'),
    'GripW': (1.0, 'design: groove width; straight walls with a round bottom'),
    'GripDepth': (0.9, 'design: groove depth, through the blue inlay so the groove bottoms are black'),
    'GripStart': (1.2, 'design: first groove centre past the back foot of the teeth'),
    # colour: black print with the touch point (the press tab) in blue, as a separate body
    'TouchY0': (102.6, 'design: blue starts just past the teeth (back foot at Y 102.4), so the teeth stay on black'),
    'TouchInlayT': (0.6, 'design: blue inlay depth from the front face; only 3 layers need both colours'),
    # cups, keyhole travel and head size from the reference proxy. The standard version has two cups on the
    # centreline, the upper one on a fixed tongue inside the lever (see STANDARD); the Double Double version
    # has one under the module and one in each wing
    'TopCupX': (28.0, 'design: from the centreline (reference 28.5); the heads reach under the case corners, 1.6 below it'),
    'TopCupDrop': (13.0, 'reference proxy: below the plate top'),
    'TopSlot': (12.0, 'design: upper slots run upward from the entry, so the load seats the stems'),
    'LowCupY': (28.0, 'design: stem under the module'),
    'LowSlot': (12.0, 'design: lower slot runs upward from the entry'),
    'KeyEntryD': (15.6, 'design: passes the 15 mm stem head, 0.3 mm a side; also the recess the head slides in'),
    'KeySlotW': (8.9, 'design: free slot from the entry, 0.2 mm a side on the 8.5 mm stem groove'),
    'KeySnapD': (8.4, 'design (Lucy: tighter cups): pocket at the slot end, 0.1 mm under the 8.5 mm stem groove; tune on a test print'),
    'KeySnapWrap': (190.0, 'design (Lucy): the pocket keeps 190 deg of its rim, so the stem clicks past the mouth'),
    'KeySnapLead': (1.5, 'design: lead-in from the free slot width down to the mouth'),
    'KeyLandT': (2.4, 'design (Lucy: tighter cups): plate left under the head recess, in the 2.5 mm groove with 0.1 mm slack (8 layers at 0.3)'),
    'CupD': (35.0, 'reference proxy (estimate)'),
    'CupDepth': (14.0, 'reference proxy (estimate): cup rim to plate rear'),
    'CupWall': (1.2, 'reference proxy'),
    'StemD': (15.0, 'reference (measured): stem and head flange outside diameter'),
    'StemLen': (3.0, 'reference proxy (estimate): stem from the cup body to the groove'),
    'GrooveD': (8.5, 'reference (measured)'),
    'GrooveH': (2.5, 'reference (measured): stem shoulder to head flange'),
    'HeadT': (3.0, 'reference (measured): head flange, opposite the cup face'),
    'StemSeat': (0.1, 'reference proxy: stem shoulder to plate rear as modelled, inside the groove slack'),
    # optional wall bracket in place of the cups: screwed or stuck to the wall, the plate hangs on its studs
    'BracketT': (7.0, 'design: plate rear to wall; at the stop the tab end moves 6.3 mm toward the wall'),
    'BracketInset': (1.0, 'design: bracket outline inside the plate outline'),
    'BracketNotchClear': (1.0, 'design: notch around the lever and its slots, so the lever is free of the bracket'),
    'BracketNotchR': (2.0, 'design: notch corners'),
    'BracketEdgeR': (1.0, 'design: front outer edge'),
    'BracketBedChamfer': (0.6, 'design: wall-side outer edge, against elephant foot'),
    'StudNeckD': (8.0, 'design: passes the 8.37 mm mouth of the slot-end pocket'),
    'StudGap': (0.3, 'design: keyhole land to the start of the head'),
    'StudHeadD': (12.6, 'design: passes the 15.6 mm keyhole entry; 45 deg underside prints without support'),
    'StudChamfer': (0.3, 'design: stud top edge'),
    'ScrewY': (46.0, 'design: between the lower keyhole (top Y 32.5) and the lever notch (Y 59.75)'),
    'ScrewDX': (12.0, 'design: screws at X 21 +/- 12, behind the plate'),
    'ScrewClearD': (4.5, 'design: clears #6 (3.5 mm) and #8 (4.2 mm) drywall screws'),
    'ScrewCskD': (9.0, 'design: 90 deg countersink diameter'),
    'ScrewSink': (0.4, 'design: counterbore above the countersink, so the head sits below the bracket face'),
    'ScrewHeadD': (8.3, 'reference: #6 drywall screw bugle head (estimate)'),
    'ScrewShankD': (3.5, 'reference: #6 drywall screw'),
    'ScrewLen': (32.0, 'reference: 1-1/4 in drywall screw'),
    # Double Double version: a printed screw with the OSSM 24 mm thread, in a hex pocket from the rear
    'DDGap': (12.5, 'design (Lucy): holder bottom to the Double Double base; see dd_checks for the plug room'),
    'DDBaseD': (33.0, 'reference (measured): OSSM Double Double 24mm Threaded base'),
    'DDThreadDepth': (21.0, 'reference (measured): Double Double internal thread depth'),
    'ThreadMajorD': (23.5, 'reference (measured): OSSM 24 mm clamping thread crest'),
    'ThreadRootD': (19.74, 'reference (measured)'),
    'ThreadPitch': (3.0, 'reference (measured): 60 deg flanks'),
    'ThreadCrest': (0.45, 'reference (measured): crest flat'),
    'ThreadFlat': (11.0, 'reference (measured): print flat 11 mm off the axis, as on the OSSM part, so the screw prints on its side'),
    'ThreadOut': (15.0, 'design (Lucy): thread standing out of the boss'),
    'DDScrewHexAF': (26.0, 'design: hex in the pocket, wide enough for the thread to pass through'),
    'DDScrewSeatD': (36.0, 'design: flange, a 45 deg cone seat flush with the plate rear'),
    'DDScrewSeatH': (3.0, 'design'),
    'DDScrewHexH': (7.0, 'design: plate rear to the hex chamfer'),
    'DDScrewChamferH': (3.0, 'design: 45 deg from the hex down to the thread, so the pocket roof needs no bridge'),
    'DDPocketClear': (0.1, 'design: tight, so the screw cannot turn; tune on a test print'),
    'DDHoleClear': (0.35, 'design: thread hole in the boss top, radial'),
    'DDBossD': (38.0, 'design: boss on the plate front under the Double Double base'),
    'DDBossT': (5.0, 'design: boss height; with the 6 mm plate the screw sits in 11 mm'),
    'DDCupHeadClear': (0.3, 'design: room over the fourth cup head in the screw head'),
    'DDCupSnap': (0.4, 'design (Lucy: the cup clicks in): slot mouth this much narrower than the stem groove; tune on a test print'),
    'DDCupSnapLead': (1.5, 'design: lead-in from the free slot width down to the mouth'),
}
P = {k: v for k, (v, _) in PARAMS.items()}
DD = False   # True while main() builds the Double Double version
SIDE = False   # True while main() builds the Side Cups version

# The standard version (two cups in line, no wings) changes these. Its lever is a U: two arms from the root,
# joined by the press tab, with a fixed tongue between them that carries the upper cup, so the cup sits
# right under the tab and pressing the tab never pulls on it.
STANDARD = {
    'LatchX0': (3.0, 'design: lever left edge; the slot and its root relief stay 0.2 clear of the ledge foot'),
    'LatchX1': (39.0, 'design: lever right edge'),
    'TongueX': (9.4, 'design: half width of the fixed tongue: the 15.6 mm head recess plus 1.6 mm webs'),
    'TongueTop': (101.5, 'design: tongue free end; the press tab starts past the slot across it'),
    'TongueWeb': (1.6, 'design: tongue past the head recess at its free end'),
    'ToothXL': (5.5, 'design: left tooth X 5.5-9.5, on the left arm'),
    'ToothXR': (32.5, 'design: right tooth X 32.5-36.5, on the right arm'),
    'TouchY0': (103.2, 'design: blue starts just past the slot across the tongue end'),
    'GripStart': (2.0, 'design: first groove centre past the teeth, clear of the slot across the tongue end'),
    'GripN': (3.0, 'design'),
    'LedgeY1': (92.0, 'design: ledge end, with a 45 deg lead-in, 2.6 short of the case end'),
}

# The Side Cups version changes these on top of STANDARD. Its lever and tongue stay as they are, so the
# lever feels the same, but no cup sits on the tongue.
SIDE_CUPS = {
    'LowCupY': (11.0, 'design (Lucy: sideways keyholes in opposite directions): lower cup, entry on the left; its head recess stays 3 mm clear of the hood foot and the rim shows 3.7 mm below the plate'),
    'UpCupY': (50.5, 'design: upper cup, entry on the right; its head recess stays 2.45 mm clear of the lever slot reliefs (Y 60.75), and the cups are 39.5 mm apart'),
    'SideSlot': (11.0, 'design: entry to click end; one short of the standard 12, so the head recesses stay 1.4 mm clear of the ledge feet (X 0.8 and 41.2)'),
}
BASE = dict(P)

# The side lips run from the jack end to where the swoop starts, at Y 44, so the swoop is a plain wall.
# The walls have fallen to the plate before the switch cover.
FAR = 400.0   # extent of construction solids that must run past the part


def plate_top():
    return P['DeviceTopY'] + P['DeviceTopInset']


def z_front():
    return P['BodyRearZ'] - P['RestGap']


def z_rear():
    return z_front() - P['PlateT']


def z_wall_top():
    return P['HousingTopZ'] + P['WallTopAbove']


def V(x, y, z):
    return App.Vector(x, y, z)


def prism(points_xy, z0, z1):
    pts = [V(x, y, z0) for x, y in points_xy]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, z1 - z0))


def prism_xz(points_xz, y0, y1):
    pts = [V(x, y0, z) for x, z in points_xz]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, y1 - y0, 0))


def prism_yz(points_yz, x0, x1):
    pts = [V(x0, y, z) for y, z in points_yz]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(r, x, y, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0))


def round_face(face, concave, convex):
    """Round a planar face's corners: out-in rounds concave corners, in-out rounds convex ones."""
    if concave:
        face = face.makeOffset2D(concave, join=0).makeOffset2D(-concave, join=0)
    if convex:
        face = face.makeOffset2D(-convex, join=0).makeOffset2D(convex, join=0)
    return face


def flat_face(solids, z):
    """Fuse thin construction solids and return their face lying at height z."""
    s = solids[0].fuse(solids[1:]).removeSplitter() if len(solids) > 1 else solids[0]
    return [f for f in s.Faces if abs(f.CenterOfMass.z - z) < 1e-6 and abs(f.normalAt(0, 0).z) > 0.99][0]


def cup_centres():
    cx = P['DeviceCx']
    if DD:
        yt = plate_top() - P['TopCupDrop']
        return {'UL': (cx - P['TopCupX'], yt), 'UR': (cx + P['TopCupX'], yt), 'L': (cx, P['LowCupY'])}
    if SIDE:
        return {'U': (cx, P['UpCupY']), 'L': (cx, P['LowCupY'])}
    return {'U': (cx, P['TongueTop'] - P['TongueWeb'] - P['KeyEntryD'] / 2), 'L': (cx, P['LowCupY'])}


def cup_positions():
    """Every cup: the keyhole cups, and in the Double Double version the one held by the screw."""
    cups = cup_centres()
    if DD:
        cups['D'] = dd_axis()
    return cups


def key_dir(key):
    """Unit vector (X, Y) from a keyhole's entry to its click end: up, so the load seats the stems, or in
    the Side Cups version sideways, the lower one to the right and the upper one to the left."""
    if SIDE:
        return (1.0, 0.0) if key == 'L' else (-1.0, 0.0)
    return (0.0, 1.0)


def key_slot(key):
    if SIDE:
        return P['SideSlot']
    return P['TopSlot'] if key in ('UL', 'UR', 'U') else P['LowSlot']


def entry_centre(key):
    (sx, sy), (dx, dy) = cup_centres()[key], key_dir(key)
    return sx - dx * key_slot(key), sy - dy * key_slot(key)


def key_local(key, pts):
    """Plate (X, Y) of keyhole points given as (across, along) from its click end, along running away from
    the entry."""
    (sx, sy), (dx, dy) = cup_centres()[key], key_dir(key)
    return [(sx + u * dy + v * dx, sy - u * dx + v * dy) for u, v in pts]


def key_box(key, across, along=0.0):
    """(x0, x1, y0, y1) from a keyhole's entry centre to its click end, grown `across` either side of the
    slot and `along` past both ends."""
    (sx, sy), (ex, ey), (dx, dy) = cup_centres()[key], entry_centre(key), key_dir(key)
    gx, gy = across * abs(dy) + along * abs(dx), across * abs(dx) + along * abs(dy)
    return min(sx, ex) - gx, max(sx, ex) + gx, min(sy, ey) - gy, max(sy, ey) + gy


def dd_axis():
    """Double Double screw axis (X, Y): on the centreline, with the base DDGap below the hood."""
    return P['DeviceCx'], y_end() - P['DDGap'] - P['DDBaseD'] / 2


def outer_x(side):
    """Sleeve outer face at the USB-C end, where the case is widest."""
    c, t = P['WallClear'], P['RailT']
    return P['BodyX0'] - c - t if side == 'L' else P['BodyX1'] + c + t


def case_face(grow=0.0, z=0.0):
    """The case outline in plan, from the enclosed case's own builder, grown outwards by grow."""
    f = ENC.plan_outline(z)
    return ENC.offset_face(f, grow) if grow else f


def side_x(y, side):
    """The case side at y, before the jack end corners round it (the case curves in toward the jack)."""
    h = ENC.half_width(max(y, P['DeviceBottomY']))
    return P['DeviceCx'] - h if side == 'L' else P['DeviceCx'] + h


def side_stations(y0, y1, step=4.0):
    """Y positions from y0 to y1 at which a section through the curved sides is close enough to them."""
    ys = ENC.P['taper'][0]
    n = max(1, int(math.ceil((min(y1, ys) - y0) / step))) if y0 < ys else 1
    pts = [y0 + (min(y1, ys) - y0) * i / n for i in range(n + 1)] if y0 < ys else [y0]
    if y1 > pts[-1]:
        pts.append(y1)
    return pts


def y_end():
    """Outer face of the hood at the jack end."""
    return P['DeviceBottomY'] - P['WallClear'] - P['RailT']


def plan_face():
    """Plate outline: the case outline grown by the wall, running on past the case's top end to the plate
    top. The Double Double version flares into two round-ended cup wings and runs on past the jack end to
    a round end around its screw."""
    zr = z_rear(); top = plate_top(); t = 1.0
    xl, xr = outer_x('L'), outer_x('R')
    body = case_face(P['WallClear'] + P['RailT'], zr).extrude(V(0, 0, t))
    parts = [body, box(xl, xr, P['DeviceTopY'] - 10, top, zr, zr + t)]
    if not DD:
        return round_face(flat_face(parts, zr), 0, P['CornerR'])
    re = P['KeyEntryD'] / 2 + P['WingWeb']                # wing lobe radius around each entry
    (ulx, uly), (urx, _) = entry_centre('UL'), entry_centre('UR')
    wx0, wx1 = ulx - re, urx + re
    parts += [box(wx0, wx1, uly, top, zr, zr + t), cyl(re, ulx, uly, zr, zr + t), cyl(re, urx, uly, zr, zr + t)]
    # The body runs on past the jack end, as wide as the sleeve there, to a round end around the screw. The
    # box reaches up past the sleeve's corners, so its sides cross them cleanly.
    ay = dd_axis()[1]
    hw = ENC.half_width(P['DeviceBottomY']) + P['WallClear'] + P['RailT']
    cx = P['DeviceCx']
    parts += [box(cx - hw, cx + hw, ay, P['DeviceBottomY'] + 10, zr, zr + t), cyl(hw, cx, ay, zr, zr + t)]
    return round_face(flat_face(parts, zr), P['FlareR'], P['CornerR'])


def elevation_wire_pts():
    """Side elevation (Y, Z) of the sleeve top: flat from past the hood at the jack end (the plan outline
    ends it, square like the side walls), then the S-swoop down to the plate."""
    zf, zr, zt = z_front(), z_rear(), z_wall_top()
    ya = y_end() - 3.0
    # two equal tangent arcs from (SwoopY0, zt) down to (SwoopY1, zf)
    s0, s1 = P['SwoopY0'], P['SwoopY1']; H = zt - zf; Ls = s1 - s0
    th = 2 * math.atan(H / Ls); Rs = Ls / (2 * math.sin(th))
    c_up = (s0, zt - Rs); c_lo = (s1, zf + Rs)
    m_up = (c_up[0] + Rs * math.sin(th / 2), c_up[1] + Rs * math.cos(th / 2))
    mid = (c_up[0] + Rs * math.sin(th), c_up[1] + Rs * math.cos(th))
    m_lo = (c_lo[0] - Rs * math.sin(th / 2), c_lo[1] - Rs * math.cos(th / 2))
    return dict(start=(ya, zr - 1), ya=(ya, zt), s0=(s0, zt),
                m_up=m_up, mid=mid, m_lo=m_lo, s1=(s1, zf), far=(FAR, zf), far_low=(FAR, zr - 1),
                swoop_r=Rs, swoop_deg=math.degrees(th))


def elevation_solid():
    e = elevation_wire_pts(); xa, xb = -FAR / 2, FAR / 2
    P3 = lambda p: V(xa, p[0], p[1])
    edges = [Part.LineSegment(P3(e['start']), P3(e['ya'])), Part.LineSegment(P3(e['ya']), P3(e['s0'])),
             Part.Arc(P3(e['s0']), P3(e['m_up']), P3(e['mid'])), Part.Arc(P3(e['mid']), P3(e['m_lo']), P3(e['s1'])),
             Part.LineSegment(P3(e['s1']), P3(e['far'])), Part.LineSegment(P3(e['far']), P3(e['far_low'])),
             Part.LineSegment(P3(e['far_low']), P3(e['start']))]
    wire = Part.Wire([g.toShape() for g in edges])
    s = Part.Face(wire).extrude(V(xb - xa, 0, 0))
    if DD:   # the hood ends in a step at its outer face and the plate runs on past it
        ye, zr, zf = y_end(), z_rear(), z_front()
        s = s.cut(box(xa, xb, -FAR, ye, -FAR, FAR)).fuse(box(xa, xb, -FAR, ye, zr - 1, zf)).removeSplitter()
    return s


def _vertical(face):
    try:
        u0, u1, v0, v1 = face.ParameterRange
        return abs(face.normalAt((u0 + u1) / 2, (v0 + v1) / 2).z) < 1e-6
    except Exception:
        return False


def sleeve_blank():
    """Plan outline x side elevation, with the outer top edge filleted and the bed edge chamfered."""
    zr = z_rear()
    blank = plan_face().extrude(V(0, 0, z_wall_top() + 2 - zr)).common(elevation_solid()).removeSplitter()
    if DD:
        ax, ay = dd_axis()
        blank = blank.fuse(cyl(P['DDBossD'] / 2, ax, ay, z_front() - 1, z_front() + P['DDBossT'])).removeSplitter()
    top_edges, bed_edges = [], []
    ye, zf = y_end(), z_front()
    for e in blank.Edges:
        faces = blank.ancestorsOfType(e, Part.Face)
        if len(faces) != 2:
            continue
        b = e.BoundBox
        if DD and max(abs(b.YMin - ye), abs(b.YMax - ye), abs(b.ZMin - zf), abs(b.ZMax - zf)) < 1e-6:
            continue   # the hood step's foot stays sharp: a round there is tangent to the plug opening's floor
        vert = [_vertical(f) for f in faces]
        if vert.count(True) != 1:
            continue
        other = faces[vert.index(False)]
        if abs(other.CenterOfMass.z - zr) < 1e-6:
            bed_edges.append(e)
        else:
            top_edges.append(e)
    for r in (P['EdgeR'], P['EdgeR'] * 0.75, P['EdgeR'] * 0.5):
        try:
            s = blank.makeFillet(r, top_edges)
            if s.isValid():
                blank = s; print('sleeve: top edge fillet R%.2f on %d edges' % (r, len(top_edges))); break
        except Exception as ex:
            print('sleeve: top fillet R%.2f failed: %s' % (r, ex))
    try:
        bed = [e for e in blank.Edges if abs(e.BoundBox.ZMax - zr) < 1e-6 and abs(e.BoundBox.ZMin - zr) < 1e-6]
        s = blank.makeChamfer(P['BedChamfer'], bed)
        if s.isValid():
            blank = s
    except Exception as ex:
        print('sleeve: bed chamfer failed: %s' % ex)
    return blank


def lip_reach():
    """How far the lips reach in over the case's sides and jack end."""
    r, c = P['TopFilletR'], P['WallClear']
    return r - (r + c) / math.sqrt(2) + P['LipPastTangent']


def cavity():
    """Module space: the side section with its lips and inner foot chamfer, taken through the curved sides
    in sections a few mm apart, clipped at the jack end by the case's plan corners offset by the clearance
    and by the same section turned to the end, for the end lip."""
    assert ENC.P['round_stop'] >= 45.0, 'the lips need the case round to reach its 45 deg point'
    zf = z_front(); c = P['WallClear']; ch = P['InnerChamfer']; ztop = z_wall_top() + 5
    r = P['TopFilletR']
    hs = lip_reach()
    zw, lc = z_wall_top(), P['LipChamfer']

    def prof(lips, y):
        # The lip underside is the case's 45 deg face over its top round, moved out by the clearance, so it
        # prints without support: x + z = k on the right, mirrored on the left.
        xl, xr = side_x(y, 'L'), side_x(y, 'R')
        il, ir = xl - c, xr + c
        kl = (xr - r) + (P['HousingTopZ'] - r) + (r + c) * math.sqrt(2)
        zl = kl - ir                                      # where it leaves the inner face
        if lips:
            tl, tr, zt, d = xl + hs, xr - hs, kl - (xr - hs), lc
        else:                                             # same vertices, the lip faces run straight up
            tl, tr, zt, d = il, ir, zl + hs, 0.0
        return [(il + ch, zf), (ir - ch, zf), (ir, zf + ch), (ir, zl), (tr, zt), (tr, zw - lc), (tr + d, zw),
                (tr + d, ztop), (tl - d, ztop), (tl - d, zw), (tl, zw - lc), (tl, zt), (il, zl), (il, zf + ch)]

    def wire(pr, y):
        return Part.makePolygon([V(x, y, z) for x, z in pr + pr[:1]])

    def run(lips, y0, y1):
        ys = side_stations(y0, y1)
        return Part.makeLoft([wire(prof(lips, y), y) for y in ys], True, True)

    # The lips end where the swoop starts, tapering out to the inner face at 45 deg in plan, so the
    # swoop is a plain 2 mm wall.
    le = P['SwoopY0']
    taper = prof(True, le)[11][0] - prof(False, le)[11][0]   # lip tip to the inner face, along X
    parts = [run(True, -10.0, le - taper),
             Part.makeLoft([wire(prof(True, le - taper), le - taper), wire(prof(False, le), le)], True, True),
             run(False, le, FAR)]
    # jack end: plan corners
    yb0, zr = P['DeviceBottomY'], z_rear()
    plan = case_face(c, zr).extrude(V(0, 0, 40))
    # jack end: the end lip is the side lip turned to the end, its 45 deg underside clear of the case's
    # end by the clearance
    zc = P['HousingTopZ'] - r
    zat = lambda y: (y - yb0) + zc + r * (math.sqrt(2) - 1) + c * math.sqrt(2)
    yi, yt = yb0 - c, yb0 + hs                            # inner face, lip tip
    end = prism_yz([(yi + ch, zf), (FAR, zf), (FAR, ztop), (yt - lc, ztop), (yt - lc, zw), (yt, zw - lc),
                    (yt, zat(yt)), (yi, zat(yi)), (yi, zf + ch)], -FAR / 2, FAR / 2)
    jack_end = parts[0].common(plan).common(end)
    return jack_end.fuse(parts[1:]).removeSplitter()


def jack_opening():
    """Round-cornered opening through the hood for the 3.5 mm plug."""
    zf = z_front(); x0, x1 = P['JackOpenX0'], P['JackOpenX1']
    pts = [V(x0, -6.0, zf), V(x1, -6.0, zf), V(x1, -6.0, z_wall_top() + 6), V(x0, -6.0, z_wall_top() + 6)]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    if not DD:   # where the plate runs on, round corners would meet it at a tangent and spoil the mesh
        face = face.makeOffset2D(-P['JackOpenR'], join=0).makeOffset2D(P['JackOpenR'], join=0)
    # the convex rounding also rounds the top corners, which are outside the part; keep the bottom flat
    return face.extrude(V(0, P['DeviceBottomY'] + lip_reach() + 1.0 + 6.0, 0))


def key_mouth():
    """(half-width, offset toward the entry) of the mouth of the slot-end pocket: the pocket keeps
    KeySnapWrap of its rim, so the mouth is the chord across the rest."""
    rp = P['KeySnapD'] / 2; a = math.radians((360 - P['KeySnapWrap']) / 2)
    return rp * math.sin(a), rp * math.cos(a)


def keyholes():
    """Entry hole for the stem head; a slot for its groove that narrows to a mouth and opens into a round
    pocket at the end, which the stem clicks into; and a recess from the front over the whole slide so
    the plate left under the head (KeyLandT) fits the groove. The head sits in the recess."""
    zf = z_front(); zr = z_rear(); zl = zr + P['KeyLandT']
    cut = []
    w, re, rp = P['KeySlotW'] / 2, P['KeyEntryD'] / 2, P['KeySnapD'] / 2
    m, ym = key_mouth(); yl = ym + P['KeySnapLead']
    for key, (sx, sy) in cup_centres().items():
        (ex, ey), s = entry_centre(key), key_slot(key)
        slot = prism(key_local(key, [(-w, -s), (w, -s), (w, -yl), (m, -ym), (m, 0), (-m, 0), (-m, -ym), (-w, -yl)]),
                     zr - 1, zf + 1)
        x0, x1, y0, y1 = key_box(key, re)
        cut += [cyl(re, ex, ey, zr - 1, zf + 1), cyl(rp, sx, sy, zr - 1, zf + 1), slot,
                cyl(re, sx, sy, zl, zf + 1), box(x0, x1, y0, y1, zl, zf + 1)]
    return cut


def cup_head_top():
    return z_rear() - P['StemSeat'] + P['GrooveH'] + P['HeadT']


def screw_centres():
    return [(P['DeviceCx'] - P['ScrewDX'], P['ScrewY']), (P['DeviceCx'] + P['ScrewDX'], P['ScrewY'])]


def stud(x, y):
    """Keyhole stud: a neck through the slot and a head with a 45 deg underside, so the bracket prints
    upright without support. The top is level with the cup heads, so the lower one clears the case."""
    zr = z_rear()
    rn, rh, c = P['StudNeckD'] / 2, P['StudHeadD'] / 2, P['StudChamfer']
    z0 = zr + P['KeyLandT'] + P['StudGap']; zt = cup_head_top()
    pts = [(0, zr - 0.5), (rn, zr - 0.5), (rn, z0), (rh, z0 + rh - rn), (rh, zt - c), (rh - c, zt), (0, zt)]
    face = Part.Face(Part.makePolygon([V(x + r, y, z) for r, z in pts + pts[:1]]))
    return Part.Solid(face.revolve(V(x, y, 0), V(0, 0, 1), 360))


def wall_bracket():
    """One-piece bracket in place of the cups, so the studs are aligned for you. It follows the plate
    outline with a notch that leaves the lever free to move toward the wall, and has two
    countersunk screw holes behind the plate. The flat rear also takes adhesive strips."""
    zr = z_rear(); t = P['BracketT']; c = P['BracketNotchClear']
    notch = box(P['LatchX0'] - P['LatchSlot'] - c, P['LatchX1'] + P['LatchSlot'] + c,
                P['LatchRootY'] - P['LatchReliefD'] / 2 - c, FAR, zr - 1, zr + 1)
    if not DD:   # the bracket runs up under the fixed tongue to carry the upper stud, clear of the arms and tab
        notch = notch.cut(tongue_box(P['LatchSlot'] - c).common(box(-FAR, FAR, -FAR, P['TongueTop'] + P['LatchSlot'] - c,
                                                                     zr - 2, zr + 2)))
    face = plan_face().makeOffset2D(-P['BracketInset'], join=0).cut(notch).Faces[0]
    face = round_face(face, P['BracketNotchR'], P['BracketNotchR'])
    body = face.extrude(V(0, 0, -t))
    front = [e for e in body.Edges if abs(e.BoundBox.ZMin - zr) < 1e-6 and abs(e.BoundBox.ZMax - zr) < 1e-6]
    body = try_fillet(body, front, (P['BracketEdgeR'], 0.6), 'bracket front edge')
    back = [e for e in body.Edges if abs(e.BoundBox.ZMax - (zr - t)) < 1e-6]
    try:
        body = body.makeChamfer(P['BracketBedChamfer'], back)
    except Exception as ex:
        print('WARN bracket bed chamfer failed: %s' % ex)
    rc, rk, sink = P['ScrewClearD'] / 2, P['ScrewCskD'] / 2, P['ScrewSink']
    zc = zr - sink - (rk - rc)                            # countersink meets the clearance hole
    cuts = []
    for x, y in screw_centres():
        cuts += [cyl(rc, x, y, zr - t - 1, zr + 1), Part.makeCone(rc, rk, rk - rc, V(x, y, zc)),
                 cyl(rk, x, y, zr - sink, zr + 1)]
    body = body.cut(cuts).removeSplitter()
    return body.fuse([stud(x, y) for x, y in cup_centres().values()]).removeSplitter()


def screw_shape(x, y):
    """Seated drywall screw in the bracket: 90 deg head (lifted 0.05 off the seat), plain shank."""
    zr = z_rear(); rk, rh = P['ScrewCskD'] / 2, P['ScrewHeadD'] / 2
    rs = P['ScrewShankD'] / 2
    ztop = zr - P['ScrewSink'] - (rk - rh) + 0.05         # head top, where the countersink is head-sized
    head = Part.makeCone(rs, rh, rh - rs, V(x, y, ztop - (rh - rs)))
    shank = cyl(rs, x, y, ztop - P['ScrewLen'], ztop - (rh - rs) + 0.01)
    return head.fuse(shank).removeSplitter()


def tooth_profile():
    """YZ profile of a tooth on the full-thickness press tab: stop face, flat, 30 deg lead-in ramp to
    just below the case rear, then a 45 deg back slope down to the plate front."""
    zt0 = z_front() - 0.01
    zt = P['BodyRearZ'] + P['ToothRise']
    ys = P['DeviceTopY'] + P['ToothClear']
    yf = ys + P['ToothFlat']
    z_r = P['BodyRearZ'] - 0.5
    yr = yf + (zt - z_r) / math.tan(math.radians(P['RampAngle']))
    yb = yr + (z_r - zt0)
    return [(ys, zt0), (ys, zt), (yf, zt), (yr, z_r), (yb, zt0)]


def latch_cut():
    """Two slots from the root out through the top edge free the lever; round stress-relief ends at the
    root; the flex zone is thinned from the front; grip grooves cross the press tab beyond the teeth. In the
    standard version two more slots and one across the end cut a fixed tongue for the upper cup out of
    the middle of the lever, which leaves a U: two arms joined by the press tab. Only the arms are thinned."""
    zf, zr = z_front(), z_rear(); g = P['LatchSlot']; y0 = P['LatchRootY']
    x0, x1 = P['LatchX0'], P['LatchX1']
    rr = P['LatchReliefD'] / 2
    cuts = []
    for xa in (x0 - g, x1):
        cuts += [box(xa, xa + g, y0, FAR, zr - 1, zf + 1), cyl(rr, xa + g / 2, y0, zr - 1, zf + 1)]
    zt = zr + P['LatchT']; ramp = P['LatchRootRamp']; ye = P['LatchFlexEndY']
    hinge = [(y0, zf), (y0 + ramp, zt), (ye, zt), (ye + ramp, zf), (ye + ramp, zf + 1), (y0, zf + 1)]
    if DD:
        cuts.append(prism_yz(hinge, x0, x1))
    else:
        cx, xt, yt = P['DeviceCx'], P['TongueX'], P['TongueTop']
        for xa in (cx - xt - g, cx + xt):                 # tongue slots
            cuts += [box(xa, xa + g, y0, yt + g, zr - 1, zf + 1), cyl(rr, xa + g / 2, y0, zr - 1, zf + 1)]
        cuts.append(box(cx - xt - g, cx + xt + g, yt, yt + g, zr - 1, zf + 1))   # across the tongue end
        for xa, xb in ((x0, cx - xt - g), (cx + xt + g, x1)):   # thin hinges in the arms only
            cuts.append(prism_yz(hinge, xa, xb))
    y = max(y for y, _ in tooth_profile()) + P['GripStart']
    r = P['GripW'] / 2; zb = zf - P['GripDepth'] + r       # axis of the round groove bottom
    for i in range(int(P['GripN'])):
        yc = y + i * P['GripPitch']
        cuts += [Part.makeCylinder(r, x1 - x0 - 3.0, V(x0 + 1.5, yc, zb), V(1, 0, 0)),
                 box(x0 + 1.5, x1 - 1.5, yc - r, yc + r, zb, zf + 1)]
    return cuts


def tongue_box(grow=0.0):
    """Plan box of the fixed tongue in the standard version's lever, grown by grow (None in the Double
    Double version)."""
    if DD:
        return None
    cx, xt = P['DeviceCx'], P['TongueX']
    return box(cx - xt - grow, cx + xt + grow, P['LatchRootY'] - 10, P['TongueTop'] + grow, z_rear() - 2, FAR)


def touch_region():
    """The blue touch point: the front of the press tab between the lever slots, from just past the
    teeth out to the top edge."""
    zf = z_front()
    blue = box(P['LatchX0'], P['LatchX1'], P['TouchY0'], FAR, zf - P['TouchInlayT'], zf)
    return blue.cut(pull_stop_parts()[0])                 # the rails over the tab edges stay black


def split_colours(printed):
    """(black, blue) bodies of the printed part."""
    reg = touch_region()
    return printed.cut(reg).removeSplitter(), printed.common(reg).removeSplitter()


def latch_teeth():
    """Two teeth on the press tab, either side of the USB-C plug."""
    prof = tooth_profile(); zt0 = prof[0][1]
    teeth = []
    for xa in (P['ToothXL'], P['ToothXR']):
        t = prism_yz(prof, xa, xa + P['ToothW'])
        sides = [e for e in t.Edges if abs(e.BoundBox.XMax - e.BoundBox.XMin) < 1e-6 and e.BoundBox.ZMax > zt0 + 0.01
                 and not (abs(e.BoundBox.ZMin - zt0) < 1e-6 and abs(e.BoundBox.ZMax - zt0) < 1e-6)]
        teeth.append(try_fillet(t, sides, (P['ToothEdgeR'],), 'tooth side edges'))
    return teeth


def stop_parts():
    """(fingers, pockets): a finger from each slot's outer wall on the bed, and the pocket it sits in
    under the lever. The pocket is open to the rear and the slot. Its roof rises at 45 deg toward the
    slot, so it prints without a bridge, and the finger top runs parallel to it, StopGap below."""
    zr, zf = z_rear(), z_front(); g = P['LatchSlot']
    y0, w, c, pen, gap = P['StopY0'], P['StopW'], P['StopClear'], P['StopPen'], P['StopGap']
    z_edge = zf - P['StopLand']                           # roof where it meets the slot
    fingers, pockets = [], []
    for edge, inward in ((P['LatchX0'], 1), (P['LatchX1'], -1)):
        x = lambda d: edge + inward * d                    # d: distance into the lever from its edge
        zt = z_edge - gap
        fingers.append(prism_xz([(x(-g - 0.5), zr), (x(pen), zr), (x(pen), zt - pen), (x(0), zt),
                                 (x(-g - 0.5), zt)], y0, y0 + w))
        d1 = pen + c
        pockets.append(prism_xz([(x(-0.01), zr - 1), (x(d1), zr - 1), (x(d1), z_edge - d1),
                                 (x(-0.01), z_edge + 0.01)], y0 - c, y0 + w + c))
    return fingers, pockets


def pull_stop_parts():
    """(rails, cuts): a rail from the plate over each edge of the press tab, flush with the front, from
    past the press-stop pockets out to the top edge, where it takes the same round as the plate; and the
    cut in the lever's front corner under it. The rail's underside rises at 45 deg toward its tip, so it
    prints without support, and the lever face runs parallel to it, PullGap below. Pulling the tab
    outward lands its top end on the rails."""
    zf = z_front(); g = P['LatchSlot']; yt = plate_top(); r = P['EdgeR']
    y0, pen, c, gap = P['PullY0'], P['PullPen'], P['StopClear'], P['PullGap']
    zt = zf - P['PullLand']                               # underside at the tip
    rails, cuts = [], []
    for edge, inward in ((P['LatchX0'], 1), (P['LatchX1'], -1)):
        x = lambda d: edge + inward * d                    # d: distance into the lever from its edge
        root = -g - 0.5
        rail = prism_xz([(x(root), zf), (x(pen), zf), (x(pen), zt), (x(root), zt - (pen - root))], y0, yt)
        xa, xb = min(x(root), x(pen)) - 1, max(x(root), x(pen)) + 1
        corner = box(xa, xb, yt - r, yt + 1, zf - r, zf + 1).cut(
            Part.makeCylinder(r, xb - xa, V(xa, yt - r, zf - r), V(1, 0, 0)))
        rails.append(rail.cut(corner))
        z0 = zt - pen - gap                               # lever face at the lever edge
        cuts.append(prism_xz([(x(-0.01), zf + 1), (x(pen + c), zf + 1), (x(pen + c), z0 + pen + c),
                              (x(-0.01), z0 - 0.01)], y0 - c, FAR))
    return rails, cuts


def pull_checks():
    """Teeth travel when the tab is pulled onto the rails, and the rail bending stress per 10 N at the
    slot wall."""
    teeth = P['DeviceTopY'] + P['ToothClear']
    d_teeth = P['PullGap'] * lever_shape(teeth) / lever_shape(plate_top())
    arm = P['LatchSlot'] + P['PullPen'] / 2
    h = P['PullLand'] + P['PullPen'] + P['LatchSlot']      # rail depth at the slot wall
    stress = 6 * 10.0 * arm / ((plate_top() - P['PullY0']) * h ** 2)
    return d_teeth, stress


def lever_shape(y):
    """Relative deflection along the lever under a load at the teeth (flex zone plus rigid tab)."""
    y0 = P['LatchRootY'] + P['LatchRootRamp'] / 2
    a = P['LatchFlexEndY'] - P['LatchRootY']
    Lt = P['DeviceTopY'] + P['ToothClear'] - y0
    s = y - y0
    if s <= a:
        return Lt * s ** 2 / 2 - s ** 3 / 6
    return Lt * a ** 2 / 2 - a ** 3 / 6 + (Lt * a - a ** 2 / 2) * (s - a)


def stop_checks():
    """Teeth travel and lever strain when the stop bottoms out; finger bending stress per 10 N."""
    yc = P['StopY0'] + P['StopW'] / 2
    teeth = P['DeviceTopY'] + P['ToothClear']
    d_teeth = P['StopGap'] * lever_shape(teeth) / lever_shape(yc)
    strain = latch_strain() * d_teeth / (P['ToothRise'] + 0.2)
    arm = P['LatchSlot'] + P['StopPen'] / 2
    h = z_front() - P['StopLand'] - P['StopGap'] - z_rear()   # finger height over the slot
    stress = 6 * 10.0 * arm / (P['StopW'] * h ** 2)
    return d_teeth, strain, stress


def latch_strain():
    """Flex zone of length a (to the middle of the end ramp) with a rigid tab out to the teeth;
    deflection at the teeth = tooth rise + 0.2 mm margin. Returns strain as a fraction."""
    a = P['LatchFlexEndY'] + P['LatchRootRamp'] / 2 - (P['LatchRootY'] + P['LatchRootRamp'] / 2)
    Lt = P['DeviceTopY'] + P['ToothClear'] - (P['LatchRootY'] + P['LatchRootRamp'] / 2)
    d = P['ToothRise'] + 0.2
    compliance = Lt * a ** 2 / 2 - a ** 3 / 6 + (Lt * a - a ** 2 / 2) * (Lt - a)
    return (P['LatchT'] / 2) * Lt * d / compliance


def ledges():
    """The case rests on a ledge along the foot of each side wall, in under its sides to a straight inner
    edge clear of the screw countersinks; where the case curves in toward the jack end the ledge narrows.
    The inner face is 45 deg, and the end where the case comes in is a 45 deg lead-in."""
    zf, zb, c = z_front(), P['BodyRearZ'], P['WallClear']; h = zb - zf
    y0, y1, reach = P['DeviceBottomY'] - c - 0.01, P['LedgeY1'], P['LedgeReach']
    run = prism_yz([(y0, zf - 0.01), (y1, zf - 0.01), (y1 - h, zb), (y0, zb)], -FAR / 2, FAR / 2)
    walls = case_face(c + P['RailT'], zf - 1).extrude(V(0, 0, h + 2))   # no further out than the sleeve
    out = []
    for edge, inward in ((P['BodyX0'], 1), (P['BodyX1'], -1)):
        x = lambda d: edge + inward * d                    # d: distance in from the case side at the USB-C end
        sec = prism_xz([(x(-20), zf - 0.01), (x(reach + h), zf - 0.01), (x(reach), zb), (x(-20), zb)], y0 - 1, y1 + 1)
        out.append(sec.common(run).common(walls))
    return out


def fillet_edges_in(shape, boxes, r, z, label, exclude=()):
    """Fillet the edges of `shape` lying at height z inside any of the XY boxes (and outside the
    `exclude` boxes); keep shape on failure."""
    sel = []
    inside = lambda b, bx: bx[0] <= b.XMin and b.XMax <= bx[1] and bx[2] <= b.YMin and b.YMax <= bx[3]
    for e in shape.Edges:
        b = e.BoundBox
        if abs(b.ZMin - z) > 1e-4 or abs(b.ZMax - z) > 1e-4 or any(inside(b, bx) for bx in exclude):
            continue
        if any(x0 <= b.XMin and b.XMax <= x1 and y0 <= b.YMin and b.YMax <= y1 for x0, x1, y0, y1 in boxes):
            sel.append(e)
    if not sel:
        print('%s: no edges' % label); return shape
    try:
        s = shape.makeFillet(r, sel)
        if s.isValid() and len(s.Solids) == 1:
            print('%s: fillet R%.2f on %d edges' % (label, r, len(sel))); return s
        print('%s: fillet result invalid, skipped' % label)
    except Exception as ex:
        print('%s: fillet failed (%s), skipped' % (label, ex))
    return shape


def _normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)


def try_fillet(shape, edges, radii, label):
    """Fillet `edges` with the first radius that gives a valid single solid; keep shape otherwise."""
    if not edges:
        print('%s: no edges' % label); return shape
    for r in radii:
        try:
            s = shape.makeFillet(r, edges)
            if s.isValid() and len(s.Solids) == 1:
                print('%s: fillet R%.2f on %d edges' % (label, r, len(edges))); return s
        except Exception as ex:
            print('%s: fillet R%.2f failed (%s)' % (label, r, ex))
    print('%s: left sharp' % label)
    return shape


def mesh_ok(shape):
    """The shape tessellates, at the export settings, to a closed mesh without self-intersections."""
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False)
    return m.isSolid() and not m.hasNonManifolds() and not m.getSelfIntersections()


def fillet_inner_top(shape):
    """Round the inner top edges of the sleeve: the inner faces where the swoop crosses them. They are
    edges between a vertical face and an upward face inside the module footprint. The lip tips, along
    the sides and the jack end, have a chamfer in the section instead."""
    zf = z_front(); x0 = P['BodyX0'] - 0.3; x1 = P['BodyX1'] + 0.3
    sel = []
    for e in shape.Edges:
        b = e.BoundBox
        if b.XMin < x0 or b.XMax > x1 or b.ZMax < zf + P['InnerChamfer'] + 0.05:
            continue                                      # (the foot chamfer edges stay as they are)
        faces = shape.ancestorsOfType(e, Part.Face)
        if len(faces) != 2:
            continue
        n = [_normal(f) for f in faces]
        vert = [abs(v.z) < 1e-6 for v in n]
        if vert.count(True) != 1:
            continue
        up = n[vert.index(False)]
        if abs(up.z - math.sqrt(0.5)) < 0.01 and abs(math.hypot(up.x, up.y) - math.sqrt(0.5)) < 0.01:
            continue                                      # the lip chamfers
        if up.z > 0.2 and not (abs(up.z - 1) < 1e-6 and abs(faces[vert.index(False)].CenterOfMass.z - zf) < 1e-6):
            sel.append(e)
    r = P['InnerEdgeR']
    try:
        s = shape.makeFillet(r, sel)
        if s.isValid() and len(s.Solids) == 1 and mesh_ok(s):
            print('inner top edges: fillet R%.2f on all %d edges' % (r, len(sel))); return s
    except Exception:
        pass
    # OCC cannot round every edge (where the swoop runs out tangentially into the plate, and around the
    # hood corners); round the ones that work on their own, together.
    ok = []
    for e in sel:
        try:
            if shape.makeFillet(r, [e]).isValid():
                ok.append(e)
        except Exception:
            pass
    print('inner top edges: %d of %d can be rounded' % (len(ok), len(sel)))
    s = try_fillet(shape, ok, (r,), 'inner top edges (subset)')
    if s is not shape and mesh_ok(s):
        return s
    chosen = []                                           # together they fail: add them one at a time
    s = shape                                             # and keep only rounds that mesh cleanly
    for e in ok:
        try:
            t = shape.makeFillet(r, chosen + [e])
            if t.isValid() and len(t.Solids) == 1 and mesh_ok(t):
                chosen.append(e); s = t
        except Exception:
            pass
    print('inner top edges: fillet R%.2f on %d of them, one at a time' % (r, len(chosen)))
    return s


def fillet_jack_opening(shape):
    """Round the mouth of the plug opening where it meets the outer end face and the hood top."""
    x0, x1, r = P['JackOpenX0'], P['JackOpenX1'], P['JackEdgeR']
    zf, ye = z_front(), y_end()
    on_side = lambda f: (f.Surface.__class__.__name__ == 'Plane' and abs(abs(_normal(f).x) - 1) < 1e-6
                         and min(abs(f.CenterOfMass.x - x0), abs(f.CenterOfMass.x - x1)) < 1e-4)
    outer, top = [], []
    for e in shape.Edges:
        b = e.BoundBox
        if (b.XMin < x0 - 0.01 or b.XMax > x1 + 0.01 or b.ZMax < zf + 0.05
                or b.YMax > P['DeviceBottomY'] + lip_reach() + P['LipChamfer'] + 0.3):   # past the end lip
            continue
        if abs(b.YMin - ye) < 1e-4 and abs(b.YMax - ye) < 1e-4:
            outer.append(e)
        elif any(on_side(f) for f in shape.ancestorsOfType(e, Part.Face)) and b.ZMin > zf + 3:
            top.append(e)
    s = try_fillet(shape, outer + top, (r, r * 0.6), 'jack opening (mouth and top)')
    if s is shape:
        s = try_fillet(shape, outer, (r, r * 0.6), 'jack opening (mouth only)')
    return s


def printed_part():
    zf = z_front()
    body = sleeve_blank().cut(cavity()).removeSplitter()
    body = fillet_inner_top(body)
    body = body.cut(jack_opening()).removeSplitter()
    body = fillet_jack_opening(body)
    body = body.cut(keyholes()).removeSplitter()
    w = P['KeyEntryD'] / 2 + 0.1
    kboxes = [key_box(key, w, w) for key in cup_centres()]
    body = fillet_edges_in(body, kboxes, P['KeyEdgeR'], zf, 'keyholes')
    if DD:
        body = body.cut(dd_pocket()).removeSplitter()
    body = body.cut(latch_cut()).removeSplitter()
    g = P['LatchSlot'] + 0.1
    body = fillet_edges_in(body, [(P['LatchX0'] - g - 2, P['LatchX1'] + g + 2, P['LatchRootY'] - 2,
                                   plate_top() + 1)], P['SlotEdgeR'], zf, 'lever slots',
                           exclude=[(P['LatchX0'] - 0.01, P['LatchX1'] + 0.01, P['LatchRootY'] - 0.01,
                                     P['LatchRootY'] + 0.01)])
    fingers, pockets = stop_parts()
    rails, corner_cuts = pull_stop_parts()
    body = body.cut(pockets + corner_cuts).removeSplitter()
    printed = body.fuse(ledges() + latch_teeth() + fingers + rails).removeSplitter()
    return printed


def cup_shape(x, y):
    """Suction cup in its keyhole: cup body, stem, groove through the keyhole land, head flange."""
    zr = z_rear(); rs = P['StemD'] / 2
    zs = zr - P['StemSeat']                               # stem shoulder, just behind the plate
    rim = zr - P['CupDepth']; zb = zs - P['StemLen']
    outside = Part.makeCone(P['CupD'] / 2, rs, zb - rim, V(x, y, rim))
    inside = Part.makeCone(P['CupD'] / 2 - P['CupWall'], rs - P['CupWall'], zb - rim - 1.5, V(x, y, rim - 0.1))
    stem = cyl(rs, x, y, zb - 0.5, zs)
    groove = cyl(P['GrooveD'] / 2, x, y, zs - 0.01, zs + P['GrooveH'] + 0.01)
    head = cyl(rs, x, y, zs + P['GrooveH'], cup_head_top())
    return outside.cut(inside).fuse([stem, groove, head]).removeSplitter()


def revolved(rz):
    """Solid of revolution about Z from a closed (r, z) profile."""
    pts = [V(r, 0, z) for r, z in rz]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).revolve(V(0, 0, 0), V(0, 0, 1), 360)


def hex_prism(af, z0, z1):
    """Hex about Z with flats facing +-Y."""
    rc = af / 2 / math.cos(math.radians(30))
    pts = [V(rc * math.cos(math.radians(a)), rc * math.sin(math.radians(a)), z0) for a in range(0, 360, 60)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, z1 - z0))


def thread_solid(z0, z1):
    """OSSM 24 mm thread about Z from z0 to z1, with a 45 deg lead-in at z1. Rebuilt from the measured
    profile: the OSSM STEP self-intersects, so it can't be cut. The ridge is trimmed by one solid of
    revolution before the core goes in; trimming the fused thread leaves it invalid."""
    rc, rr, p = P['ThreadMajorD'] / 2, P['ThreadRootD'] / 2, P['ThreadPitch']
    a = P['ThreadCrest'] / 2; b = a + (rc - rr) * math.tan(math.radians(30)); ri = rr - 0.4
    h0, h1 = z0 - 2 * p, z1 + 2 * p
    helix = Part.makeHelix(p, h1 - h0, rr); helix.translate(V(0, 0, h0))
    prof = Part.makePolygon([V(ri, 0, h0 - b), V(rr, 0, h0 - b), V(rc, 0, h0 - a), V(rc, 0, h0 + a),
                             V(rr, 0, h0 + b), V(ri, 0, h0 + b), V(ri, 0, h0 - b)])
    pipe = Part.BRepOffsetAPI.MakePipeShell(Part.Wire(helix))
    pipe.setBiNormalMode(V(0, 0, 1)); pipe.add(prof, False, False); pipe.build(); pipe.makeSolid()
    li = rc - rr + 0.3
    env = revolved([(0, z0), (rc + 1, z0), (rc + 1, z1 - li - 1), (rr - 0.3, z1), (0, z1)])
    core = revolved([(0, z0), (rr + 0.01, z0), (rr + 0.01, z1 - 0.31), (rr - 0.3, z1), (0, z1)])
    return pipe.shape().Solids[0].common(env).fuse(core).removeSplitter()


def dd_screw_head(c=0.0):
    """Screw head about its own axis Z, z 0 at the plate rear: a 45 deg cone flange flush with the rear,
    the hex, then a 45 deg chamfer from the hex down to the thread. c grows it into the pocket."""
    af = P['DDScrewHexAF'] + 2 * c; rh = af / 2 / math.cos(math.radians(30)); rs = P['DDScrewSeatD'] / 2 + c
    hs, hh, hc = P['DDScrewSeatH'], P['DDScrewHexH'], P['DDScrewChamferH']
    z0 = -1.0 if c else 0.0                               # the pocket runs out through the rear face
    seat = revolved([(0, z0), (rs - z0, z0), (rs - hs, hs), (0, hs)])
    cham = hex_prism(af, hh, hh + hc).common(revolved([(0, hh), (rh, hh), (rh - hc, hh + hc), (0, hh + hc)]))
    return seat.fuse([hex_prism(af, z0, hh), cham]).removeSplitter()


def dd_cup_socket():
    """Keyhole for the fourth cup in the screw head's rear face, open to +Y: a slot for the stem groove
    through a land as thick as the plate's, and a recess behind it for the head. The stem slides in
    from the +Y side and clicks past a mouth narrower than the groove, and the pocket wall closes that
    side once the screw is in. The slot opens away from the print flat, so it prints as an open channel."""
    w, re = P['KeySlotW'] / 2, P['KeyEntryD'] / 2
    m = dd_cup_mouth() / 2; ym = math.sqrt(w * w - m * m); yl = ym + P['DDCupSnapLead']
    zl, zh = P['KeyLandT'], cup_head_top() - z_rear() + P['DDCupHeadClear']
    slot = prism([(-m, ym), (m, ym), (w, yl), (w, 50), (-w, 50), (-w, yl)], -1, zl + 0.01)
    return cyl(w, 0, 0, -1, zl + 0.01).fuse([slot, cyl(re, 0, 0, zl, zh), box(-re, re, 0, 50, zl, zh)])


def dd_cup_mouth():
    return P['GrooveD'] - P['DDCupSnap']


def dd_screw():
    """The printed screw about its own axis Z, z 0 at the plate rear, with the print flat on -Y."""
    tip = P['PlateT'] + P['DDBossT'] + P['ThreadOut']
    s = dd_screw_head().fuse(thread_solid(P['DDScrewHexH'] - 1.0, tip)).removeSplitter()
    s = s.common(box(-50, 50, -P['ThreadFlat'], 50, -10, tip + 10)).removeSplitter()
    return s.cut(dd_cup_socket()).removeSplitter()


def dd_placed(shape):
    ax, ay = dd_axis()
    return shape.translated(V(ax, ay, z_rear()))


def dd_pocket():
    """Hex pocket from the rear for the screw head, with the screw's print flat, and the thread hole out
    through the boss top."""
    ax, ay = dd_axis(); c = P['DDPocketClear']
    hole = cyl(P['ThreadMajorD'] / 2 + P['DDHoleClear'], ax, ay, z_rear() + P['DDScrewHexH'], z_front() + P['DDBossT'] + 1)
    head = dd_screw_head(c).common(box(-50, 50, -P['ThreadFlat'] - c, 50, -10, 50))
    return dd_placed(head).fuse(hole)


def double_double_proxy():
    """OSSM Double Double 24mm Threaded (proxy of its STL): base on the boss, thread bore, neck, shaft."""
    r, rb = P['DDBaseD'] / 2, P['ThreadMajorD'] / 2 + 0.42
    body = revolved([(0, 0), (r, 0), (r, 22.0), (11.0, 33.0), (11.0, 116.75), (0, 116.75)])
    body = body.cut(Part.makeCylinder(rb, P['DDThreadDepth'] + 1, V(0, 0, -1)))
    ax, ay = dd_axis()
    return body.translated(V(ax, ay, z_front() + P['DDBossT']))


def dd_checks(printed, screw):
    ax, ay = dd_axis(); dd = double_double_proxy()
    print('CHECK screw valid %s, solids %d, %.1f cm3; thread out of the boss %.1f mm, Double Double takes %.0f' % (
        screw.isValid(), len(screw.Solids), screw.Volume / 1000, P['ThreadOut'], P['DDThreadDepth']))
    print('CHECK screw in its pocket: overlap %.4f mm3 (it seats on the pocket shoulder, %.2f mm clear at the sides)' % (
        screw.common(printed).Volume, P['DDPocketClear']))
    print('CHECK Double Double on the boss: overlap %.4f mm3, gap %.2f mm; base edge %.1f mm below the hood' % (
        dd.common(printed).Volume, dd.distToShape(printed)[0], y_end() - (ay + P['DDBaseD'] / 2)))
    print('CHECK Double Double to the screw: overlap %.4f mm3' % dd.common(screw).Volume)
    cup = cup_shape(ax, ay); rs = P['StemD'] / 2
    head = cyl(rs, ax, ay, z_rear() - P['StemSeat'] + P['GrooveH'], cup_head_top())
    print('CHECK fourth cup in the screw: overlap %.4f mm3 with the screw, %.4f with the plate; head %.2f mm thick in a %.2f mm recess' % (
        cup.common(screw).Volume, cup.common(printed).Volume, P['HeadT'],
        cup_head_top() + P['DDCupHeadClear'] - z_rear() - P['KeyLandT']))
    print('CHECK fourth cup captive: head slid 20 mm out along its slot overlaps the plate by %.0f mm3' % (
        head.translated(V(0, 20, 0)).common(printed).Volume))
    jx, jz = ENC.P['jack_axis']; face = 0.0              # J5 nose face, 0.6 inside the case end
    for r in (3.0, 4.5):
        n = 0.0
        while n < 40 and Part.makeCylinder(r, n + 0.1, V(jx, face, jz), V(0, -1, 0)).common(
                printed.fuse(dd)).Volume < 1e-6:
            n += 0.1
        print('CHECK straight 3.5 mm plug: a %.0f mm body has %.1f mm from the jack face' % (2 * r, n))
    m, rg = dd_cup_mouth(), P['GrooveD'] / 2
    print('CHECK fourth cup click: %.2f mm mouth on the %.2f mm groove, %.2f mm a side, so the slot wraps %.0f deg of the groove' % (
        m, P['GrooveD'], P['DDCupSnap'] / 2, 360 - 2 * math.degrees(math.asin(m / 2 / rg))))


def design_checks(printed, black, blue, bracket):
    """Numbers worth reading after a change: keyhole webs, latch strain, overall size, colour split,
    wall bracket fit."""
    outline = plan_face()
    for key in cup_centres():
        sx, sy = cup_centres()[key]; ex, ey = entry_centre(key)
        w = P['KeyEntryD'] / 2; zr = z_rear()              # the head recess is the widest outline
        x0, x1, y0, y1 = key_box(key, w)
        kf = flat_face([cyl(w, ex, ey, zr, zr + 1), cyl(w, sx, sy, zr, zr + 1), box(x0, x1, y0, y1, zr, zr + 1)], zr)
        web = min(kf.distToShape(e)[0] for e in outline.Edges)
        print('CHECK keyhole %s web to plate edge %.2f mm' % (key, web))
    zf = z_front()
    if SIDE:
        (ux, uy), (lx, ly) = cup_centres()['U'], cup_centres()['L']
        d = math.hypot(ux - lx, uy - ly)
        print('CHECK cups %.1f mm apart, %.1f mm between the rims of %.0f mm cups; lower rim %.1f mm below the plate end' % (
            d, d - P['CupD'], P['CupD'], y_end() - (ly - P['CupD'] / 2)))
        print('CHECK upper head recess to the lever slot reliefs %.2f mm' % (
            P['LatchRootY'] - P['LatchReliefD'] / 2 - (uy + P['KeyEntryD'] / 2)))
        h = P['BodyRearZ'] - zf; fl, fr = P['BodyX0'] + P['LedgeReach'] + h, P['BodyX1'] - P['LedgeReach'] - h
        for key in cup_centres():
            x0, x1, _, _ = key_box(key, 0.0, P['KeyEntryD'] / 2)
            print('CHECK keyhole %s head recess X %.2f to %.2f, %.2f mm clear of the ledge feet' % (
                key, x0, x1, min(x0 - fl, fr - x1)))
    print('CHECK cup head and stud top %.2f mm under the case rear, %.2f under the plate front' % (
        P['BodyRearZ'] - cup_head_top(), zf - cup_head_top()))
    m, _ = key_mouth()
    print('CHECK cup click: %.2f mm pocket keeps %.0f deg of its rim, so a %.2f mm mouth on the %.2f mm stem groove; '
          'bracket stud neck %.2f passes it with %.2f a side' % (P['KeySnapD'], P['KeySnapWrap'], 2 * m, P['GrooveD'],
                                                                 P['StudNeckD'], m - P['StudNeckD'] / 2))
    if bracket is not None:
        bb = bracket.BoundBox
        print('CHECK bracket valid %s, solids %d, %.1f x %.1f x %.1f mm, volume %.1f cm3' % (
            bracket.isValid(), len(bracket.Solids), bb.XLength, bb.YLength, bb.ZLength, bracket.Volume / 1000))
        print('CHECK bracket overlap with the plate %.4f mm3' % bracket.common(printed).Volume)
        for key, (x, y) in cup_centres().items():
            print('CHECK stud %s gap to the plate %.2f mm' % (key, stud(x, y).distToShape(printed)[0]))
        yc = P['StopY0'] + P['StopW'] / 2
        tab = P['StopGap'] * lever_shape(plate_top()) / lever_shape(yc)
        print('CHECK lever room: tab end moves %.2f mm toward the wall at the stop, bracket gives %.1f' % (tab, P['BracketT']))
        for x, y in screw_centres():
            print('CHECK screw (%.1f, %.1f): rim to lower keyhole %.2f, to lever notch %.2f' % (
                x, y, y - P['ScrewCskD'] / 2 - (P['LowCupY'] + P['KeySlotW'] / 2),
                P['LatchRootY'] - P['LatchReliefD'] / 2 - P['BracketNotchClear'] - (y + P['ScrewCskD'] / 2)))
        print('CHECK screw head top %.2f mm below the bracket face' % (P['ScrewSink'] + (P['ScrewCskD'] - P['ScrewHeadD']) / 2 - 0.05))
    strain = latch_strain()
    print('CHECK latch strain %.2f %%' % (strain * 100))
    d_teeth, s_stop, sigma = stop_checks()
    print('CHECK stop: teeth travel %.2f mm (%.2f below the case rear), lever strain %.2f %%, finger root stress %.1f MPa per 10 N'
          % (d_teeth, d_teeth - P['ToothRise'], s_stop * 100, sigma))
    print('CHECK pull stop: teeth move out %.2f mm, rail stress %.1f MPa per 10 N' % pull_checks())
    print('CHECK colour split: black valid %s (%d solid), blue valid %s (%d solid), volume %.1f + %.1f = %.1f of %.1f' % (
        black.isValid(), len(black.Solids), blue.isValid(), len(blue.Solids), black.Volume, blue.Volume,
        black.Volume + blue.Volume, printed.Volume))
    bb = printed.BoundBox
    print('CHECK printed part %.1f x %.1f x %.1f mm, valid %s, solids %d' % (
        bb.XLength, bb.YLength, bb.ZLength, printed.isValid(), len(printed.Solids)))
    e = elevation_wire_pts()
    print('CHECK swoop radius %.1f mm, %.1f deg' % (e['swoop_r'], e['swoop_deg']))
    escape_checks(printed)
    return strain


def escape_checks(printed):
    """Can the plate slide off its cups? Moved 2 mm each way in its plane, it either runs into a cup stem
    or slides along the slots. The stems sit 0.05 mm tight in their click pockets, so the overlap at rest
    is not zero."""
    cups = {k: cup_shape(x, y) for k, (x, y) in cup_centres().items()}
    rest = {k: c.common(printed).Volume for k, c in cups.items()}
    for name, (dx, dy) in (('up', (0, 2)), ('down', (0, -2)), ('left', (-2, 0)), ('right', (2, 0))):
        moved = printed.translated(V(dx, dy, 0))
        over = {k: c.common(moved).Volume for k, c in cups.items()}
        stuck = ['%s (%.0f mm3)' % (k, v) for k, v in over.items() if v > rest[k] + 1.0]
        print('CHECK plate moved 2 mm %s: %s' % (name, 'blocked by cup ' + ', '.join(stuck) if stuck else
                                                 'slides on its cups along the slots'))


# The enclosed case's outer parts in DTT-Enclosed.FCStd
MODULE_PARTS = ['Part__Feature001', 'RearCover', 'SwitchCover', 'Diffuser', 'LogoInlay', 'ButtonInlay'] + [
    'PCBMountScrew%d' % i for i in range(1, 5)]


def plug_proxies():
    """(3.5 mm plug, USB-C plug): a 9 mm plug body out of the jack end, and a USB-C overmold the size
    of the case's USB-C recess, the largest that seats, out of the USB-C end."""
    jx, jz = ENC.P['jack_axis']; ux, uz = ENC.P['usb_center']; w, h, d = ENC.P['usb_recess']
    jack = Part.makeCylinder(4.5, 60.0, V(jx, P['DeviceBottomY'], jz), V(0, -1, 0))
    usb = ENC.stadium_y(ux, uz, w - 0.2, h - 0.2, (h - 0.2) / 2 - 1e-3, P['DeviceTopY'] - d + 0.1, P['DeviceTopY'] + 60)
    return jack, usb


def module_checks(doc, printed):
    """Fit against the enclosed case as modelled: clear in place and all along the slide (the lever
    springs aside), held by the lips and the teeth, the switch cover free over its travel, the cup
    heads clear under it, and room for both plugs."""
    parts = [doc.getObject(n) for n in MODULE_PARTS]
    worst = max((o.Shape.common(printed).Volume, o.Label) for o in parts)
    print('CHECK case in place: worst overlap %.4f mm3 (%s), %d parts' % (worst[0], worst[1], len(parts)))
    case = [o.Shape for o in parts[:3]]                     # housing, rear cover, switch cover
    lever = box(P['LatchX0'], P['LatchX1'], P['LatchRootY'], FAR, z_rear() - 1, P['BodyRearZ'] + P['ToothRise'] + 1)
    if not DD:
        lever = lever.cut(tongue_box())                   # the tongue stays put
    fixed = printed.cut(lever)
    slide = [max(s.translated(V(0, d, 0)).common(fixed).Volume for s in case)
             for d in (0.5, 2, 5, 10, 20, 30, 45, 60, 80, 100, 120)]
    print('CHECK slide out to 120 mm: worst overlap %.4f mm3 outside the lever' % max(slide))
    held = case[1].translated(V(0, 0.5, 0)).common(Part.makeCompound(latch_teeth()))
    bb = held.BoundBox if held.Volume > 0 else None
    print('CHECK teeth: case pulled out 0.5 mm meets them over %.2f mm of its end face (Z %.2f to %.2f), %.1f mm3' % (
        bb.ZLength if bb else 0, bb.ZMin if bb else 0, bb.ZMax if bb else 0, held.Volume))
    lift = sum(s.translated(V(0, 0, 0.5)).common(printed).Volume for s in case)
    print('CHECK lips: case lifted 0.5 mm meets them, %.1f mm3' % lift)
    slider = doc.getObject('SwitchCover').Shape
    t = ENC.P['travel']
    for y, name in ((0, 'at rest'), (t, 'at full travel')):
        s = slider.translated(V(0, y, 0))
        print('CHECK switch cover %s: overlap %.4f mm3, gap %.2f mm' % (name, s.common(printed).Volume, s.distToShape(printed)[0]))
    rear = doc.getObject('RearCover').Shape
    screws = [o.Shape for o in parts if o.Name.startswith('PCBMountScrew')]
    print('CHECK ledges: the case rests on %.1f mm of its flat rear a side, %.2f mm clear of the screw heads' % (
        P['LedgeReach'] - ENC.P['bottom_chamfer'], min(l.distToShape(s)[0] for l in ledges() for s in screws)))
    for key, (x, y) in cup_positions().items():
        cup = cup_shape(x, y)
        print('CHECK cup %s to the case: overlap %.4f mm3, gap %.2f mm' % (key, cup.common(rear).Volume, cup.distToShape(rear)[0]))
    jack, usb = plug_proxies()
    print('CHECK USB-C: recess-size overmold overlap %.4f mm3' % usb.common(printed).Volume)
    if not DD:   # the Double Double version reports its plug room in dd_checks
        print('CHECK 3.5 mm plug: 9 mm body overlap %.4f mm3' % jack.common(printed).Volume)


def tagged(doc, name, label, shape, colour=None, transparency=0):
    o = doc.addObject('Part::Feature', name); o.Label = label; o.Shape = shape
    o.addProperty('App::PropertyString', 'Concept', TAG, 'Created by build_snap_backplate.py'); o.Concept = TAG
    if colour and App.GuiUp:
        o.ViewObject.ShapeColor = colour; o.ViewObject.Transparency = transparency
        fine_mesh(o)
    return o


def fine_mesh(o):
    """Display tessellation fine enough for small rounds on a long part: the default, relative to the
    part's size, draws R1 rounds and the thread as jagged spikes."""
    o.ViewObject.Deviation = 0.05; o.ViewObject.AngularDeflection = 5


def parameter_sheet(doc):
    sheet = doc.addObject('Spreadsheet::Sheet', 'SnapBackplateParameters')
    sheet.Label = 'Snap backplate parameters'
    sheet.set('A1', 'Parameter'); sheet.set('B1', 'Value (mm)'); sheet.set('C1', 'Basis')
    rows = dict(PARAMS)
    if not DD:
        rows.update(STANDARD)
    if SIDE:
        rows.update(SIDE_CUPS)
    for i, (k, (_, note)) in enumerate(rows.items(), 2):
        sheet.set('A%d' % i, k); sheet.set('B%d' % i, '%g' % P[k]); sheet.set('C%d' % i, note)
    return sheet


PLATE_COLOUR = (0.13, 0.13, 0.14)    # black print
TOUCH_COLOUR = (0.09, 0.42, 0.93)    # blue touch points (placeholder for the product blue)
CUP_COLOUR = (0.80, 0.84, 0.88)
SCREW_COLOUR = (0.25, 0.25, 0.27)
BRACKET_PREVIEW_COLOUR = (0.30, 0.30, 0.32)    # a touch lighter than the plate, so the two read apart


def build(variant):
    """Build one version ('standard', 'double-double' or 'side-cups') into its own copy of the DTT
    assembly, export it and save it beside this script."""
    global DD, SIDE
    DD, SIDE = variant == 'double-double', variant == 'side-cups'
    dd = DD
    P.clear(); P.update(BASE)
    if not dd:
        P.update({k: v for k, (v, _) in STANDARD.items()})
    if SIDE:
        P.update({k: v for k, (v, _) in SIDE_CUPS.items()})
    stem = 'DTT-Snap-Backplate' + {'double-double': '-Double-Double', 'side-cups': '-Side-Cups'}.get(variant, '')
    doc = App.openDocument(MODULE)
    o = doc.getObject('ExplodedView')   # the case's exploded copies
    if o is not None:
        o.Visibility = False
    printed = printed_part()
    black, blue = split_colours(printed)
    bracket = None if dd or SIDE else wall_bracket()
    design_checks(printed, black, blue, bracket)
    module_checks(doc, printed)
    group = doc.addObject('App::Part', 'SnapBackplate'); group.Label = 'Snap backplate'
    parameter_sheet(doc)
    bodies = [tagged(doc, 'SnapBackplatePrinted', 'Snap backplate - printed, black', black, PLATE_COLOUR),
              tagged(doc, 'SnapBackplateTouch', 'Snap backplate - printed, blue touch point', blue, TOUCH_COLOUR)]
    for o in bodies:
        group.addObject(o)
    for key, (x, y) in cup_positions().items():
        group.addObject(tagged(doc, 'SnapCup' + key, 'Suction cup %s (proxy)' % key, cup_shape(x, y), CUP_COLOUR, 35))
    if dd:
        screw = dd_screw()
        dd_checks(printed, dd_placed(screw))
        group.addObject(tagged(doc, 'SnapDDScrew', 'Double Double screw - printed, black', dd_placed(screw),
                               PLATE_COLOUR))
        group.addObject(tagged(doc, 'SnapDoubleDouble', 'OSSM Double Double 24mm Threaded (proxy)',
                               double_double_proxy(), CUP_COLOUR))
    elif bracket is not None:
        # the bracket and its screws take the place of the cups, so they start hidden
        br = tagged(doc, 'SnapWallBracket', 'Wall bracket (in place of the cups; screws or adhesive strips)',
                    bracket, PLATE_COLOUR)
        br.Visibility = False
        group.addObject(br)
        for key, (x, y) in zip(('L', 'R'), screw_centres()):
            o = tagged(doc, 'SnapScrew' + key, 'Wall screw %s (bracket, proxy)' % key, screw_shape(x, y), SCREW_COLOUR)
            o.Visibility = False
            group.addObject(o)
    doc.recompute()
    os.makedirs(IMAGES, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    if App.GuiUp:
        import ImportGui                                  # keeps the two bodies and their colours
        ImportGui.export(bodies, os.path.join(OUT, stem + '.step'))
    else:
        Part.makeCompound([black, blue]).exportStep(os.path.join(OUT, stem + '.step'))
    meshes = [(printed, ''), (black, '-Black'), (blue, '-Blue')]
    if bracket is not None:
        bracket.exportStep(os.path.join(OUT, stem + '-Wall-Bracket.step'))
        meshes.append((bracket, '-Wall-Bracket'))
    if dd:   # the screw prints on its side, on its flat
        lying = screw.rotated(V(0, 0, 0), V(1, 0, 0), 90).translated(V(0, 0, P['ThreadFlat']))
        lying.exportStep(os.path.join(OUT, stem + '-Screw.step'))
        meshes.append((lying, '-Screw'))
    import MeshPart
    for shape, suffix in meshes:
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False).write(
            os.path.join(OUT, stem + suffix + '.stl'))
    if App.GuiUp:
        pic = stem.replace('DTT-', '')
        render(doc, pic)
        if dd:
            render_double_double(doc, pic)
        elif SIDE:
            render_side_cups(doc, pic)
        else:
            render_bracket(doc)
    doc.saveAs(os.path.join(HERE, stem + '-Concept.FCStd'))
    return doc


def main():
    variants = os.environ.get('SNAP_VARIANTS', 'standard,double-double,side-cups').split(',')
    return [build(v.strip()) for v in variants]


def _rgb_uint(r, g, b):
    return (int(r * 255) << 24) | (int(g * 255) << 16) | (int(b * 255) << 8)


def render(doc, pic):
    import FreeCADGui as Gui
    pv = App.ParamGet('User parameter:BaseApp/Preferences/View')
    pv.SetBool('ShowNaviCube', False); pv.SetBool('ShowAxisCross', False)
    view = Gui.getDocument(doc.Name).ActiveView
    printed = doc.getObject('SnapBackplatePrinted')
    housing = doc.getObject('Cover___V3_v5')
    cups = [doc.getObject('SnapCup' + k) for k in cup_positions()]
    extras = [o for o in (doc.getObject('SnapDDScrew'), doc.getObject('SnapDoubleDouble')) if o is not None]
    proxy = doc.getObject('SnapDoubleDouble')
    out = lambda name: os.path.join(IMAGES, '%s-%s.png' % (pic, name))
    housing.Visibility = True
    tops = [o for o in doc.RootObjects if o.TypeId == 'App::Part']
    saved = {o.Name: o.Visibility for o in tops}
    # standard previews (same set as the baseline concept)
    view.viewIsometric(); view.fitAll()
    view.saveImage(out('Assembled'), 1400, 1400, 'White')
    for o in tops:
        o.Visibility = o.Name == 'SnapBackplate'
    housing.Visibility = False
    view.viewIsometric(); view.fitAll()
    view.saveImage(out('Front'), 1400, 1400, 'White')
    view.setCameraOrientation(App.Rotation(V(0, 1, 0), 180)); view.fitAll()
    view.saveImage(out('Rear'), 1400, 1400, 'White')
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    housing.Visibility = True
    view.viewRight(); view.fitAll()
    view.saveImage(out('Side'), 1400, 1400, 'White')
    # hero renders: wall-mounted orientation (USB-C end up), front three-quarter from above right,
    # shaded without edge lines, soft gradient backdrop
    pv.SetBool('Gradient', True); pv.SetBool('Simple', False)
    pv.SetUnsigned('BackgroundColor2', _rgb_uint(0.93, 0.93, 0.95))
    pv.SetUnsigned('BackgroundColor3', _rgb_uint(0.70, 0.71, 0.75))
    case = [doc.getObject(n) for n in MODULE_PARTS]
    for o in [printed, doc.getObject('SnapBackplateTouch')] + cups + extras + case:
        if 'Shaded' in o.ViewObject.getEnumerationsOfProperty('DisplayMode') if hasattr(o.ViewObject, 'DisplayMode') else []:
            o.ViewObject.DisplayMode = 'Shaded'
    cam = App.Rotation(V(0, 1, 0), 36).multiply(App.Rotation(V(1, 0, 0), -20))
    view.setCameraOrientation(cam); view.fitAll()
    view.saveImage(out('Hero'), 1600, 1600, 'Current')
    for o in tops:
        o.Visibility = o.Name == 'SnapBackplate'
    housing.Visibility = False
    hidden = cups + ([proxy] if proxy else [])
    for o in hidden:
        o.Visibility = False
    view.setCameraOrientation(cam); view.fitAll()
    view.saveImage(out('Hero-Part'), 1600, 1600, 'Current')
    for o in hidden:
        o.Visibility = True
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    housing.Visibility = True


def preview(doc, fname, names, cam, moves=None, turned=False, colours=None):
    """Shaded preview of copies of some objects, in a document of their own, on the hero backdrop set up
    by render(). moves offsets named objects; turned turns the scene to the rear, since a camera turned
    to the rear renders dim."""
    import FreeCADGui as Gui
    turn = App.Placement(V(0, 0, 0), App.Rotation(V(0, 1, 0), 180),
                         doc.getObject('SnapBackplatePrinted').Shape.BoundBox.Center).toMatrix()
    tmp = App.newDocument('SnapPreview')
    for n in names:
        src = doc.getObject(n); s = src.Shape.copy()
        if moves and n in moves:
            s.translate(moves[n])
        if turned:
            s.transformShape(turn)
        o = tmp.addObject('Part::Feature', n); o.Shape = s
        o.ViewObject.ShapeAppearance = src.ViewObject.ShapeAppearance
        if colours and n in colours:
            o.ViewObject.ShapeColor = colours[n]
        o.ViewObject.Transparency = src.ViewObject.Transparency
        o.ViewObject.DisplayMode = 'Shaded'; fine_mesh(o)
    tmp.recompute()
    Gui.ActiveDocument = Gui.getDocument(tmp.Name)
    view = Gui.getDocument(tmp.Name).ActiveView
    # fit again once the new view is up, or it can keep the clipping planes of the last scene
    view.setCameraOrientation(cam); view.fitAll(); Gui.updateGui(); view.fitAll(); Gui.updateGui()
    view.saveImage(os.path.join(IMAGES, fname), 1600, 1600, 'Current')
    App.closeDocument(tmp.Name)


def render_bracket(doc):
    plate = ['SnapBackplatePrinted', 'SnapBackplateTouch']
    bracket = ['SnapWallBracket', 'SnapScrewL', 'SnapScrewR']
    lift = V(0, P['TopSlot'], 30)    # plate lifted to the keyhole entries and pulled off the studs
    grey = {'SnapWallBracket': BRACKET_PREVIEW_COLOUR}
    preview(doc, 'Snap-Backplate-Wall-Bracket.png', bracket,
            App.Rotation(V(0, 1, 0), 36).multiply(App.Rotation(V(1, 0, 0), -20)), colours=grey)
    preview(doc, 'Snap-Backplate-Bracket-Exploded.png', bracket + plate,
            App.Rotation(V(0, 1, 0), 55).multiply(App.Rotation(V(1, 0, 0), -15)),
            moves={n: lift for n in plate}, colours=grey)
    preview(doc, 'Snap-Backplate-Bracket-Rear.png', bracket + plate,
            App.Rotation(V(0, 1, 0), -30).multiply(App.Rotation(V(1, 0, 0), -20)), turned=True, colours=grey)


def render_double_double(doc, pic):
    """The screw from the side, lying on its print flat; the screw, plate and Double Double pulled apart
    along the screw axis; and the screw, with the fourth cup, going into its pocket from the wall side."""
    grey = {'SnapDDScrew': BRACKET_PREVIEW_COLOUR}
    names = ['SnapBackplatePrinted', 'SnapBackplateTouch', 'SnapDDScrew', 'SnapDoubleDouble']
    apart = {'SnapDDScrew': V(0, 0, -45), 'SnapDoubleDouble': V(0, 0, 30)}
    preview(doc, pic + '-Screw.png', ['SnapDDScrew'],
            App.Rotation(V(0, 1, 0), 70).multiply(App.Rotation(V(1, 0, 0), -18)), colours=grey)
    preview(doc, pic + '-Exploded.png', names,
            App.Rotation(V(0, 1, 0), 50).multiply(App.Rotation(V(1, 0, 0), -15)), moves=apart, colours=grey)
    preview(doc, pic + '-Exploded-Rear.png', names[:3] + ['SnapCupD'],
            App.Rotation(V(0, 1, 0), -35).multiply(App.Rotation(V(1, 0, 0), -20)),
            moves={'SnapDDScrew': V(0, 0, -40), 'SnapCupD': V(0, 30, -40)}, turned=True, colours=grey)


def render_side_cups(doc, pic):
    """The plate from the wall side with each cup at its entry, pulled back: the lower one goes in on the
    left and slides right, the upper one goes in on the right and slides left (as seen from the front)."""
    names = ['SnapBackplatePrinted', 'SnapBackplateTouch', 'SnapCupL', 'SnapCupU']
    cam = App.Rotation(V(0, 1, 0), -30).multiply(App.Rotation(V(1, 0, 0), -20))
    back = 30.0
    r = cam.multVec(V(1, 0, 0))
    c = back * r.z / r.x              # cancels the sideways shift the pull-back makes in this view, so each
    moves = {}                        # cup shows right over its entry (the turn to the rear flips X)
    for key in ('L', 'U'):
        (sx, sy), (ex, ey) = cup_centres()[key], entry_centre(key)
        moves['SnapCup' + key] = V(ex - sx + c, ey - sy, -back)
    preview(doc, pic + '-Exploded-Rear.png', names, cam, moves=moves, turned=True)


if __name__ == '__main__' or True:
    DOCUMENT = main()
