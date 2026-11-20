"""Build the DTT v2 assembly: board, screen, battery, case, switch cover and the slide-in cradle.

Headless FreeCAD 1.0+:
    FreeCADCmd build_dtt_v2_assembly.py
It writes DTT-v2.FCStd and DTT-v2.step beside this script, the printed parts in parts/ (STEP and
STL) and render meshes plus scene files in build/ (git-ignored), which render_scenes.py turns into
images/.

Device coordinates: X across the board (right when you face the screen with the top end up), Y along
it (bottom end, toward the toy, at Y 0; top end at Y 64), Z out of the front face. The PCB front face
is Z 0, its back face Z -1.6. The wall is at -Z.

Board geometry comes from hardware/pcb/kicad-rev5/dtt_v2 (board 38 x 64, R3): a KiCad STEP export
in parts/DTT-v2-Board.step and the part positions below, which match build_dtt_v2.py PLACE.
"""
import math
import os
import sys
import json

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, 'parts')
BUILD = os.path.join(HERE, 'build')
BOARD_STEP = os.environ.get('DTT_BOARD_STEP', os.path.join(PARTS, 'DTT-v2-Board.step'))
V = App.Vector
FAR = 400.0

# name: (value, basis)
PARAMS = {
    # board (hardware/pcb/kicad-rev5/dtt_v2)
    'PcbW': (38.0, 'board'), 'PcbL': (64.0, 'board'), 'PcbT': (1.6, 'board'), 'PcbR': (3.0, 'board corners'),
    'Holes': ([(-16.0, 2.5), (16.0, 2.5), (-16.0, 61.5), (16.0, 61.5)], 'board: M2 case-screw holes, 2.2 mm'),
    # screen: bare 2.0 in 240x320 IPS panel with CST816D touch; glass outline assumed until a sample is measured
    'GlassW': (36.0, 'assumed'), 'GlassL': (52.0, 'assumed'), 'GlassT': (2.3, 'assumed: LCD 1.3 + touch glass 1.0'),
    'GlassY0': (5.0, 'design: glass bottom edge, 0.2 clear of the lower bosses; the FPC wraps round the board end below it'),
    'GlassFoam': (0.5, 'design: tape under the glass, over the trimmed USB-C shield legs'),
    'ActiveW': (30.6, 'panel: 240 x 0.1275 mm'), 'ActiveL': (40.8, 'panel: 320 x 0.1275 mm'),
    'ActiveBottom': (8.0, 'assumed: driver-IC border at the FPC end'),
    'FpcW': (13.0, 'assumed: tail into the 21-pin connector'),
    # ToF
    'TofXY': ((10.0, 2.3), 'board: U5, front, bottom right'), 'TofBody': ((4.4, 2.4, 1.0), 'VL53L4CD datasheet: 4.4 x 2.4 x 1.0'),
    'TofWin': ((5.4, 2.8), 'design: pill window at the bezel underside, long axis along the sensor'),
    'TofWinTaper': (20.0, 'design: window walls open outward, deg'),
    'TofApert': (1.3, 'estimate: emitter and receiver within 1.3 of the sensor centre, 0.3 radius'),
    'TofCone': (12.0, 'design: checked half-angle, the 18 deg field (9 deg half) plus 3 deg margin'),
    # battery: rev 4 uses a 702035 LiPo; a 502035 drops the case by 2 mm
    'BatT': (7.0, 'rev 4 battery 702035'), 'BatW': (20.0, 'rev 4 battery'), 'BatL': (35.0, 'rev 4 battery'),
    'BatY0': (14.5, 'design: centred on the board length, clear of the FPC connector and the top end'),
    'BatZ': (-5.0, 'design: battery front face, behind the ESP32 module and the USB-C shell'),
    # case
    'Wall': (1.75, 'design: 0.25 beside the board'),
    'CaseX': (21.0, 'design: half width = board 19 + 0.25 + wall'),
    'CaseY0': (-3.1, 'design: bottom end face; 1.35 inside for the screen FPC bend'),
    'CaseY1': (66.0, 'design: top end face'),
    'CaseR': (4.0, 'design: plan corners, board R3 + 1'),
    'TopZ': (3.9, 'design: bezel top, 1.0 mm plate over the glass with 0.1 clearance'),
    'TopFillet': (1.2, 'design: same round as the rev 4 enclosed case'),
    'SeamZ': (-1.6, 'design: at the PCB back face, so every side opening is in the rear cover'),
    'RearZ': (-13.5, 'design: battery back -12.0, 0.3 clearance, 1.2 floor'),
    'Floor': (1.2, 'design'),
    'BottomChamfer': (0.8, 'design'),
    'WindowMargin': (0.4, 'design: bezel opening past the active area'),
    'WindowChamfer': (0.6, 'design: 45 deg on the bezel opening'),
    'BossD': (4.6, 'design: screw bosses in the front shell and posts in the rear cover'),
    'PilotD': (1.6, 'design: M2 self-tapping pilot'), 'PilotDepth': (3.5, 'design: leaves 0.4 under the top'),
    'ScrewClearD': (2.4, 'design'), 'CskD': (4.4, 'design: 82 deg countersink for an M2 flat head'),
    'LipT': (0.85, 'design: rear cover lip inside the front shell wall'), 'LipH': (1.5, 'design'),
    'LipClear': (0.15, 'design'),
    'RimW': (1.2, 'design: PCB rests on a rim beside the glass, X 18.05 to 19.25'),
    # side openings (device Y / Z)
    'UsbY': (28.0, 'board: J1'), 'UsbZ': (-3.23, 'board: J1 shell centre'), 'UsbWH': ((9.6, 3.8), 'design: HRO plug 8.3 x 2.6 + 0.6'),
    'Ph6Y': (28.5, 'board: J4'), 'Ph6Z': (-4.6, 'board: J4 body centre'), 'Ph6WH': ((15.0, 7.2), 'design: PHR-6 housing 13 x 5'),
    'Sw2XY': ((-14.0, 42.5), 'board: SW2 BOOT, a top-push TS-1187A on the board back, plunger toward the rear cover'),
    'Sw2Body': (5.1, 'TS-1187A'), 'Sw2H': (1.5, 'TS-1187A: board to plunger top'),
    'PinBoreD': (1.5, 'design: paperclip bore, prints about 1.2 as a vertical hole'),
    'PinCskD': (2.5, 'design: lead-in on the outer face'),
    'PinTubeOD': (3.4, 'design: guide tube up from the floor so the clip lands on the plunger'),
    'PinTubeGap': (1.0, 'design: tube top to the plunger'),
    'IconInlayT': (0.6, 'design: white reset icon inlaid in the outer face, 2 layers at 0.30'),
    'IconR': (2.9, 'design: icon ring centre radius'), 'IconLine': (1.0, 'design: line width for a 0.6 nozzle'),
    'IconArc': ((45.0, 255.0), 'design: ring tail angle and clockwise sweep, seen from the back'),
    'IconHead': ((2.8, 1.9), 'design: arrowhead base and length'),
    # slide switch SW1 and its printed cover (blue touch point), as on the rev 4 enclosed case
    'SwBody': (((14.9, 18.5), (9.5, 18.5), (-5.1, -1.6)), 'board: JS102011JAQN, X / Y / Z ranges'),
    'ActY': (15.55, 'board: actuator centre as drawn on the fab layer; the other detent is 3.1 lower'),
    'ActTravel': (3.1, 'board'), 'ActW': (1.5, 'board'), 'ActZ': ((-4.1, -2.6), 'estimate'), 'ActTipX': (20.7, 'board'),
    'GripL': (5.0, 'design'), 'GripZ': ((-4.8, -2.3), 'design: window height'), 'GripProud': (0.4, 'design'),
    'SliderClear': (0.15, 'design'), 'FlangeT': (0.7, 'design: between the switch body (X 18.5) and the wall'),
    'FlangeMargin': (0.9, 'design: flange past the window'),
    # cradle: plate the case slides into, held by lips over its top round, a hood over the bottom end and
    # a release lever whose teeth catch the top end; two suction cups in keyholes on the centreline
    'RestGap': (1.0, 'design: plate front to the case rear'), 'PlateT': (6.0, 'design'),
    'WallClear': (0.2, 'design'), 'RailT': (2.0, 'design'),
    'WallTopAbove': (1.2, 'design: wall top above the bezel'), 'HookEngage': (0.6, 'design: lip reach over the case'),
    'LipChamfer': (0.6, 'design'), 'InnerChamfer': (1.0, 'design: 45 deg foot inside the walls'),
    'LowWallH': (3.5, 'design: wall height where the side ports are, below their openings'),
    'PortGapR': ((8.8, 35.0), 'design: right wall low from the switch window to past USB-C'),
    'SwitchGroove': (0.3, 'design: clearance round the switch grip in its groove along the right wall'),
    'PortGapL': ((19.0, 38.0), 'design: left wall low over the PH6 port'),
    'SwoopY0': (50.0, 'design: wall top starts to fall'), 'SwoopY1': (63.0, 'design: wall reaches the plate'),
    'PlateTop': (83.0, 'design: 17 past the case top end, room for the press tab'),
    'LowCupY': (14.0, 'design: lower cup snap point; its disc ends 1.8 inside the plate bottom'),
    'CupEntry': ((12.0, -12.0), 'design: entry offset from the snap, lower / upper cup. The lower cup slides down '
                 'to lock and the upper one up, so on the wall the plate is held both ways without the clicks'),
    'TongueX': (9.4, 'design: half width of the fixed tongue inside the lever that carries the upper cup '
                '(entry 15.6 plus 1.6 webs)'),
    'TongueTop': (72.0, 'design: tongue free end, just under the press tab'), 'TongueWeb': (1.6, 'design'),
    'CornerR': (6.0, 'design'),
    'EdgeR': (1.0, 'design'), 'BedChamfer': (0.6, 'design'),
    'KeyEntryD': (15.6, 'rev 4'), 'KeySlotW': (8.9, 'rev 4'), 'KeySnapD': (8.4, 'rev 4'), 'KeySnapWrap': (190.0, 'rev 4'),
    'KeySnapLead': (1.5, 'rev 4'), 'KeyLandT': (2.4, 'rev 4'),
    'CupD': (35.0, 'rev 4'), 'CupDepth': (14.0, 'rev 4'), 'StemD': (15.0, 'rev 4'), 'StemLen': (3.0, 'rev 4'),
    'GrooveD': (8.5, 'rev 4'), 'GrooveH': (2.5, 'rev 4'), 'HeadT': (3.0, 'rev 4'), 'StemSeat': (0.1, 'rev 4'),
    'LatchX': (15.3, 'design: lever half width; the arms run from the tongue slots out to here, 0.2 short of the ledges'), 'LatchRootY': (44.0, 'design'), 'LatchSlot': (1.5, 'design'),
    'LatchReliefD': (2.5, 'design'), 'LatchT': (2.0, 'design: flex zone, thinned from the front'),
    'LatchRootRamp': (6.0, 'design'), 'LatchFlexEndY': (62.0, 'design'),
    'ToothX': (((-15.0, -11.2), (11.2, 15.0)), 'design: a tooth on each lever arm'),
    'ToothRise': (3.0, 'design: catches the top end face above its rear chamfer'), 'ToothClear': (0.2, 'design'),
    'ToothFlat': (1.0, 'design'), 'RampAngle': (30.0, 'design'),
    'GripN': (4, 'design'), 'GripPitch': (2.0, 'design'), 'GripW': (1.0, 'design'), 'GripDepth': (0.9, 'design'),
    'TouchInlayT': (0.6, 'design: blue inlay'),
    'LedgeReach': (3.0, 'design: ledge under each side of the case'), 'LedgeY1': (62.0, 'design'),
}
P = {k: v for k, (v, _) in PARAMS.items()}

BLACK = (0.16, 0.16, 0.17)
BLUE = (0.09, 0.42, 0.93)
WHITE = (0.93, 0.93, 0.92)
PCB = (0.12, 0.35, 0.22)
GLASS = (0.05, 0.05, 0.07)
SCREEN = (0.14, 0.22, 0.42)
BATTERY = (0.72, 0.72, 0.75)
CUP = (0.80, 0.84, 0.88)
METAL = (0.75, 0.75, 0.78)


# ----------------------------------------------------------------------------- helpers
def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    if min(x1 - x0, y1 - y0, z1 - z0) <= 1e-6:
        raise ValueError('box with no size: x %s..%s y %s..%s z %s..%s' % (x0, x1, y0, y1, z0, z1))
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(d, x, y, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(x, y, z0))


def rounded_rect(x0, y0, x1, y1, r, z=0.0):
    r = min(r, (x1 - x0) / 2 - 1e-3, (y1 - y0) / 2 - 1e-3)
    k = r * (1 - math.sqrt(0.5))
    e = [Part.LineSegment(V(x0 + r, y0, z), V(x1 - r, y0, z)),
         Part.Arc(V(x1 - r, y0, z), V(x1 - k, y0 + k, z), V(x1, y0 + r, z)),
         Part.LineSegment(V(x1, y0 + r, z), V(x1, y1 - r, z)),
         Part.Arc(V(x1, y1 - r, z), V(x1 - k, y1 - k, z), V(x1 - r, y1, z)),
         Part.LineSegment(V(x1 - r, y1, z), V(x0 + r, y1, z)),
         Part.Arc(V(x0 + r, y1, z), V(x0 + k, y1 - k, z), V(x0, y1 - r, z)),
         Part.LineSegment(V(x0, y1 - r, z), V(x0, y0 + r, z)),
         Part.Arc(V(x0, y0 + r, z), V(x0 + k, y0 + k, z), V(x0 + r, y0, z))]
    return Part.Face(Part.Wire([s.toShape() for s in e]))


def rrect_prism(x0, y0, x1, y1, r, z0, z1):
    return rounded_rect(x0, y0, x1, y1, r, z0).extrude(V(0, 0, z1 - z0))


def prism(points_xy, z0, z1):
    pts = [V(x, y, z0) for x, y in points_xy]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, z1 - z0))


def prism_xz(points_xz, y0, y1):
    pts = [V(x, y0, z) for x, z in points_xz]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, y1 - y0, 0))


def prism_yz(points_yz, x0, x1):
    pts = [V(x0, y, z) for y, z in points_yz]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))


def stadium_x(cy, cz, w, h, r, x0, x1):
    """Rounded rectangle in the YZ plane (w along Y, h along Z), extruded along X from x0 to x1."""
    f = rounded_rect(cy - w / 2, cz - h / 2, cy + w / 2, cz + h / 2, r)
    f.rotate(V(0, 0, 0), V(0, 0, 1), 90)       # XY -> (-Y)X : x becomes y
    f.rotate(V(0, 0, 0), V(0, 1, 0), 90)       # then into the YZ plane
    # after the two rotations the face lies in the plane x = 0 with y -> y, z -> z (checked by bbox)
    b = f.BoundBox
    f.translate(V(-b.XMin, cy - (b.YMin + b.YMax) / 2, cz - (b.ZMin + b.ZMax) / 2))
    f.translate(V(x0, 0, 0))
    return f.extrude(V(x1 - x0, 0, 0))


def yz_rect(cy, cz, w, h, r, x0, x1):
    """Rounded rectangle in the YZ plane built directly, extruded along X."""
    f = rounded_rect(cy - w / 2, cz - h / 2, cy + w / 2, cz + h / 2, r)   # in XY: x = Y, y = Z
    m = App.Matrix()
    # map (x, y, z) -> (0, x, y): rotate about the axis (1,1,1) by 120 deg
    m.A11, m.A12, m.A13 = 0, 0, 1
    m.A21, m.A22, m.A23 = 1, 0, 0
    m.A31, m.A32, m.A33 = 0, 1, 0
    f = f.transformGeometry(m)
    f.translate(V(x0, 0, 0))
    return f.extrude(V(x1 - x0, 0, 0))


def try_fillet(shape, edges, radii, label):
    if not edges:
        print('%s: no edges' % label)
        return shape
    for r in radii:
        try:
            s = shape.makeFillet(r, edges)
            if s.isValid() and len(s.Solids) == 1:
                print('%s: fillet R%.2f on %d edges' % (label, r, len(edges)))
                return s
        except Exception as ex:
            print('%s: fillet R%.2f failed (%s)' % (label, r, ex))
    print('%s: left sharp' % label)
    return shape


def try_chamfer(shape, edges, d, label):
    try:
        s = shape.makeChamfer(d, edges)
        if s.isValid() and len(s.Solids) == 1:
            return s
    except Exception as ex:
        print('%s: chamfer failed (%s)' % (label, ex))
    return shape


def edges_at_z(shape, z, tol=1e-4):
    return [e for e in shape.Edges if abs(e.BoundBox.ZMin - z) < tol and abs(e.BoundBox.ZMax - z) < tol]


def round_face(face, concave, convex):
    if concave:
        face = face.makeOffset2D(concave, join=0).makeOffset2D(-concave, join=0)
    if convex:
        face = face.makeOffset2D(-convex, join=0).makeOffset2D(convex, join=0)
    return face


def flat_face(solids, z):
    s = solids[0].fuse(solids[1:]).removeSplitter() if len(solids) > 1 else solids[0]
    return [f for f in s.Faces if abs(f.CenterOfMass.z - z) < 1e-6 and abs(f.normalAt(0, 0).z) > 0.99][0]


def case_outline(z0, z1, grow=0.0):
    return rrect_prism(-P['CaseX'] - grow, P['CaseY0'] - grow, P['CaseX'] + grow, P['CaseY1'] + grow,
                       P['CaseR'] + grow, z0, z1)


# ----------------------------------------------------------------------------- board and stack
def load_board():
    """KiCad STEP export (x = KiCad x, y = -KiCad y, front face at z 1.51) into device coordinates."""
    import Import
    doc = App.newDocument('board')
    Import.insert(BOARD_STEP, doc.Name)
    shapes = [o.Shape for o in doc.Objects if hasattr(o, 'Shape') and not o.InList]
    s = shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)
    sol = sorted(s.Solids, key=lambda x: -x.Volume)
    board = sol[0]
    zf = board.BoundBox.ZMax
    s.translate(V(-119.0, 164.0, -zf))
    App.closeDocument(doc.Name)
    pcb = [x for x in s.Solids if abs(x.Volume - board.Volume) < 1e-6][0]
    others = Part.makeCompound([x for x in s.Solids if abs(x.Volume - board.Volume) > 1e-6])
    return pcb, others


def sw2_proxy(zb):
    (hx, hy), b, h = P['Sw2XY'], P['Sw2Body'] / 2, P['Sw2H']
    return box(hx - b, hx + b, hy - b, hy + b, zb - h + 0.35, zb).fuse(box(hx - 0.9, hx + 0.9, hy - 0.9, hy + 0.9,
                                                                         zb - h, zb - h + 0.36))


def pin_geom():
    (hx, hy) = P['Sw2XY']
    plunger = -P['PcbT'] - P['Sw2H']
    return hx, hy, plunger, plunger - P['PinTubeGap']


def reset_icon():
    """A clockwise open-circle arrow round the BOOT pin hole, as seen from the back (X mirrored)."""
    hx, hy, _, _ = pin_geom()
    zr = P['RearZ']
    r, lw = P['IconR'], P['IconLine']
    ro, ri = r + lw / 2, r - lw / 2
    t0, sweep = P['IconArc']
    t1 = t0 - sweep
    base, length = P['IconHead']
    to_dev = lambda sx, sy: V(hx - sx, hy + sy, zr)
    pol = lambda rad, deg: (rad * math.cos(math.radians(deg)), rad * math.sin(math.radians(deg)))
    tm = (t0 + t1) / 2
    arc_o = Part.Arc(to_dev(*pol(ro, t0)), to_dev(*pol(ro, tm)), to_dev(*pol(ro, t1))).toShape()
    arc_i = Part.Arc(to_dev(*pol(ri, t1)), to_dev(*pol(ri, tm)), to_dev(*pol(ri, t0))).toShape()
    band = Part.Face(Part.Wire([arc_o, Part.LineSegment(to_dev(*pol(ro, t1)), to_dev(*pol(ri, t1))).toShape(), arc_i,
                                Part.LineSegment(to_dev(*pol(ri, t0)), to_dev(*pol(ro, t0))).toShape()]))
    a = math.radians(t1)
    n, tg = (math.cos(a), math.sin(a)), (math.sin(a), -math.cos(a))      # radial, clockwise tangent
    bx, by = r * n[0], r * n[1]
    pts = [(bx + n[0] * base / 2, by + n[1] * base / 2), (bx + tg[0] * length, by + tg[1] * length),
           (bx - n[0] * base / 2, by - n[1] * base / 2)]
    # overlap the band a little so the head and the ring fuse into one face
    pts = [(x - tg[0] * 0.05, y - tg[1] * 0.05) if i != 1 else (x, y) for i, (x, y) in enumerate(pts)]
    head = Part.Face(Part.makePolygon([to_dev(*q) for q in pts] + [to_dev(*pts[0])]))
    face = band.fuse(head).removeSplitter()
    return face.extrude(V(0, 0, P['IconInlayT']))


def board_proxies():
    """Boxes for the parts whose 3D models are not in the KiCad export."""
    zb = -P['PcbT']
    (sx0, sx1), (sy0, sy1), (sz0, sz1) = P['SwBody']
    az0, az1 = P['ActZ']
    ay = P['ActY']
    parts = {
        'J1 USB-C': box(10.2, 19.15, 24.3, 31.7, zb - 3.26, zb),
        'J2 battery connector': box(-17.5, -10.1, 6.4, 14.6, zb - 6.0, zb),
        'J4 PH6 port': box(-16.8, -7.2, 20.5, 36.5, zb - 6.0, zb),
        'SW1 slide switch': box(sx0, sx1, sy0, sy1, sz0, sz1).fuse(
            box(sx1 - 0.01, P['ActTipX'], ay - P['ActW'] / 2, ay + P['ActW'] / 2, az0, az1)),
        'SW2 BOOT button': sw2_proxy(zb),
        'U6 IMU': box(-1.5 + P['TofXY'][0] * 0 - 3.7, -1.2, 47.5, 50.5, zb - 0.83, zb),
        'U7 magnetometer': box(0.0, 2.0, 14.0, 16.0, zb - 1.0, zb),
    }
    tx, ty = P['TofXY']
    tw, tl, th = P['TofBody']
    parts['U5 ToF'] = box(tx - tw / 2, tx + tw / 2, ty - tl / 2, ty + tl / 2, 0, th)
    return parts


def glass():
    w, L, t = P['GlassW'], P['GlassL'], P['GlassT']
    y0 = P['GlassY0']
    z0 = P['GlassFoam']
    g = box(-w / 2, w / 2, y0, y0 + L, z0, z0 + t)
    aw, al = P['ActiveW'], P['ActiveL']
    ay0 = y0 + P['ActiveBottom']
    active = box(-aw / 2, aw / 2, ay0, ay0 + al, z0 + t - 0.05, z0 + t + 0.001)
    # FPC: from under the glass bottom edge down round the board end to the connector on the back
    fw = P['FpcW']
    zf = z0 + 0.6
    strip = box(-fw / 2, fw / 2, 0.0, y0 + 2.0, zf, zf + 0.12)
    bend = (Part.makeCylinder(1.6, fw, V(0, 0, -0.8), V(1, 0, 0)).cut(
        Part.makeCylinder(1.48, fw, V(0, 0, -0.8), V(1, 0, 0)))).common(box(-fw / 2, fw / 2, -3, 0.0, -3, 3))
    bend.translate(V(-fw / 2, 0, 0))
    back = box(-fw / 2, fw / 2, 0.0, 5.5, -P['PcbT'] - 1.3, -P['PcbT'] - 1.18)
    fpc = strip.fuse([bend, back])
    return g.cut(active), active, fpc


def battery():
    w, L, t = P['BatW'], P['BatL'], P['BatT']
    y0, z1 = P['BatY0'], P['BatZ']
    b = box(-w / 2, w / 2, y0, y0 + L, z1 - t, z1)
    return try_fillet(b, [e for e in b.Edges if abs(e.BoundBox.YMax - e.BoundBox.YMin) > 1], (1.0,), 'battery')


def active_y():
    return P['GlassY0'] + P['ActiveBottom'], P['GlassY0'] + P['ActiveBottom'] + P['ActiveL']


# ----------------------------------------------------------------------------- case
def side_cuts():
    """Openings in the rear cover sides: USB-C, PH6, switch window and flange channel."""
    x = P['CaseX']
    w, h = P['UsbWH']
    usb = yz_rect(P['UsbY'], P['UsbZ'], w, h, h / 2 - 1e-3, x - 4, x + 2)
    w, h = P['Ph6WH']
    ph6 = yz_rect(P['Ph6Y'], P['Ph6Z'], w, h, 1.0, -x - 2, -x + 4)
    return [usb, ph6] + slider_cuts()


def slider_geom():
    c = P['SliderClear']
    xi = P['SwBody'][0][1] + 0.05                 # flange inner face, just off the switch body
    xf = xi + P['FlangeT']
    xw = P['CaseX'] - P['Wall']                   # wall inner face
    gz0, gz1 = P['GripZ']
    m = P['FlangeMargin']
    t, gl = P['ActTravel'], P['GripL']
    ya = P['ActY'] - t / 2                        # grip centred between the two detents
    wl = gl + t + 2 * c                           # window length
    fl = wl + 2 * m + t                           # flange covers the window at both ends of the travel
    fz1 = min(gz1 + m, -P['PcbT'] - 0.2)       # the flange stops short of the PCB back face
    return dict(xi=xi, xf=xf, xw=xw, gz0=gz0, gz1=gz1, fz0=gz0 - m, fz1=fz1, ya=ya, wl=wl, fl=fl, c=c)


def slider_cuts():
    g = slider_geom()
    ya, c = g['ya'], g['c']
    chan = box(g['xi'] - 0.3, P['CaseX'] - P['Wall'] + 0.01, ya - g['fl'] / 2 - c, ya + g['fl'] / 2 + c,
               g['fz0'] - c, g['fz1'] + c)
    win = box(g['xw'] - 0.2, P['CaseX'] + 2, ya - g['wl'] / 2, ya + g['wl'] / 2, g['gz0'] - c, g['gz1'] + c)
    return [chan, win]


def build_slider():
    g = slider_geom()
    ya = P['ActY'] - P['ActTravel'] / 2 + P['ActTravel'] / 2   # drawn as at the upper detent (ActY)
    yc = P['ActY']                                          # grip centred on the actuator
    gl = P['GripL']
    xo = P['CaseX'] + P['GripProud']
    flange = box(g['xi'], g['xf'], yc - g['fl'] / 2, yc + g['fl'] / 2, g['fz0'], g['fz1'])
    grip = box(g['xf'] - 0.01, xo, yc - gl / 2, yc + gl / 2, g['gz0'], g['gz1'])
    outer = [e for e in grip.Edges if abs(e.BoundBox.XMin - xo) < 1e-6 and abs(e.BoundBox.XMax - xo) < 1e-6]
    grip = try_fillet(grip, outer, (0.5,), 'grip')
    s = flange.fuse(grip)
    for dy in (-1.5, 0.0, 1.5):
        s = s.cut(box(xo - 0.35, yc + dy - 0.3, g['gz0'] - 1, xo + 1, yc + dy + 0.3, g['gz1'] + 1))
    az0, az1 = P['ActZ']
    w = P['ActW'] + 0.4
    s = s.cut(box(g['xi'] - 1, P['ActTipX'] + 0.4, P['ActY'] - w / 2, P['ActY'] + w / 2, az0 - 0.25, az1 + 0.25))
    return s.removeSplitter()


def tof_window(z0, z1):
    tx, ty = P['TofXY']
    (L, W), g = P['TofWin'], math.tan(math.radians(P['TofWinTaper']))
    za, zb = z0 - 0.3, z1 + 0.3
    grow = lambda z: (z - z0) * g
    pill = lambda z: rounded_rect(tx - L / 2 - grow(z), ty - W / 2 - grow(z), tx + L / 2 + grow(z),
                                  ty + W / 2 + grow(z), W / 2 + grow(z), z).OuterWire
    return Part.makeLoft([pill(za), pill(zb)], True)


def tof_cones(height=4.0):
    """The ToF emitter and receiver fields, as cones from the sensor top, for the clearance check."""
    tx, ty = P['TofXY']
    a, r = P['TofApert'], 0.3
    z = P['TofBody'][2]
    t = math.tan(math.radians(P['TofCone']))
    return [Part.makeCone(r, r + height * t, height, V(tx + dx, ty, z)) for dx in (-a, a)]


def front_shell():
    x, y0, y1 = P['CaseX'], P['CaseY0'], P['CaseY1']
    zt, zs, w = P['TopZ'], P['SeamZ'], P['Wall']
    s = case_outline(zs, zt)
    s = try_fillet(s, edges_at_z(s, zt), (P['TopFillet'], 0.8), 'front shell top edge')
    # hollow: everything inside the walls below the plate
    plate_bottom = zt - 1.0
    s = s.cut(rrect_prism(-x + w, y0 + w, x - w, y1 - w, P['CaseR'] - w, zs - 1, plate_bottom))
    # window over the active area, chamfered on the outside
    ay0, ay1 = active_y()
    m = P['WindowMargin']
    wx, wy0, wy1 = P['ActiveW'] / 2 + m, ay0 - m, ay1 + m
    s = s.cut(box(-wx, wx, wy0, wy1, plate_bottom - 1, zt + 1))
    c = P['WindowChamfer']
    s = s.cut(prism_yz([(wy0 - c, zt + 0.01), (wy0 + 0.01, zt - c), (wy0 + 0.01, zt + 0.01)], -wx - 1, wx + 1))
    s = s.cut(prism_yz([(wy1 + c, zt + 0.01), (wy1 - 0.01, zt - c), (wy1 - 0.01, zt + 0.01)], -wx - 1, wx + 1))
    s = s.cut(prism_xz([(-wx - c, zt + 0.01), (-wx + 0.01, zt - c), (-wx + 0.01, zt + 0.01)], wy0 - 1, wy1 + 1))
    s = s.cut(prism_xz([(wx + c, zt + 0.01), (wx - 0.01, zt - c), (wx - 0.01, zt + 0.01)], wy0 - 1, wy1 + 1))
    # rims the PCB rests on, beside the glass along the long sides, and bosses at the screw holes
    adds = []
    rw = P['RimW']
    for sx in (-1, 1):
        xa, xb = sorted((sx * (x - w + 0.01), sx * (x - w - rw)))
        adds.append(box(xa, xb, 0.0, P['PcbL'], 0.0, plate_bottom + 0.01))
    for hx, hy in P['Holes']:
        adds.append(cyl(P['BossD'], hx, hy, 0.0, plate_bottom + 0.01))
    s = s.fuse(adds).removeSplitter()
    for hx, hy in P['Holes']:
        s = s.cut(cyl(P['PilotD'], hx, hy, -1.0, P['PilotDepth']))
    # ToF window: a pill slot whose walls open outward, wide enough that the bezel never clips the field
    s = s.cut(tof_window(plate_bottom, zt))
    # lip joint: the rear cover's lip rises inside the front shell wall along the long sides
    lt, lh, lc = P['LipT'], P['LipH'], P['LipClear']
    for sx in (-1, 1):
        xa, xb = sorted((sx * (x - w - 0.01), sx * (x - w + lt + lc)))
        s = s.cut(box(xa, xb, P['CaseR'], y1 - P['CaseR'], zs - 1, zs + lh + lc))
    return s.removeSplitter()


def rear_cover():
    x, y0, y1 = P['CaseX'], P['CaseY0'], P['CaseY1']
    zs, zr, w, fl = P['SeamZ'], P['RearZ'], P['Wall'], P['Floor']
    s = case_outline(zr, zs)
    s = try_chamfer(s, edges_at_z(s, zr), P['BottomChamfer'], 'rear cover bottom')
    s = s.cut(rrect_prism(-x + w, y0 + w, x - w, y1 - w, P['CaseR'] - w, zr + fl, zs + 1))
    # lip along the long sides
    lt, lh = P['LipT'], P['LipH']
    lips = []
    for sx in (-1, 1):
        xa, xb = sorted((sx * (x - w), sx * (x - w + lt)))
        lips.append(box(xa, xb, P['CaseR'] + 0.3, y1 - P['CaseR'] - 0.3, zs - 0.01, zs + lh))
    # screw posts up to the PCB back, and battery ribs
    posts = [cyl(P['BossD'], hx, hy, zr + fl - 0.01, zs) for hx, hy in P['Holes']]
    bw, by0, bl = P['BatW'], P['BatY0'], P['BatL']
    ribs = [box(sx * (bw / 2 + 0.3), sx * (bw / 2 + 1.3), by0 - 0.3, by0 + bl + 0.3, zr + fl - 0.01, zr + fl + 2.0)
            for sx in (-1, 1)]
    ribs = [box(min(r.BoundBox.XMin, r.BoundBox.XMax), max(r.BoundBox.XMin, r.BoundBox.XMax), by0 - 0.3, by0 + bl + 0.3,
                zr + fl - 0.01, zr + fl + 2.0) for r in ribs]
    hx, hy, _, tube_top = pin_geom()
    tube = cyl(P['PinTubeOD'], hx, hy, zr + fl - 0.01, tube_top)
    s = s.fuse(lips + posts + ribs + [tube]).removeSplitter()
    # BOOT pin hole through the back and up the tube, with a lead-in, and the white icon round it
    s = s.cut(cyl(P['PinBoreD'], hx, hy, zr - 1, tube_top + 1))
    rk, rb = P['PinCskD'] / 2, P['PinBoreD'] / 2
    s = s.cut(Part.makeCone(rk + 0.3, rb, rk - rb + 0.3, V(hx, hy, zr - 0.3)))
    s = s.cut(reset_icon())
    # screw holes with countersinks on the outside
    for hx, hy in P['Holes']:
        s = s.cut(cyl(P['ScrewClearD'], hx, hy, zr - 1, zs + 1))
        rk, rc = P['CskD'] / 2, P['ScrewClearD'] / 2
        h = (rk - rc) / math.tan(math.radians(41))
        s = s.cut(Part.makeCone(rk + 0.5 * math.tan(math.radians(41)), rc, h + 0.5, V(hx, hy, zr - 0.5)))
    s = s.cut(side_cuts()).removeSplitter()
    return s


def screw(hx, hy):
    zr = P['RearZ']
    dk, d = P['CskD'] - 0.2, 2.0
    k = (dk - d) / 2 / math.tan(math.radians(41))
    head = Part.makeCone(dk / 2, d / 2, k, V(hx, hy, zr))
    shank = cyl(d, hx, hy, zr + k - 0.01, zr + 16.0 - 0.5)
    tip = Part.makeCone(d / 2, 0.3, 0.5, V(hx, hy, zr + 16.0 - 0.5))
    s = head.fuse([shank, tip])
    rec = cyl(1.6, hx, hy, zr - 0.1, zr + 0.8).fuse(
        [cyl(0.6, hx + 0.85 * math.cos(math.pi * i / 3), hy + 0.85 * math.sin(math.pi * i / 3), zr - 0.1, zr + 0.8)
         for i in range(6)])
    return s.cut(rec).removeSplitter()


# ----------------------------------------------------------------------------- cradle
def z_front():
    return P['RearZ'] - P['RestGap']


def z_rear():
    return z_front() - P['PlateT']


def z_wall_top():
    return P['TopZ'] + P['WallTopAbove']


def outer_x():
    return P['CaseX'] + P['WallClear'] + P['RailT']


def y_end():
    return P['CaseY0'] - P['WallClear'] - P['RailT']


def cup_centres():
    yu = P['TongueTop'] - P['TongueWeb'] - P['KeyEntryD'] / 2
    return {'L': (0.0, P['LowCupY']), 'U': (0.0, yu)}


def entry_centre(key):
    sx, sy = cup_centres()[key]
    return sx, sy + P['CupEntry'][0 if key == 'L' else 1]


def plan_face():
    zr = z_rear()
    top = P['PlateTop']
    xl, xr = -outer_x(), outer_x()
    return round_face(flat_face([box(xl, xr, y_end(), top, zr, zr + 1.0)], zr), 0, P['CornerR'])


def wall_profile(y):
    """Wall top height above the plate front along Y: full with lips, low beside the ports, the swoop."""
    zt = z_wall_top()
    s0, s1 = P['SwoopY0'], P['SwoopY1']
    if y >= s1:
        return z_front()
    if y >= s0:
        t = (y - s0) / (s1 - s0)
        return z_front() + (zt - z_front()) * (1 + math.cos(math.pi * t)) / 2
    return zt


def elevation_solid():
    """Side elevation of the sleeve: a flat top from the hood to SwoopY0, then an S-swoop to the plate."""
    zf, zr, zt = z_front(), z_rear(), z_wall_top()
    pts = [(y_end() - 1, zr - 1), (y_end() - 1, zt)]
    s0, s1 = P['SwoopY0'], P['SwoopY1']
    n = 16
    for i in range(n + 1):
        y = s0 + (s1 - s0) * i / n
        pts.append((y, wall_profile(y)))
    pts += [(FAR, zf), (FAR, zr - 1)]
    return prism_yz(pts, -FAR / 2, FAR / 2)


def sleeve_blank():
    zr = z_rear()
    blank = plan_face().extrude(V(0, 0, z_wall_top() + 2 - zr)).common(elevation_solid()).removeSplitter()
    top = []
    for e in blank.Edges:
        b = e.BoundBox
        if b.ZMin > zr + 0.5 and (b.ZMax - b.ZMin) < 1e-6 and abs(b.ZMax - z_wall_top()) < 1e-6:
            top.append(e)
    blank = try_fillet(blank, top, (P['EdgeR'], 0.6), 'sleeve top edge')
    blank = try_chamfer(blank, edges_at_z(blank, zr), P['BedChamfer'], 'sleeve bed')
    return blank


def cavity():
    """Space for the case: walls with lips over the top round along the sides where there are no ports,
    low walls beside the ports, a hood lip over the bottom end."""
    zf = z_front()
    c, ch = P['WallClear'], P['InnerChamfer']
    he = P['HookEngage']
    xr, r, zt = P['CaseX'], P['TopFillet'], P['TopZ']
    ir = xr + c
    ztop = z_wall_top() + 5
    kl = (xr - r) + (zt - r) + (r + c) * math.sqrt(2)      # lip underside: x + z = kl (45 deg, clear of the round)
    zl = kl - ir
    zw, lc = z_wall_top(), P['LipChamfer']

    def prof(lips):
        if lips:
            tr, zh, d = xr - he, kl - (xr - he), lc
        else:
            tr, zh, d = ir, zl + he, 0.0
        right = [(ir - ch, zf), (ir, zf + ch), (ir, zl), (tr, zh), (tr, zw - lc), (tr + d, zw), (tr + d, ztop)]
        left = [(-x, z) for x, z in reversed(right)]
        return right + left

    def low_prof():
        h = P['LowWallH']
        return [(-ir, zf + h), (-ir + ch, zf), (ir - ch, zf), (ir, zf + ch), (ir, zf + h), (ir, ztop), (-ir, ztop)]

    lip, plain = prof(True), prof(False)
    # along Y: lips except over the port gaps, where the wall is low on that side
    y0 = y_end() - 1
    sections = []
    (r0, r1), (l0, l1) = P['PortGapR'], P['PortGapL']
    cuts_y = sorted({y0, r0, r1, l0, l1, FAR})
    for a, b in zip(cuts_y, cuts_y[1:]):
        mid = (a + b) / 2
        right_low = r0 <= mid < r1
        left_low = l0 <= mid < l1
        full = prism_xz(lip, a, b)
        if right_low:
            full = full.fuse(prism_xz([(0, zf + P['LowWallH']), (ir + 5, zf + P['LowWallH']), (ir + 5, ztop), (0, ztop)], a, b))
        if left_low:
            full = full.fuse(prism_xz([(-ir - 5, zf + P['LowWallH']), (0, zf + P['LowWallH']), (0, ztop), (-ir - 5, ztop)], a, b))
        sections.append(full.removeSplitter())
    cav = sections[0].fuse(sections[1:]).removeSplitter()
    # bottom end: plan corners of the case and the hood lip over its end
    yb0 = P['CaseY0']
    foot = Part.Face(Part.makePolygon([V(-xr, yb0, z_rear()), V(xr, yb0, z_rear()), V(xr, 60.0, z_rear()),
                                       V(-xr, 60.0, z_rear()), V(-xr, yb0, z_rear())]))
    plan = round_face(foot, 0, P['CaseR']).makeOffset2D(c, join=0).extrude(V(0, 0, 60))
    yi = yb0 - c                                            # hood inner face
    end = prism_yz([(yi + ch, zf), (FAR, zf), (FAR, ztop), (yi + he + c, ztop), (yi + he + c, zw),
                    (yi + he + c - lc, zw - lc), (yi + he + c - lc, zt + c + 0.3), (yi, zt - r), (yi, zf + ch)],
                   -FAR / 2, FAR / 2)
    cav = cav.common(plan.fuse(box(-FAR, FAR, yb0 + P['CaseR'], FAR, z_rear() - 1, ztop + 1))).common(end)
    # groove in the right wall at the switch grip height, so the grip rides along it while the case slides out
    gz0, gz1 = P['GripZ']
    g = P['SwitchGroove']
    cav = cav.fuse(box(ir - 0.01, ir + P['GripProud'] + g, r1 - 0.01, P['SwoopY1'] + 1, gz0 - g, gz1 + g))
    return cav.removeSplitter()


def keyholes():
    zf, zr = z_front(), z_rear()
    zl = zr + P['KeyLandT']
    cut = []
    w, re, rp = P['KeySlotW'] / 2, P['KeyEntryD'] / 2, P['KeySnapD'] / 2
    a = math.radians((360 - P['KeySnapWrap']) / 2)
    m, ym = rp * math.sin(a), rp * math.cos(a)
    yl = ym + P['KeySnapLead']
    for key, (sx, sy) in cup_centres().items():
        ex, ey = entry_centre(key)
        d = 1 if ey < sy else -1                    # +1: the cup slides up into its snap, -1: down
        slot = prism([(sx - w, ey), (sx + w, ey), (sx + w, sy - d * yl), (sx + m, sy - d * ym), (sx + m, sy),
                      (sx - m, sy), (sx - m, sy - d * ym), (sx - w, sy - d * yl)], zr - 1, zf + 1)
        cut += [cyl(2 * re, sx, ey, zr - 1, zf + 1), cyl(2 * rp, sx, sy, zr - 1, zf + 1), slot,
                cyl(2 * re, sx, sy, zl, zf + 1), box(sx - re, sx + re, ey, sy, zl, zf + 1)]
    return cut


def cup_head_top():
    return z_rear() - P['StemSeat'] + P['GrooveH'] + P['HeadT']


def cup_shape(x, y):
    zr = z_rear()
    rs = P['StemD'] / 2
    zs = zr - P['StemSeat']
    rim = zr - P['CupDepth']
    zb = zs - P['StemLen']
    outside = Part.makeCone(P['CupD'] / 2, rs, zb - rim, V(x, y, rim))
    inside = Part.makeCone(P['CupD'] / 2 - 1.2, rs - 1.2, zb - rim - 1.5, V(x, y, rim - 0.1))
    stem = cyl(2 * rs, x, y, zb - 0.5, zs)
    groove = cyl(P['GrooveD'], x, y, zs - 0.01, zs + P['GrooveH'] + 0.01)
    head = cyl(2 * rs, x, y, zs + P['GrooveH'], cup_head_top())
    return outside.cut(inside).fuse([stem, groove, head]).removeSplitter()


def tooth_profile():
    zt0 = z_front() - 0.01
    zt = P['RearZ'] + P['ToothRise']
    ys = P['CaseY1'] + P['ToothClear']
    yf = ys + P['ToothFlat']
    z_r = P['RearZ'] - 0.5
    yr = yf + (zt - z_r) / math.tan(math.radians(P['RampAngle']))
    yb = yr + (z_r - zt0)
    prof = [(ys, zt0), (ys, zt), (yf, zt), (yr, z_r), (yb, zt0)]
    # the hinge's ramp back up to the plate front ends under the tooth: carry the tooth's foot down onto it
    zh, ye, ramp = z_rear() + P['LatchT'], P['LatchFlexEndY'], P['LatchRootRamp']
    if ys < ye + ramp:
        zlow = max(zh, zh + (ys - ye) / ramp * (z_front() - zh)) - 0.1
        prof = [(ys, zlow)] + prof[1:] + [(ye + ramp, zt0)]
    return prof


def latch_cut():
    """The lever is a U: two arms from the root, joined by the press tab at the plate top edge. The fixed
    tongue between the arms carries the upper cup, so the cup never rides on the lever."""
    zf, zr = z_front(), z_rear()
    g, y0, xh = P['LatchSlot'], P['LatchRootY'], P['LatchX']
    xt, yt = P['TongueX'], P['TongueTop']
    rr = P['LatchReliefD'] / 2
    cuts = []
    for xa in (-xh - g, xh):                       # outer slots, open at the top edge
        cuts += [box(xa, xa + g, y0, FAR, zr - 1, zf + 1), cyl(2 * rr, xa + g / 2, y0, zr - 1, zf + 1)]
    for xa in (-xt - g, xt):                       # tongue slots
        cuts += [box(xa, xa + g, y0, yt + g, zr - 1, zf + 1), cyl(2 * rr, xa + g / 2, y0, zr - 1, zf + 1)]
    cuts.append(box(-xt - g, xt + g, yt, yt + g, zr - 1, zf + 1))   # across the tongue end
    zt = zr + P['LatchT']
    ramp, ye = P['LatchRootRamp'], P['LatchFlexEndY']
    hinge = [(y0, zf), (y0 + ramp, zt), (ye, zt), (ye + ramp, zf), (ye + ramp, zf + 1), (y0, zf + 1)]
    for xa, xb in ((-xh, -xt - g), (xt + g, xh)):  # thin hinges in the arms only
        cuts.append(prism_yz(hinge, xa, xb))
    y = max(y for y, _ in tooth_profile()) + 1.2
    r = P['GripW'] / 2
    zb = zf - P['GripDepth'] + r
    for i in range(int(P['GripN'])):
        yc = y + i * P['GripPitch']
        cuts += [Part.makeCylinder(r, 2 * xh - 3.0, V(-xh + 1.5, yc, zb), V(1, 0, 0)),
                 box(-xh + 1.5, xh - 1.5, yc - r, yc + r, zb, zf + 1)]
    return cuts


def latch_teeth():
    prof = tooth_profile()
    teeth = []
    for xa, xb in P['ToothX']:
        t = prism_yz(prof, xa, xb)
        sides = [e for e in t.Edges if abs(e.BoundBox.XMax - e.BoundBox.XMin) < 1e-6 and e.BoundBox.ZMax > z_front() + 0.01]
        teeth.append(try_fillet(t, sides, (0.5,), 'tooth'))
    return teeth


def touch_region():
    zf = z_front()
    y0 = max(y for y, _ in tooth_profile()) + 0.2
    return box(-P['LatchX'], P['LatchX'], y0, FAR, zf - P['TouchInlayT'], zf)


def ledges():
    zf, zb, c = z_front(), P['RearZ'], P['WallClear']
    h = zb - zf
    y0, y1, reach = P['CaseY0'] - c - 0.01, P['LedgeY1'], P['LedgeReach']
    run = prism_yz([(y0, zf - 0.01), (y1, zf - 0.01), (y1 - h, zb), (y0, zb)], -FAR / 2, FAR / 2)
    out = []
    for edge, inward in ((-P['CaseX'], 1), (P['CaseX'], -1)):
        x = lambda d: edge + inward * d
        sec = prism_xz([(x(-c - 0.01), zf - 0.01), (x(reach + h), zf - 0.01), (x(reach), zb), (x(-c - 0.01), zb)],
                       y0 - 1, y1 + 1)
        out.append(sec.common(run))
    return out


def cradle():
    body = sleeve_blank().cut(cavity()).removeSplitter()
    body = body.cut(keyholes()).removeSplitter()
    body = body.cut(latch_cut()).removeSplitter()
    printed = body.fuse(ledges() + latch_teeth()).removeSplitter()
    reg = touch_region()
    return printed.cut(reg).removeSplitter(), printed.common(reg).removeSplitter()


# ----------------------------------------------------------------------------- checks, export, scenes
def check(label, shape):
    bb = shape.optimalBoundingBox()
    print('CHECK %s: valid %s, solids %d, %.1f x %.1f x %.1f mm, %.1f cm3' % (
        label, shape.isValid(), len(shape.Solids), bb.XLength, bb.YLength, bb.ZLength, shape.Volume / 1000))


def overlap(a, b):
    try:
        return a.common(b).Volume
    except Exception:
        return float('nan')


def mesh(shape, path, fine=0.03):
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=fine, AngularDeflection=0.25, Relative=False)
    m.write(path)


def main():
    os.makedirs(PARTS, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    pcb, models = load_board()
    proxies = board_proxies()
    g, active, fpc = glass()
    bat = battery()
    front = front_shell()
    rear = rear_cover()
    icon = reset_icon()
    slider = build_slider()
    screws = [screw(hx, hy) for hx, hy in P['Holes']]
    plate_black, plate_blue = cradle()
    cups = {k: cup_shape(x, y) for k, (x, y) in cup_centres().items()}

    for label, s in [('front shell', front), ('rear cover', rear), ('rear icon', icon), ('switch cover', slider),
                     ('cradle black', plate_black), ('cradle blue', plate_blue)]:
        check(label, s)
    print('CHECK case %.1f x %.1f x %.1f mm' % (2 * P['CaseX'], P['CaseY1'] - P['CaseY0'], P['TopZ'] - P['RearZ']))
    pcb_all = pcb.fuse([models] + list(proxies.values()))
    for label, s in [('front shell', front), ('rear cover', rear), ('switch cover', slider)]:
        print('CHECK %s vs board and parts: overlap %.3f mm3' % (label, overlap(s, pcb_all)))
        print('CHECK %s vs glass: overlap %.3f mm3, vs battery %.3f' % (label, overlap(s, g), overlap(s, bat)))
    print('CHECK front shell vs rear cover: overlap %.3f mm3' % overlap(front, rear))
    cones = Part.makeCompound(tof_cones())
    print('CHECK ToF field (%.0f deg half-angle) vs front shell %.3f, glass %.3f mm3' % (
        P['TofCone'], overlap(cones, front), overlap(cones, g)))
    print('CHECK rear icon vs rear cover: overlap %.3f mm3, flush %s' % (
        overlap(icon, rear), abs(icon.BoundBox.ZMin - rear.BoundBox.ZMin) < 1e-6))
    hx, hy, plunger, _ = pin_geom()
    clip = cyl(1.0, hx, hy, P['RearZ'] - 5, plunger + 0.3)
    others = pcb.fuse([models] + [v for k, v in proxies.items() if not k.startswith('SW2')])
    print('CHECK paperclip (1.0) up the BOOT hole: rear cover %.3f, battery %.3f, other parts %.3f mm3; '
          'presses the button %.2f mm3' % (overlap(clip, rear), overlap(clip, bat), overlap(clip, others),
                                           overlap(clip, proxies['SW2 BOOT button'])))
    print('CHECK switch cover vs shells: %.3f mm3' % overlap(slider, Part.makeCompound([front, rear])))
    case = Part.makeCompound([front, rear, slider])
    print('CHECK case in the cradle: overlap %.3f mm3' % overlap(case, Part.makeCompound([plate_black, plate_blue])))
    for label, s in [('front shell', front), ('rear cover', rear), ('switch cover', slider)]:
        for plabel, pl in [('black', plate_black), ('blue', plate_blue)]:
            cm = s.common(pl)
            if cm.Volume > 1e-6:
                bb = cm.BoundBox
                print('CHECK   %s vs cradle %s: %.3f mm3 at x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f' % (
                    label, plabel, cm.Volume, bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    lever = box(-P['LatchX'], P['LatchX'], P['LatchRootY'], FAR, z_rear() - 1, P['RearZ'] + P['ToothRise'] + 1)
    fixed = plate_black.cut(lever)
    slide = [(overlap(case.translated(V(0, d, 0)), fixed), d) for d in [0.5] + [2.5 * i for i in range(1, 37)]]
    print('CHECK case sliding out to 90 mm: worst overlap %.3f mm3 outside the lever, at %.1f mm' % max(slide))
    held = rear.translated(V(0, 0.5, 0)).common(Part.makeCompound(latch_teeth()))
    print('CHECK teeth: case pulled 0.5 mm meets them, %.1f mm3' % held.Volume)
    lift = overlap(case.translated(V(0, 0, 0.5)), plate_black)
    print('CHECK lips: case lifted 0.5 mm meets them, %.1f mm3' % lift)
    for k, cup in cups.items():
        print('CHECK cup %s vs rear cover: %.3f mm3, gap %.2f' % (k, overlap(cup, rear), cup.distToShape(rear)[0]))
    (lx, ly), (ux, uy) = cup_centres()['L'], cup_centres()['U']
    print('CHECK cups: %.1f mm apart, %.1f mm between the discs; discs %.1f to %.1f in Y, plate %.1f to %.1f' % (
        uy - ly, uy - ly - P['CupD'], ly - P['CupD'] / 2, uy + P['CupD'] / 2, y_end(), P['PlateTop']))

    if os.environ.get('DTT_CHECK_ONLY'):
        print('done (checks only)')
        return
    # document
    doc = App.newDocument('DTT_v2')
    groups = {}

    def add(group, name, label, shape):
        if group not in groups:
            groups[group] = doc.addObject('App::Part', group)
            groups[group].Label = group
        o = doc.addObject('Part::Feature', name)
        o.Label = label
        o.Shape = shape
        groups[group].addObject(o)
        return o

    add('Board', 'Pcb', 'PCB (KiCad export)', pcb)
    add('Board', 'Components', 'Components (KiCad models)', models)
    for name, s in proxies.items():
        add('Board', 'Proxy_' + name.split()[0], name + ' (proxy)', s)
    add('Screen', 'Glass', 'Touch panel glass', g)
    add('Screen', 'Active', 'Active area', active)
    add('Screen', 'Fpc', 'Screen FPC', fpc)
    add('Battery', 'Battery', 'LiPo %dx%dx%d' % (P['BatT'], P['BatW'], P['BatL']), bat)
    add('Case', 'FrontShell', 'Front shell - print black', front)
    add('Case', 'RearCover', 'Rear cover - print black', rear)
    add('Case', 'RearIcon', 'Rear cover BOOT icon - print white', icon)
    add('Case', 'SwitchCover', 'Switch cover - print blue', slider)
    for i, s in enumerate(screws, 1):
        add('Case', 'Screw%d' % i, 'M2 x 16 flat head self-tapping %d' % i, s)
    add('Cradle', 'CradleBlack', 'Cradle - print black', plate_black)
    add('Cradle', 'CradleBlue', 'Cradle touch point - print blue', plate_blue)
    for k, cup in cups.items():
        add('Cradle', 'Cup' + k, 'Suction cup %s (proxy)' % k, cup)
    sheet = doc.addObject('Spreadsheet::Sheet', 'Parameters')
    sheet.set('A1', 'Parameter'); sheet.set('B1', 'Value'); sheet.set('C1', 'Basis')
    for i, (k, (v, note)) in enumerate(PARAMS.items(), 2):
        sheet.set('A%d' % i, k); sheet.set('B%d' % i, str(v)); sheet.set('C%d' % i, note)
    doc.recompute()
    doc.saveAs(os.path.join(HERE, 'DTT-v2.FCStd'))
    Part.makeCompound([pcb, models, g, active, fpc, bat, front, rear, icon, slider, plate_black, plate_blue] + screws
                      + list(cups.values()) + list(proxies.values())).exportStep(os.path.join(HERE, 'DTT-v2.step'))
    for name, s in [('Front-Shell-Black', front), ('Rear-Cover-Black', rear), ('Rear-Cover-White', icon),
                    ('Switch-Cover-Blue', slider),
                    ('Cradle-Black', plate_black), ('Cradle-Blue', plate_blue)]:
        s.exportStep(os.path.join(PARTS, name + '.step'))
        mesh(s, os.path.join(PARTS, name + '.stl'), 0.02)
    # render meshes
    vis = {'pcb': (pcb, PCB), 'models': (models, METAL), 'glass': (g, GLASS), 'active': (active, SCREEN),
           'fpc': (fpc, (0.85, 0.6, 0.2)), 'battery': (bat, BATTERY), 'front': (front, BLACK), 'rear': (rear, BLACK),
           'rear_icon': (icon, WHITE),
           'slider': (slider, BLUE), 'cradle_black': (plate_black, BLACK), 'cradle_blue': (plate_blue, BLUE),
           'screws': (Part.makeCompound(screws), (0.55, 0.55, 0.58)),
           'cups': (Part.makeCompound(list(cups.values())), CUP),
           'proxies': (Part.makeCompound(list(proxies.values())), (0.35, 0.35, 0.38))}
    for name, (s, col) in vis.items():
        mesh(s, os.path.join(BUILD, name + '.stl'), 0.05)
    # sections for the renders: the half x <= 0, the half y >= the switch actuator, and through the BOOT hole
    secs = {'secx': box(-FAR, 0.0, -FAR, FAR, -FAR, FAR), 'secy': box(-FAR, FAR, P['ActY'], FAR, -FAR, FAR),
            'secp': box(-FAR, FAR, P['Sw2XY'][1], FAR, -FAR, FAR)}
    for sname, half in secs.items():
        for name, (s, col) in vis.items():
            try:
                cm = s.common(half)
            except Exception:
                continue
            if cm.Volume > 1e-6:
                mesh(cm, os.path.join(BUILD, '%s_%s.stl' % (sname, name)), 0.05)
    json.dump({k: c for k, (s, c) in vis.items()}, open(os.path.join(BUILD, 'colours.json'), 'w'))
    print('done')


if __name__ == '__main__' or True:
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise
