"""Build the DTT slide-in backplate around the unmodified module.

Run from the repository root under the FreeCAD GUI (needed for colours and previews):
    freecad hardware/cad/snap-backplate/build_snap_backplate.py
or headless with xvfb-run. It opens hardware/cad/DTT.FCStd read-only, adds the backplate and
saves the result beside this script as DTT-Snap-Backplate-Concept.FCStd, with STEP/STL exports in
hardware/production-exports/cad/snap-backplate/. DTT.FCStd itself is not modified. Edit PARAMS
below and re-run to change the design.

Design language: the track and the plate are one form. The part is the intersection of
a plan outline (body flaring into the two cup wings with large radii) and a side elevation (a hood
at the jack end that leans at the housing's own end angle, a flat top along the module, then one
S-shaped swoop down into the wings ahead of the side switch). The outer top edge carries one
continuous fillet and the module cavity is cut out of that form. The latch is a release lever
that is part of the plate outline: two slots run from under the module out through the top edge,
the flex zone is thinned from the front, and the full-thickness press tab carries grip grooves.
Printed-in stops limit the lever both ways: fingers under the tab and chamfered rails over its edges.
The print is black; the touch point, the front of the press tab, is a 0.6 mm blue inlay kept as a
separate body for two-colour printing. The grip grooves cut through it, so their bottoms are black.
Instead of the cups, an optional one-piece wall bracket carries the three keyhole studs. It screws or
sticks to the wall, and the plate hangs on it.

Device coordinates: X across the module, Y along it (USB-C end at +Y), Z out of the front face. The
PCB rear face is Z -5.1. The wall is at -Z; the part prints rear face down.
"""
import math, os
import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
CAD = os.path.join(ROOT, 'hardware', 'cad')
HERE = os.path.join(CAD, 'snap-backplate')
OUT = os.path.join(ROOT, 'hardware', 'production-exports', 'cad', 'snap-backplate')
TAG = 'SnapBackplate'

# name: (value, basis)
PARAMS = {
    # module, measured from the housing and board solids in DTT.FCStd
    'PCBRearZ': (-5.1, 'verified: board rear face'),
    'DeviceCx': (21.0, 'verified: housing centreline'),
    'DeviceBottomY': (1.0, 'verified: housing jack end face'),
    'DeviceTopY': (93.0, 'verified: housing USB-C end'),
    'HousingTopZ': (14.17, 'verified: front face'),
    'EndSlopeZ0': (9.5, 'verified: jack-end top slope starts at Y 1.0, Z 9.5'),
    'EndSlopeY1': (4.41, 'verified: jack-end top slope ends at Y 4.41, Z 14.17'),
    'EndCornerC': (3.0, 'verified: jack-end plan corners are 3 mm 45 deg chamfers (R1 blends)'),
    # plate outline: a body flush with the track, flaring into two wings that carry the upper cups
    'PlateT': (4.0, 'reference proxy (estimate)'),
    'DeviceTopInset': (17.0, 'reference proxy: plate top to housing top end'),
    'WingWeb': (3.5, 'design: plate web around the upper keyhole entries'),
    'FlareR': (14.0, 'design: concave blend from the body into each wing'),
    'CornerR': (8.0, 'design: convex plan corners, also the jack-end corners of the sleeve'),
    # sleeve: side elevation and edges
    'RestGap': (2.6, 'design: plate front to PCB rear; PCB screw heads and the lower cup head pass under the PCB'),
    'WallClear': (0.2, 'design: clearance to the housing sides'),
    'RailT': (2.0, 'design: side wall thickness at the widest housing section'),
    'WallTopAbove': (0.8, 'design: wall top above the housing front face'),
    'HoodT': (1.4, 'design: jack-end hood thickness normal to the housing end slope'),
    'HoodTopR': (4.0, 'design: blend from the hood slope into the flat top'),
    'SwoopY0': (44.0, 'design: wall top starts to fall here; lips run to about Y 50'),
    'SwoopY1': (78.0, 'design: wall reaches the plate here, below the S1 switch at Y 79.4'),
    'EdgeR': (1.0, 'design: fillet along the whole outer top edge of the sleeve and wings, half the 2 mm wall so its top stays square'),
    'BedChamfer': (0.6, 'design: rear outer edge, against elephant foot'),
    'InnerChamfer': (1.0, 'design: 45 deg fillet-chamfer at the inner foot of the walls'),
    'HookEngage': (0.6, 'design: lip overlap onto the top chamfer and onto the jack-end slope'),
    'JackOpenX0': (14.0, 'design: opening in the hood for the 3.5 mm plug'),
    'JackOpenX1': (28.0, 'design'),
    'JackOpenR': (3.0, 'design: bottom corners of the plug opening'),
    'JackEdgeR': (1.0, 'design: rounded edges of the plug opening'),
    'InnerEdgeR': (0.5, 'design: rounded inner top edges of the walls and lips'),
    'SlotEdgeR': (0.4, 'design: rounded front edges of the lever slots'),
    'KeyEdgeR': (0.8, 'design: rounded front edges of the keyholes'),
    'SkidW': (2.0, 'design: skids under the PCB, between the screw-head and connector tracks'),
    'SkidY0': (5.0, 'design: skid start'),
    'SkidY1': (64.0, 'design: skid end, short of the tongue'),
    # release lever: part of the plate outline between two slots; teeth snap behind the PCB
    'LatchX0': (9.0, 'design: lever left edge'),
    'LatchX1': (33.0, 'design: lever right edge'),
    'LatchRootY': (66.0, 'design: lever root (slot ends), under the module'),
    'LatchSlot': (1.5, 'design: slot width either side of the lever; slots run out through the top edge'),
    'LatchReliefD': (2.5, 'design: round stress-relief ends of the slots at the root'),
    'LatchT': (2.0, 'design: flex zone thickness, thinned from the FRONT so it prints flat on the bed'),
    'LatchRootRamp': (6.0, 'design: run of the thinning ramps at both ends of the flex zone'),
    'LatchFlexEndY': (86.0, 'design: flex zone ends; the press tab with the teeth is full thickness'),
    'ToothXL': (10.5, 'design: left tooth X 10.5-14.5, outside the USB-C plug zone'),
    'ToothXR': (27.5, 'design: right tooth X 27.5-31.5, outside the USB-C zone and the J2/J6 lead tracks'),
    'ToothW': (4.0, 'design: each tooth'),
    'ToothEdgeR': (0.5, 'design: rounded side edges of the teeth'),
    'ToothRise': (1.2, 'design: tooth top above the PCB rear, catches the board edge'),
    'ToothClear': (0.2, 'design: tooth stop face to the module end'),
    'ToothFlat': (1.0, 'design'),
    'RampAngle': (30.0, 'design: lead-in ramp, degrees from the plate'),
    # over-travel stop: a fixed finger from the plate crosses each slot on the bed into a pocket in the
    # lever's rear; the pocket roof is bridged over the finger and bottoms out on it when pressed too far
    'StopY0': (92.6, 'design: fingers start just past the flex zone (the lever is full thickness from Y 92)'),
    'StopW': (4.0, 'design: finger width along Y'),
    'StopLand': (0.5, 'design: square lever edge at the slot above the 45 deg pocket roof, clear of the slot edge round'),
    'StopGap': (1.8, 'design: finger top to pocket roof, measured along Z: the press travel at the fingers'),
    'StopPen': (0.9, 'design: finger overlap into the lever, beside the teeth'),
    'StopClear': (0.5, 'design: clearance around the fingers, wide enough that elephant foot does not fuse them'),
    'PullY0': (98.0, 'design: pull-out rails beside the press tab, from just past the press-stop pockets (Y 97.1) out to the top edge'),
    'PullPen': (0.9, 'design: rail reach over the lever edge'),
    'PullLand': (0.4, 'design: rail thickness at its tip, flush with the front'),
    'PullGap': (1.0, 'design: rail underside to the lever, measured along Z: the outward travel at the tab edges'),
    'GripN': (4.0, 'design: grip grooves across the press tab'),
    'GripPitch': (2.0, 'design'),
    'GripW': (1.0, 'design: groove width; straight walls with a round bottom'),
    'GripDepth': (0.9, 'design: groove depth, through the blue inlay so the groove bottoms are black'),
    'GripStart': (1.5, 'design: first groove centre past the back foot of the teeth'),
    # colour: black print with the touch point (the press tab) in blue, as a separate body
    'TouchY0': (99.5, 'design: blue starts just past the teeth (back foot at Y 99.3), so the teeth stay on black'),
    'TouchInlayT': (0.6, 'design: blue inlay depth from the front face; only 3 layers need both colours'),
    # cups, keyhole travel and head size from the reference proxy
    'TopCupX': (28.0, 'design: from the centreline (reference 28.5), heads just outside the module'),
    'TopCupDrop': (13.0, 'reference proxy: below the plate top'),
    'TopSlot': (12.0, 'design: upper slots run upward from the entry, so the load seats the stems'),
    'LowCupY': (28.0, 'design: stem under the module, head clear of the skids'),
    'LowSlot': (12.0, 'design: lower slot runs upward from the entry'),
    'KeyEntryD': (14.0, 'reference proxy'),
    'KeySlotW': (9.0, 'reference proxy'),
    'CupD': (35.0, 'reference proxy (estimate)'),
    'CupDepth': (14.0, 'reference proxy (estimate)'),
    'CupShoulderR': (5.5, 'reference proxy'),
    'CupWall': (1.2, 'reference proxy'),
    'CupRearGap': (0.6, 'reference proxy'),
    'StemD': (7.5, 'reference proxy (estimate)'),
    'HeadD': (12.0, 'reference proxy (estimate)'),
    'HeadT': (1.8, 'reference proxy (estimate)'),
    'HeadGap': (0.4, 'reference proxy'),
    # optional wall bracket in place of the cups: screwed or stuck to the wall, the plate hangs on its studs
    'BracketT': (5.0, 'design: plate rear to wall; at the stop the tab end moves 3.3 mm toward the wall'),
    'BracketInset': (1.0, 'design: bracket outline inside the plate outline'),
    'BracketNotchClear': (1.0, 'design: notch around the lever and its slots, so the lever is free of the bracket'),
    'BracketNotchR': (2.0, 'design: notch corners'),
    'BracketEdgeR': (1.0, 'design: front outer edge'),
    'BracketBedChamfer': (0.6, 'design: wall-side outer edge, against elephant foot'),
    'StudNeckD': (8.4, 'design: in the 9 mm keyhole slot'),
    'StudGap': (0.3, 'design: plate front to the start of the head'),
    'StudHeadD': (11.0, 'design: passes the 14 mm keyhole entry; 45 deg underside prints without support'),
    'StudChamfer': (0.3, 'design: stud top edge'),
    'ScrewY': (46.0, 'design: between the lower keyhole (top Y 32.5) and the lever notch (Y 63.75)'),
    'ScrewDX': (12.0, 'design: screws at X 21 +/- 12, behind the plate'),
    'ScrewClearD': (4.5, 'design: clears #6 (3.5 mm) and #8 (4.2 mm) drywall screws'),
    'ScrewCskD': (9.0, 'design: 90 deg countersink diameter'),
    'ScrewSink': (0.4, 'design: counterbore above the countersink, so the head sits below the bracket face'),
    'ScrewHeadD': (8.3, 'reference: #6 drywall screw bugle head (estimate)'),
    'ScrewShankD': (3.5, 'reference: #6 drywall screw'),
    'ScrewLen': (32.0, 'reference: 1-1/4 in drywall screw'),
}
P = {k: v for k, (v, _) in PARAMS.items()}

# Housing side profile: (y0, y1, outer x left, outer x right, chamfer start z, chamfer inset)
SECTIONS = {'bottom': (4.0, 24.0, 2.0, 40.0, 13.18, 0.99),
            'mid': (26.4, 56.6, 0.0, 42.0, 13.18, 0.99),
            'wide': (58.4, 88.0, -1.0, 43.0, 12.18, 1.41)}
# The cavity runs continuously from the jack end out of the open end. Each Y band takes the inner
# face and chamfer lip of the section at its top end, so in the steps between sections the wall
# clears the narrower housing. The module slides toward -Y, so a band is only ever passed by its own
# section or narrower ones. The walls have fallen to the plate before the S1 switch (Y 79.4).
# The mid band (and the side lips) end where the swoop starts, at Y 44, so the swoop is a plain wall.
TRACK = [('bottom', 23.0), ('mid', 44.0), ('wide', None)]   # (section, band top Y; None = open)
# Skids under the PCB (X ranges). They sit between the tracks swept by the PCB screw heads
# (X 0.6-5.7, 36.3-41.4) and clear of the J5 and J2/J6 through-hole parts.
SKIDS = [(11.0, 13.0), (29.0, 31.0)]
FAR = 400.0   # extent of construction solids that must run past the part


def plate_top():
    return P['DeviceTopY'] + P['DeviceTopInset']


def z_front():
    return P['PCBRearZ'] - P['RestGap']


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
    cx, yt = P['DeviceCx'], plate_top() - P['TopCupDrop']
    return {'UL': (cx - P['TopCupX'], yt), 'UR': (cx + P['TopCupX'], yt),
            'L': (cx, P['LowCupY'])}


def entry_centre(key):
    sx, sy = cup_centres()[key]
    return sx, sy - (P['LowSlot'] if key == 'L' else P['TopSlot'])


def outer_x(side):
    c, t = P['WallClear'], P['RailT']
    return (min(v[2] for v in SECTIONS.values()) - c - t if side == 'L'
            else max(v[3] for v in SECTIONS.values()) + c + t)


def y_end():
    """Outer face of the hood at the jack end."""
    return P['DeviceBottomY'] - P['WallClear'] - P['RailT']


def plan_face():
    """Plate outline: a body flush with the sleeve walls flaring into two round-ended cup wings."""
    zr = z_rear(); top = plate_top()
    xl, xr = outer_x('L'), outer_x('R')
    re = P['KeyEntryD'] / 2 + P['WingWeb']                # wing lobe radius around each entry
    (ulx, uly), (urx, _) = entry_centre('UL'), entry_centre('UR')
    wx0, wx1 = ulx - re, urx + re
    t = 1.0
    parts = [box(xl, xr, y_end(), top, zr, zr + t), box(wx0, wx1, uly, top, zr, zr + t),
             cyl(re, ulx, uly, zr, zr + t), cyl(re, urx, uly, zr, zr + t)]
    return round_face(flat_face(parts, zr), P['FlareR'], P['CornerR'])


def elevation_wire_pts():
    """Side elevation (Y, Z) of the sleeve top: hood slope, flat top, S-swoop, plate."""
    zf, zr, zt = z_front(), z_rear(), z_wall_top()
    y0, z0 = P['DeviceBottomY'], P['EndSlopeZ0']
    y1, z1 = P['EndSlopeY1'], P['HousingTopZ']
    L = math.hypot(y1 - y0, z1 - z0); u = ((y1 - y0) / L, (z1 - z0) / L)
    n = (-u[1], u[0])                                     # outward normal of the housing end slope
    q = (y0 + P['HoodT'] * n[0], z0 + P['HoodT'] * n[1])  # point on the hood's outer slope
    k = u[1] / u[0]
    yc = q[0] + (zt - q[1]) / k                           # slope meets the flat top
    a = math.atan(k); R = P['HoodTopR']; tl = R * math.tan(a / 2)
    p_s = (yc - tl * u[0], zt - tl * u[1])                # tangent point on the slope
    p_f = (yc + tl, zt)                                   # tangent point on the flat
    ctr = (yc + tl, zt - R)
    d = (yc - ctr[0], zt - ctr[1]); dl = math.hypot(*d)
    p_m = (ctr[0] + R * d[0] / dl, ctr[1] + R * d[1] / dl)
    ya = y_end() - 3.0; za = q[1] + (ya - q[0]) * k
    # two equal tangent arcs from (SwoopY0, zt) down to (SwoopY1, zf)
    s0, s1 = P['SwoopY0'], P['SwoopY1']; H = zt - zf; Ls = s1 - s0
    th = 2 * math.atan(H / Ls); Rs = Ls / (2 * math.sin(th))
    c_up = (s0, zt - Rs); c_lo = (s1, zf + Rs)
    m_up = (c_up[0] + Rs * math.sin(th / 2), c_up[1] + Rs * math.cos(th / 2))
    mid = (c_up[0] + Rs * math.sin(th), c_up[1] + Rs * math.cos(th))
    m_lo = (c_lo[0] - Rs * math.sin(th / 2), c_lo[1] - Rs * math.cos(th / 2))
    return dict(start=(ya, zr - 1), ya=(ya, za), p_s=p_s, p_m=p_m, p_f=p_f, s0=(s0, zt),
                m_up=m_up, mid=mid, m_lo=m_lo, s1=(s1, zf), far=(FAR, zf), far_low=(FAR, zr - 1),
                swoop_r=Rs, swoop_deg=math.degrees(th))


def elevation_solid():
    e = elevation_wire_pts(); xa, xb = -FAR / 2, FAR / 2
    P3 = lambda p: V(xa, p[0], p[1])
    edges = [Part.LineSegment(P3(e['start']), P3(e['ya'])), Part.LineSegment(P3(e['ya']), P3(e['p_s'])),
             Part.Arc(P3(e['p_s']), P3(e['p_m']), P3(e['p_f'])), Part.LineSegment(P3(e['p_f']), P3(e['s0'])),
             Part.Arc(P3(e['s0']), P3(e['m_up']), P3(e['mid'])), Part.Arc(P3(e['mid']), P3(e['m_lo']), P3(e['s1'])),
             Part.LineSegment(P3(e['s1']), P3(e['far'])), Part.LineSegment(P3(e['far']), P3(e['far_low'])),
             Part.LineSegment(P3(e['far_low']), P3(e['start']))]
    wire = Part.Wire([g.toShape() for g in edges])
    return Part.Face(wire).extrude(V(xb - xa, 0, 0))


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
    top_edges, bed_edges = [], []
    for e in blank.Edges:
        faces = blank.ancestorsOfType(e, Part.Face)
        if len(faces) != 2:
            continue
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


def cavity():
    """Module space: one prism per Y band (inner faces, lips, inner foot chamfer), clipped at the jack end
    by the housing's chamfered plan corners and its sloped end, both offset by the clearance."""
    zf = z_front(); c = P['WallClear']; ch = P['InnerChamfer']; ztop = z_wall_top() + 5
    he = P['HookEngage']

    def prof(sec, lips):
        _, _, xl, xr, zc, inset = SECTIONS[sec]
        il, ir, zl = xl - c, xr + c, zc + c
        if lips:
            zt = zc + he * (P['HousingTopZ'] - zc) / inset + c
            tl, tr = xl + (he - c), xr - (he - c)
        else:                                             # same vertices, the lip faces run straight up
            tl, tr, zt = il, ir, zl + he
        return [(il + ch, zf), (ir - ch, zf), (ir, zf + ch), (ir, zl), (tr, zt), (tr, ztop),
                (tl, ztop), (tl, zt), (il, zl), (il, zf + ch)]

    def ramp(p0, y0, p1, y1):
        w = [Part.makePolygon([V(x, y, z) for x, z in pr + pr[:1]]) for pr, y in ((p0, y0), (p1, y1))]
        return Part.makeLoft(w, True, True)

    # Bands follow the housing sections, except that the side lips and the mid band end where the swoop
    # starts: the cavity tapers out to the wide band at 45 deg in plan on the flat top, so the swoop is a
    # plain 2 mm wall. The housing's mid section is only guided below Y 44 (it passes the swoop with 1.2
    # mm a side), and the wide section never reaches the swoop's lower end.
    (_, y_bm), (_, le), _ = TRACK
    mid, wide = prof('mid', True), prof('wide', False)
    taper = (mid[6][0] - wide[6][0])                      # lip tip to the wide inner face, along X
    parts = [prism_xz(prof('bottom', True), -10.0, y_bm), prism_xz(mid, y_bm, le - taper),
             ramp(mid, le - taper, wide, le), prism_xz(wide, le, FAR)]
    # jack end: plan corners
    _, _, bxl, bxr, _, _ = SECTIONS['bottom']
    yb0, cc = P['DeviceBottomY'], P['EndCornerC']
    foot = [(bxl, yb0 + cc), (bxl + cc, yb0), (bxr - cc, yb0), (bxr, yb0 + cc), (bxr, 60.0), (bxl, 60.0)]
    zr = z_rear()
    plan = prism(foot, zr, zr + 1)
    plan_f = [f for f in plan.Faces if abs(f.CenterOfMass.z - zr) < 1e-6][0].makeOffset2D(c, join=0)
    plan = plan_f.extrude(V(0, 0, 40))
    # jack end: end lip that follows the housing's end slope
    y0, z0, y1, z1 = yb0, P['EndSlopeZ0'], P['EndSlopeY1'], P['HousingTopZ']
    k = (z1 - z0) / (y1 - y0); L = math.hypot(y1 - y0, z1 - z0)
    n = (-(z1 - z0) / L, (y1 - y0) / L)
    q = (y0 + c * n[0], z0 + c * n[1])
    yi, yt = yb0 - c, yb0 + (he - c) + c                  # inner face, lip tip (0.6 over the end)
    zat = lambda y: q[1] + (y - q[0]) * k
    end = prism_yz([(yi + ch, zf), (FAR, zf), (FAR, ztop), (yt, ztop), (yt, zat(yt)), (yi, zat(yi)),
                    (yi, zf + ch)], -FAR / 2, FAR / 2)
    jack_end = parts[0].common(plan).common(end)
    return jack_end.fuse(parts[1:]).removeSplitter()


def jack_opening():
    """Round-cornered opening through the hood for the 3.5 mm plug."""
    zf = z_front(); x0, x1 = P['JackOpenX0'], P['JackOpenX1']
    pts = [V(x0, -6.0, zf), V(x1, -6.0, zf), V(x1, -6.0, z_wall_top() + 6), V(x0, -6.0, z_wall_top() + 6)]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    face = face.makeOffset2D(-P['JackOpenR'], join=0).makeOffset2D(P['JackOpenR'], join=0)
    # the convex rounding also rounds the top corners, which are outside the part; keep the bottom flat
    return face.extrude(V(0, P['DeviceBottomY'] + P['HookEngage'] + 1.0 + 6.0, 0))


def keyholes():
    zf = z_front(); zr = z_rear()
    cut = []
    w = P['KeySlotW'] / 2
    for key, (sx, sy) in cup_centres().items():
        ex, ey = entry_centre(key)
        cut += [cyl(P['KeyEntryD'] / 2, sx, ey, zr - 1, zf + 1), cyl(w, sx, sy, zr - 1, zf + 1),
                box(sx - w, sx + w, ey, sy, zr - 1, zf + 1)]
    return cut


def screw_centres():
    return [(P['DeviceCx'] - P['ScrewDX'], P['ScrewY']), (P['DeviceCx'] + P['ScrewDX'], P['ScrewY'])]


def stud(x, y):
    """Keyhole stud: a neck through the slot and a head with a 45 deg underside, so the bracket prints
    upright without support. The top is level with the cup heads, so the lower one clears the PCB."""
    zr, zf = z_rear(), z_front()
    rn, rh, c = P['StudNeckD'] / 2, P['StudHeadD'] / 2, P['StudChamfer']
    z0 = zf + P['StudGap']; zt = zf + P['HeadGap'] + P['HeadT']
    pts = [(0, zr - 0.5), (rn, zr - 0.5), (rn, z0), (rh, z0 + rh - rn), (rh, zt - c), (rh - c, zt), (0, zt)]
    face = Part.Face(Part.makePolygon([V(x + r, y, z) for r, z in pts + pts[:1]]))
    return Part.Solid(face.revolve(V(x, y, 0), V(0, 0, 1), 360))


def wall_bracket():
    """One-piece bracket in place of the cups, so the three studs are aligned for you. It follows the
    plate outline with a notch that leaves the lever free to move toward the wall, and has two
    countersunk screw holes behind the plate. The flat rear also takes adhesive strips."""
    zr = z_rear(); t = P['BracketT']; c = P['BracketNotchClear']
    notch = box(P['LatchX0'] - P['LatchSlot'] - c, P['LatchX1'] + P['LatchSlot'] + c,
                P['LatchRootY'] - P['LatchReliefD'] / 2 - c, FAR, zr - 1, zr + 1)
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
    just below the PCB rear, then a 45 deg back slope down to the plate front."""
    zt0 = z_front() - 0.01
    zt = P['PCBRearZ'] + P['ToothRise']
    ys = P['DeviceTopY'] + P['ToothClear']
    yf = ys + P['ToothFlat']
    z_r = P['PCBRearZ'] - 0.5
    yr = yf + (zt - z_r) / math.tan(math.radians(P['RampAngle']))
    yb = yr + (z_r - zt0)
    return [(ys, zt0), (ys, zt), (yf, zt), (yr, z_r), (yb, zt0)]


def latch_cut():
    """Two slots from the root out through the top edge free the lever; round stress-relief ends at the
    root; the flex zone is thinned from the front; grip grooves cross the press tab beyond the teeth."""
    zf, zr = z_front(), z_rear(); g = P['LatchSlot']; y0 = P['LatchRootY']
    x0, x1 = P['LatchX0'], P['LatchX1']
    rr = P['LatchReliefD'] / 2
    cuts = []
    for xa in (x0 - g, x1):
        cuts += [box(xa, xa + g, y0, FAR, zr - 1, zf + 1), cyl(rr, xa + g / 2, y0, zr - 1, zf + 1)]
    zt = zr + P['LatchT']; ramp = P['LatchRootRamp']; ye = P['LatchFlexEndY']
    cuts.append(prism_yz([(y0, zf), (y0 + ramp, zt), (ye, zt), (ye + ramp, zf), (ye + ramp, zf + 1), (y0, zf + 1)], x0, x1))
    y = max(y for y, _ in tooth_profile()) + P['GripStart']
    r = P['GripW'] / 2; zb = zf - P['GripDepth'] + r       # axis of the round groove bottom
    for i in range(int(P['GripN'])):
        yc = y + i * P['GripPitch']
        cuts += [Part.makeCylinder(r, x1 - x0 - 3.0, V(x0 + 1.5, yc, zb), V(1, 0, 0)),
                 box(x0 + 1.5, x1 - 1.5, yc - r, yc + r, zb, zf + 1)]
    return cuts


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


def skids():
    zf = z_front(); h = P['PCBRearZ'] - zf; y0, y1 = P['SkidY0'], P['SkidY1']
    prof = [(y0, zf - 0.01), (y1, zf - 0.01), (y1 - h, P['PCBRearZ']), (y0 + h, P['PCBRearZ'])]
    return [prism_yz(prof, xa, xb) for xa, xb in SKIDS]


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


def fillet_inner_top(shape):
    """Round the inner top edges of the sleeve: lip tips, the inner faces where the swoop crosses
    them, the band steps and the hood lip. They are edges between a vertical face and an upward
    face inside the module footprint."""
    zf = z_front(); x0 = min(v[2] for v in SECTIONS.values()) - 0.3; x1 = max(v[3] for v in SECTIONS.values()) + 0.3
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
        if up.z > 0.2 and not (abs(up.z - 1) < 1e-6 and abs(faces[vert.index(False)].CenterOfMass.z - zf) < 1e-6):
            sel.append(e)
    r = P['InnerEdgeR']
    try:
        s = shape.makeFillet(r, sel)
        if s.isValid() and len(s.Solids) == 1:
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
    if s is not shape:
        return s
    chosen = []                                           # together they fail: add them one at a time
    for e in ok:
        try:
            t = shape.makeFillet(r, chosen + [e])
            if t.isValid() and len(t.Solids) == 1:
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
        if b.XMin < x0 - 0.01 or b.XMax > x1 + 0.01 or b.YMax > P['DeviceBottomY'] + 1 or b.ZMax < zf + 0.05:
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
    kboxes = []
    for key, (sx, sy) in cup_centres().items():
        ex, ey = entry_centre(key)
        kboxes.append((sx - w, sx + w, ey - w, sy + P['KeySlotW'] / 2 + 0.1))
    body = fillet_edges_in(body, kboxes, P['KeyEdgeR'], zf, 'keyholes')
    body = body.cut(latch_cut()).removeSplitter()
    g = P['LatchSlot'] + 0.1
    body = fillet_edges_in(body, [(P['LatchX0'] - g - 2, P['LatchX1'] + g + 2, P['LatchRootY'] - 2,
                                   plate_top() + 1)], P['SlotEdgeR'], zf, 'lever slots',
                           exclude=[(P['LatchX0'] - 0.01, P['LatchX1'] + 0.01, P['LatchRootY'] - 0.01,
                                     P['LatchRootY'] + 0.01)])
    fingers, pockets = stop_parts()
    rails, corner_cuts = pull_stop_parts()
    body = body.cut(pockets + corner_cuts).removeSplitter()
    printed = body.fuse(skids() + latch_teeth() + fingers + rails).removeSplitter()
    return printed


def cup_shape(x, y):
    zf = z_front(); zr = z_rear()
    rim = zr - P['CupDepth']
    hgt = P['CupDepth'] - P['CupRearGap']
    outside = Part.makeCone(P['CupD'] / 2, P['CupShoulderR'], hgt, V(x, y, rim))
    inside = Part.makeCone(P['CupD'] / 2 - P['CupWall'], P['CupShoulderR'] - P['CupWall'], hgt - 1.5,
                           V(x, y, rim - 0.1))
    stem = cyl(P['StemD'] / 2, x, y, zr - P['CupRearGap'] - 0.5, zf + P['HeadGap'])
    head = cyl(P['HeadD'] / 2, x, y, zf + P['HeadGap'], zf + P['HeadGap'] + P['HeadT'])
    return outside.cut(inside).fuse([stem, head]).removeSplitter()


def design_checks(printed, black, blue, bracket):
    """Numbers worth reading after a change: keyhole webs, latch strain, overall size, colour split,
    wall bracket fit."""
    outline = plan_face()
    for key in cup_centres():
        sx, sy = cup_centres()[key]; ex, ey = entry_centre(key)
        w = P['KeySlotW'] / 2; zr = z_rear()
        kf = flat_face([cyl(P['KeyEntryD'] / 2, ex, ey, zr, zr + 1), cyl(w, sx, sy, zr, zr + 1),
                        box(sx - w, sx + w, ey, sy, zr, zr + 1)], zr)
        web = min(kf.distToShape(e)[0] for e in outline.Edges)
        print('CHECK keyhole %s web to plate edge %.2f mm' % (key, web))
    zf = z_front()
    bb = bracket.BoundBox
    print('CHECK bracket valid %s, solids %d, %.1f x %.1f x %.1f mm, volume %.1f cm3' % (
        bracket.isValid(), len(bracket.Solids), bb.XLength, bb.YLength, bb.ZLength, bracket.Volume / 1000))
    print('CHECK bracket overlap with the plate %.4f mm3' % bracket.common(printed).Volume)
    for key, (x, y) in cup_centres().items():
        print('CHECK stud %s gap to the plate %.2f mm' % (key, stud(x, y).distToShape(printed)[0]))
    print('CHECK stud top to PCB rear %.2f mm' % (P['PCBRearZ'] - (zf + P['HeadGap'] + P['HeadT'])))
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
    print('CHECK stop: teeth travel %.2f mm (%.2f below the PCB rear), lever strain %.2f %%, finger root stress %.1f MPa per 10 N'
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
    return strain


def tagged(doc, name, label, shape, colour=None, transparency=0):
    o = doc.addObject('Part::Feature', name); o.Label = label; o.Shape = shape
    o.addProperty('App::PropertyString', 'Concept', TAG, 'Created by build_snap_backplate.py'); o.Concept = TAG
    if colour and App.GuiUp:
        o.ViewObject.ShapeColor = colour; o.ViewObject.Transparency = transparency
    return o


def parameter_sheet(doc):
    sheet = doc.addObject('Spreadsheet::Sheet', 'SnapBackplateParameters')
    sheet.Label = 'Snap backplate parameters'
    sheet.set('A1', 'Parameter'); sheet.set('B1', 'Value (mm)'); sheet.set('C1', 'Basis')
    for i, (k, (v, note)) in enumerate(PARAMS.items(), 2):
        sheet.set('A%d' % i, k); sheet.set('B%d' % i, '%g' % v); sheet.set('C%d' % i, note)
    return sheet


PLATE_COLOUR = (0.13, 0.13, 0.14)    # black print
TOUCH_COLOUR = (0.09, 0.42, 0.93)    # blue touch points (placeholder for the product blue)
CUP_COLOUR = (0.80, 0.84, 0.88)
SCREW_COLOUR = (0.25, 0.25, 0.27)


def main():
    doc = App.openDocument(os.path.join(CAD, 'DTT.FCStd'))
    # The backplate replaces the hook-and-loop backing; hide it and the exploded copies.
    for n in ('LoopBacking', 'ExplodedView'):
        o = doc.getObject(n)
        if o is not None:
            o.Visibility = False
    printed = printed_part()
    black, blue = split_colours(printed)
    bracket = wall_bracket()
    design_checks(printed, black, blue, bracket)
    group = doc.addObject('App::Part', 'SnapBackplate'); group.Label = 'Snap backplate'
    parameter_sheet(doc)
    bodies = [tagged(doc, 'SnapBackplatePrinted', 'Snap backplate - printed, black', black, PLATE_COLOUR),
              tagged(doc, 'SnapBackplateTouch', 'Snap backplate - printed, blue touch point', blue, TOUCH_COLOUR)]
    for o in bodies:
        group.addObject(o)
    for key, (x, y) in cup_centres().items():
        group.addObject(tagged(doc, 'SnapCup' + key, 'Suction cup %s (proxy)' % key, cup_shape(x, y), CUP_COLOUR, 35))
    # the bracket and its screws take the place of the cups, so they start hidden
    br = tagged(doc, 'SnapWallBracket', 'Wall bracket (in place of the cups; screws or adhesive strips)', bracket,
                PLATE_COLOUR)
    br.Visibility = False
    group.addObject(br)
    for key, (x, y) in zip(('L', 'R'), screw_centres()):
        o = tagged(doc, 'SnapScrew' + key, 'Wall screw %s (bracket, proxy)' % key, screw_shape(x, y), SCREW_COLOUR)
        o.Visibility = False
        group.addObject(o)
    doc.recompute()
    os.makedirs(HERE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    if App.GuiUp:
        import ImportGui                                  # keeps the two bodies and their colours
        ImportGui.export(bodies, os.path.join(OUT, 'DTT-Snap-Backplate.step'))
    else:
        Part.makeCompound([black, blue]).exportStep(os.path.join(OUT, 'DTT-Snap-Backplate.step'))
    bracket.exportStep(os.path.join(OUT, 'DTT-Snap-Backplate-Wall-Bracket.step'))
    import MeshPart
    for shape, suffix in ((printed, ''), (black, '-Black'), (blue, '-Blue'), (bracket, '-Wall-Bracket')):
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False).write(
            os.path.join(OUT, 'DTT-Snap-Backplate%s.stl' % suffix))
    if App.GuiUp:
        render(doc)
    doc.saveAs(os.path.join(HERE, 'DTT-Snap-Backplate-Concept.FCStd'))
    return doc


def _rgb_uint(r, g, b):
    return (int(r * 255) << 24) | (int(g * 255) << 16) | (int(b * 255) << 8)


def render(doc):
    import FreeCADGui as Gui
    pv = App.ParamGet('User parameter:BaseApp/Preferences/View')
    pv.SetBool('ShowNaviCube', False); pv.SetBool('ShowAxisCross', False)
    view = Gui.getDocument(doc.Name).ActiveView
    printed = doc.getObject('SnapBackplatePrinted')
    housing = doc.getObject('Cover___V3_v5'); shell = doc.getObject('Part__Feature001')
    housing.Visibility = True
    tops = [o for o in doc.RootObjects if o.TypeId == 'App::Part']
    saved = {o.Name: o.Visibility for o in tops}
    # standard previews (same set as the baseline concept)
    shell.ViewObject.Transparency = 55
    view.viewIsometric(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Assembled.png'), 1400, 1400, 'White')
    for o in tops:
        o.Visibility = o.Name == 'SnapBackplate'
    housing.Visibility = False
    view.viewIsometric(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Front.png'), 1400, 1400, 'White')
    view.setCameraOrientation(App.Rotation(V(0, 1, 0), 180)); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Rear.png'), 1400, 1400, 'White')
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    housing.Visibility = True
    view.viewRight(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Side.png'), 1400, 1400, 'White')
    # hero renders: wall-mounted orientation (USB-C end up), front three-quarter from above right,
    # shaded without edge lines, soft gradient backdrop
    pv.SetBool('Gradient', True); pv.SetBool('Simple', False)
    pv.SetUnsigned('BackgroundColor2', _rgb_uint(0.93, 0.93, 0.95))
    pv.SetUnsigned('BackgroundColor3', _rgb_uint(0.70, 0.71, 0.75))
    for o in (printed, doc.getObject('SnapBackplateTouch')):
        o.ViewObject.DisplayMode = 'Shaded'
    for k in ('UL', 'UR', 'L'):
        doc.getObject('SnapCup' + k).ViewObject.DisplayMode = 'Shaded'
    shell.ViewObject.Transparency = 40
    cam = App.Rotation(V(0, 1, 0), 36).multiply(App.Rotation(V(1, 0, 0), -20))
    view.setCameraOrientation(cam); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Hero.png'), 1600, 1600, 'Current')
    for o in tops:
        o.Visibility = o.Name == 'SnapBackplate'
    housing.Visibility = False
    for k in ('UL', 'UR', 'L'):
        doc.getObject('SnapCup' + k).Visibility = False
    view.setCameraOrientation(cam); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Hero-Part.png'), 1600, 1600, 'Current')
    for k in ('UL', 'UR', 'L'):
        doc.getObject('SnapCup' + k).Visibility = True
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    housing.Visibility = True


if __name__ == '__main__' or True:
    DOCUMENT = main()
