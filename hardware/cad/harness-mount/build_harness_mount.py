"""Build the DTT strap-on harness mount: the snap cradle on a plate that also holds a dildo, with strap slots.

Run from the repository root under the FreeCAD GUI (needed for colours and previews):
    freecad hardware/cad/harness-mount/build_harness_mount.py
or headless with xvfb-run. It reuses the snap backplate builder (sleeve, lever, latch, stops) without
running it, and writes one .FCStd per toy interface beside this script, STEP/STL exports in
hardware/production-exports/cad/harness-mount/ and the images in images/.

The plate is the Double Double backplate with the cups taken out: the case slides in USB-C end first
toward the navel, and the toy sits right under the jack end, in front of the ToF sensor. Two toy
interfaces (HARNESS_VARIANTS=ring,thread):
- ring: the strap-on O-ring standard. A printed ring drops into a socket from the body side, its flange
  flush with the plate rear, and a flared-base dildo goes through it from behind. Rings for 1.25, 1.5
  and 1.75 in toys share one socket.
- thread: the OSSM 24 mm thread, with the Double Double backplate's printed hex flange screw (no cup).
Like the soft harnesses people find comfortable (Joque, RodeoH, Aslan Jaguar), the only hard part is
small: the printed core is just the cradle and the toy lobe. It sits on a soft front panel, not printed:
leather (or neoprene) over foam padding, lined, with the 1 in (25 mm) waist and leg webbing sewn to its
hip ears and tip. The panel's body side follows a concave sheet (rear_z) that sits over the pubic mound
and curls back round the hips and between the legs; the core's rear is filled down to it. Four Chicago
screws through the core and the panel's leather hold them together, and in the ring version the panel
is also clamped between the core and the ring's flange.

Device coordinates as in the snap backplate: X across, Y along the case (USB-C end at +Y), Z out of the
front face. The wearer is at -Z; the plate prints rear face down on supports.
"""
import math, os, sys
import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
HERE = os.path.join(ROOT, 'hardware', 'cad', 'harness-mount')
os.environ['SNAP_NO_MAIN'] = '1'
sys.path.insert(0, os.path.join(ROOT, 'hardware', 'cad', 'snap-backplate'))
import build_snap_backplate as SB   # noqa: E402

V, P, box, cyl, prism = SB.V, SB.P, SB.box, SB.cyl, SB.prism
SB.IMAGES = os.path.join(HERE, 'images')
SB.OUT = os.path.join(ROOT, 'hardware', 'production-exports', 'cad', 'harness-mount')

# name: (value, basis)
PARAMS = {
    # straps
    'StrapW': (25.4, 'design: 1 in webbing, the common harness strap; 25 mm webbing fits too'),
    'WaistTabX': (88.0, 'design: hip corners of the V panel; the waist straps run over them'),
    'WaistTabY': (95.0, 'design: waist straps across the top of the V, level with the upper case'),
    'SlotW': (26.5, 'design: strap slot length, for 1 in webbing or elastic'),
    'SlotT': (5.5, 'design: strap slot width, for a doubled strap end'),
    'SlotTabT': (5.5, 'design: strap tab height off the panel front'),
    'SlotBarW': (4.5, 'design: the bar the strap wraps, outboard of the slot'),
    'SlotTunnel': (2.5, 'design: gap under the bar for the strap, over the panel front'),
    'LegSlotX': (20.0, 'design: leg slots this far either side of the toy axis, under the lobe, pointing down the leg crease'),
    # ring interface (strap-on O-ring standard)
    'SocketD': (50.0, 'design: one socket for every ring; a 1.75 in ring keeps a 2.8 mm wall'),
    'SocketClear': (0.2, 'design: radial clearance of the ring in its socket'),
    'FlangeD': (60.0, 'design: ring flange, flush with the plate rear in a counterbore'),
    'FlangeT': (2.0, 'design: ring flange thickness'),
    'CollarH': (4.0, 'design: ring stands this far proud of the boss, to steady the toy'),
    'RingTopR': (1.5, 'design: rounded inner top edge of the ring'),
    'RingID': (38.1, 'reference: 1.5 in, the most common harness ring; 31.75 and 44.45 are exported too'),
    'RingBossD': (56.0, 'design: boss around the socket on the plate front'),
    'RingBossT': (3.0, 'design: boss height, so the ring sits 9 mm deep'),
    'RingGap': (3.0, 'design: boss edge to the hood; a straight 3.5 mm plug does not fit, use a right-angle one'),
    'ToyBaseD': (60.0, 'reference proxy (estimate): flared dildo base behind the plate; a wider one rests on the curved rear'),
    'ToyBaseT': (6.0, 'reference proxy (estimate)'),
    # soft front panel (sewn, not printed) and its body-side curve, fitted to a reference body; tune on a person
    'PadT': (5.0, 'design: soft panel: 2 mm leather, about 3 mm foam and lining, behind the core and out to the ears and tip'),
    'PadRX': (225.0, 'fit: across the hips, to the MakeHuman CC0 average young female (reference/), worn tilted 14 deg'),
    'PadRUp': (2000.0, 'fit: up the lower belly, nearly flat once the harness tilts 14 deg to lie on it'),
    'PadRDown': (160.0, 'fit: curling back over the mons toward the crotch, ring over the pubic bone'),
    'PadEdgeR': (2.0, 'design: rounded panel edges (bound or rolled leather)'),
    'PadBaseHole': (46.0, 'design: ring version: the shaft passes, the flared base sits on the soft panel, which keeps the ring flange in'),
    'LeatherT': (2.0, 'reference: front leather of the panel, which the screws pass; the rest of PadT is foam and lining'),
    'ScrewHoleD': (5.4, 'reference: Chicago screw (binding post) barrel 5 mm, for 8-10 mm grip'),
    'ScrewHeadD': (10.5, 'reference: counterbore for the 10 mm post head in the cradle floor, under the case'),
    'ScrewHeadT': (1.8, 'reference: post head 1.5 mm, sunk below the floor'),
}
H = {k: v for k, (v, _) in PARAMS.items()}
RING_SIZES = (31.75, 38.1, 44.45)
MODE = 'ring'


def axis():
    """Toy axis (X, Y): on the centreline, below the hood. The thread version keeps the Double Double
    spacing (DDGap below the hood, for a straight plug); the ring version comes up close."""
    if MODE == 'thread':
        return P['DeviceCx'], SB.y_end() - P['DDGap'] - P['DDBaseD'] / 2
    return P['DeviceCx'], SB.y_end() - H['RingGap'] - H['RingBossD'] / 2


def lobe_r():
    """Radius of the plate's round lobe round the toy: past the boss, and in the ring version past the
    ring flange counterbore."""
    hw = SB.ENC.half_width(P['DeviceBottomY']) + P['WallClear'] + P['RailT']
    if MODE == 'ring':
        return max(hw, H['RingBossD'] / 2 + 2.0, H['FlangeD'] / 2 + H['SocketClear'] + 2.8)
    return max(hw, P['DDBossD'] / 2 + 2.0)


# panel outline (x from the centreline, y), right half, top to bottom; mirrored for the left
PANEL = [(0, 120), (46, 120), (80, 116), (94, 106), (90, 90), (68, 52), (58, 14), (58, -20), (56, -48),
         (48, -68), (38, -80)]


def panel_face():
    """The soft panel in plan: the classic strap-on V, wide at the hips for the waist D-rings and
    narrowing to a round point under the toy, wide enough there for foam under the leg slots."""
    cx = P['DeviceCx']; zr = SB.z_rear()
    pts = [V(cx + x, y, zr) for x, y in PANEL] + [V(cx - x, y, zr) for x, y in reversed(PANEL[1:])]
    pts.insert(len(PANEL), V(cx, -88, zr))
    c = Part.BSplineCurve(); c.interpolate(pts, PeriodicFlag=True)
    return Part.Face(Part.Wire(c.toShape()))


def pegs():
    cx = P['DeviceCx']
    return [(cx - 15, 15.0), (cx + 15, 15.0), (cx - 15, 48.0), (cx + 15, 48.0)]


def rear_z(x, y):
    """Z of the plate's rear face: concave to sit over the pubic mound, at the flat plate's rear on the
    toy axis and sweeping back toward the hips, up the belly and down between the legs."""
    ax, ay = axis()
    sag = lambda R, d: R - math.sqrt(max(R * R - d * d, 0.0))
    dy = y - ay
    return SB.z_rear() - sag(H['PadRX'], x - ax) - sag(H['PadRUp'] if dy > 0 else H['PadRDown'], dy)


def rear_surface():
    """The rear face as a B-spline sheet over the whole plate."""
    ax, ay = axis()
    xs = [ax - 102 + 6 * i for i in range(35)]
    ys = [ay - 60 + 6 * j for j in range(int((SB.plate_top() + 70 - ay) / 6) + 1)]
    s = Part.BSplineSurface()
    s.interpolate([[V(x, y, rear_z(x, y)) for y in ys] for x in xs])
    return s.toShape()


def core_face():
    """Outline of the part kept flat at the rear of its front: the sleeve's footprint, the plate past the
    case top, and the round lobe round the toy (the boss sits on it)."""
    zr = SB.z_rear(); t = 1.0; cx = P['DeviceCx']; top = SB.plate_top()
    xl, xr = SB.outer_x('L'), SB.outer_x('R')
    parts = [SB.case_face(P['WallClear'] + P['RailT'], zr).extrude(V(0, 0, t)),
             box(xl, xr, P['DeviceTopY'] - 10, top, zr, zr + t)]
    ax, ay = axis()
    hw = SB.ENC.half_width(P['DeviceBottomY']) + P['WallClear'] + P['RailT']
    rb = lobe_r()
    parts += [box(cx - hw, cx + hw, ay, P['DeviceBottomY'] + 10, zr, zr + t), cyl(rb, cx, ay, zr, zr + t)]
    return SB.round_face(SB.flat_face(parts, zr), P['FlareR'], P['CornerR'])


def core_plan(z0, z1):
    f = core_face().translated(V(0, 0, z0 - SB.z_rear()))
    return f.extrude(V(0, 0, z1 - z0))


def lever_zone(z0, z1):
    """The lever, its slots and the stops: left as the flat plate with nothing behind it, so the
    lever can still be pressed toward the body."""
    g, w = P['LatchSlot'], 2.0
    return box(P['LatchX0'] - g - w, P['LatchX1'] + g + w, P['LatchRootY'] - P['LatchReliefD'] / 2 - w, 500, z0, z1)


def slot_frames():
    """Where the strap slots sit: (edge point of the core outline in plan, outward direction), for the
    waist slots on the sides of the upper case and the leg slots on the lobe round the toy."""
    cx = P['DeviceCx']; ax, ay = axis(); wire = core_face().OuterWire; out = []
    for s in (1, -1):
        for o, d in ((V(cx, H['WaistTabY'], 0), V(s, 0, 0)), (V(ax + s * H['LegSlotX'], ay, 0), V(0, -1, 0))):
            o.z = SB.z_rear()
            hits = Part.LineSegment(o, o + d * 200).toShape().section(wire).Vertexes
            e = max((v.Point for v in hits), key=lambda q: (q - o).Length)
            out.append((e, d))
    return out


def slot_plan(e, d, u0, u1, h, z0=-100.0, z1=100.0):
    """A prism over the strap tab's rectangle: u0..u1 out along d from the core edge e, half width h."""
    t = V(-d.y, d.x, 0)
    pts = [e + d * u0 + t * h, e + d * u1 + t * h, e + d * u1 - t * h, e + d * u0 - t * h]
    pts = [V(q.x, q.y, z0) for q in pts]
    f = Part.Face(Part.makePolygon(pts + pts[:1]))
    return f, f.extrude(V(0, 0, z1 - z0))


SLOT_U = (-6.0, 3.0)   # tab from 6 mm inside the core edge; slot starts 3 mm outside it


def slot_tabs():
    """Printed strap tabs on the sides of the core, lying on the panel front: a slot and the bar outboard
    of it, which stands SlotTunnel off the panel so the strap wraps it and is sewn back on itself. The
    rings and buckles are gone; the foam is between the hardware and the skin."""
    rs = rear_surface(); tabs = []
    u0, us = SLOT_U; u1 = us + H['SlotT'] + H['SlotBarW']; h = H['SlotW'] / 2 + 3.25
    for e, d in slot_frames():
        f, _ = slot_plan(e, d, u0, u1, h)
        plan = SB.round_face(f, 0, 3.0).extrude(V(0, 0, 200))
        tab = rs.extrude(V(0, 0, H['SlotTabT'])).common(plan).removeSplitter()
        tab = tab.cut(slot_plan(e, d, us, us + H['SlotT'], H['SlotW'] / 2)[1])
        tunnel = rs.translated(V(0, 0, -1)).extrude(V(0, 0, H['SlotTunnel'] + 1)).common(
            slot_plan(e, d, us, u1 + 1, H['SlotW'] / 2 + 0.5)[1])
        tabs.append(tab.cut(tunnel).removeSplitter())
    return tabs


def slot_bars():
    """Centre of each bar on its outer face and the outward direction, for the strap routing."""
    us = SLOT_U[1] + H['SlotT'] + H['SlotBarW'] / 2
    return [(V((e + d * us).x, (e + d * us).y, rear_z((e + d * us).x, (e + d * us).y) + H['SlotTabT']), d)
            for e, d in slot_frames()]


def pad():
    """The soft front panel: an even layer behind the concave rear face over the panel outline, open
    behind the lever, with a hole for the toy shaft (ring) and the screw holes through its leather, pocketed
    in the foam for the screw heads. The straps hang off the core, so the panel is plain."""
    rs = rear_surface()
    layer = rs.extrude(V(0, 0, -H['PadT']))
    prism = panel_face().extrude(V(0, 0, 120)).translated(V(0, 0, -60))
    blank = prism.common(layer).removeSplitter()
    edges = [e for e in blank.Edges if not (e.BoundBox.XLength < 1e-3 and e.BoundBox.YLength < 1e-3)
             and min(f.normalAt(0, 0).z ** 2 for f in blank.ancestorsOfType(e, Part.Face)) < 0.5]
    blank = SB.try_fillet(blank, edges, (H['PadEdgeR'], H['PadEdgeR'] * 0.5), 'panel edges')
    cuts = [lever_zone(-100, 100).cut(box(-500, 500, -500, P['LatchRootY'] - 20, -100, 100))]
    if MODE == 'ring':
        ax, ay = axis(); cuts.append(cyl(H['PadBaseHole'] / 2, ax, ay, -100, 100))
    for x, y in pegs():
        z = rear_z(x, y) - H['LeatherT']
        cuts += [cyl(H['ScrewHoleD'] / 2, x, y, z - 1, 50), cyl(H['ScrewHeadD'] / 2, x, y, z - 1.6, z + 0.01)]
    return blank.cut(cuts).removeSplitter()


FOAM_INSET = 5.0     # foam stops short of the edge, so the edge stitching goes through leather only


def pattern(padshape, path):
    """Flat cut pattern, 1:1 in mm, as DXF (R12, layers CUT and MARK) and SVG: the leather shell (with the
    Chicago screw holes), the foam (inset, with pockets for the screw heads) and the lining (which covers the
    screw heads). MARK (dashed blue) is where the core sits. The panel is only a few mm deep over its width,
    so its outline in plan is the flat pattern."""
    rear = max(padshape.Faces, key=lambda f: f.Area if f.normalAt(*f.Surface.parameter(f.CenterOfMass)).z < -0.5 else 0)
    flat = lambda w: [(q.x, q.y) for q in w.discretize(Distance=1.0)]
    outer = flat(rear.OuterWire)
    holes = [flat(w) for w in rear.Wires if not w.isSame(rear.OuterWire)]
    circle = lambda x, y, r: [(x + r * math.cos(2 * math.pi * k / 48), y + r * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    g, w = P['LatchSlot'], 2.0   # inset from the panel outline and the lever notch (offsetting the polygon can fail)
    y0 = P['LatchRootY'] - P['LatchReliefD'] / 2 - w
    notch = Part.Face(Part.makePolygon([V(P['LatchX0'] - g - w, y0, 0), V(P['LatchX1'] + g + w, y0, 0),
                                        V(P['LatchX1'] + g + w, 500, 0), V(P['LatchX0'] - g - w, 500, 0), V(P['LatchX0'] - g - w, y0, 0)]))
    plan = [V(q.x, q.y, 0) for q in panel_face().OuterWire.discretize(Distance=1.0)]
    inset = Part.Face(Part.makePolygon(plan + plan[:1])).makeOffset2D(-FOAM_INSET, join=0)
    top = rear.OuterWire.BoundBox.YMax - FOAM_INSET   # the panel's top edge is straight, where the rear sheet ends
    inset = inset.common(Part.Face(Part.makePolygon([V(-500, -500, 0), V(500, -500, 0), V(500, top, 0), V(-500, top, 0), V(-500, -500, 0)])))
    foam = flat(max(inset.cut(notch.makeOffset2D(FOAM_INSET, join=0)).Faces, key=lambda f: f.Area).OuterWire)
    marks = [flat(core_face().OuterWire)]
    x0, y0 = min(x for x, _ in outer), min(y for _, y in outer)
    w = max(x for x, _ in outer) - x0 + 20
    pieces = [('Shell, leather x1', [outer] + holes + [circle(x, y, H['ScrewHoleD'] / 2) for x, y in pegs()], marks, 0),
              ('Foam x1', [foam] + holes + [circle(x, y, H['ScrewHeadD'] / 2) for x, y in pegs()], [], w),
              ('Lining x1', [outer] + holes, [], 2 * w)]
    loops = []
    for label, ps, ms, dx in pieces:
        loops += [(label, [(x - x0 + dx, y - y0) for x, y in pl], False) for pl in ps]
        loops += [(label, [(x - x0 + dx, y - y0) for x, y in pl], True) for pl in ms]
    with open(path + '.dxf', 'w') as f:
        f.write('0\nSECTION\n2\nENTITIES\n')
        for _, pl, mark in loops:
            layer = 'MARK' if mark else 'CUT'
            f.write('0\nPOLYLINE\n8\n%s\n66\n1\n70\n1\n' % layer)
            for x, y in pl:
                f.write('0\nVERTEX\n8\n%s\n10\n%.3f\n20\n%.3f\n' % (layer, x, y))
            f.write('0\nSEQEND\n')
        f.write('0\nENDSEC\n0\nEOF\n')
    xmax = max(x for _, pl, _ in loops for x, _ in pl) + 10; ymax = max(y for _, pl, _ in loops for _, y in pl) + 20
    with open(path + '.svg', 'w') as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="%.0fmm" height="%.0fmm" viewBox="-10 -10 %.1f %.1f">\n'
                '<rect x="-10" y="-10" width="100%%" height="100%%" fill="white"/>\n' % (xmax + 10, ymax + 30, xmax + 10, ymax + 30))
        for label, pl, mark in loops:
            d = 'M' + ' L'.join('%.2f %.2f' % (x, ymax - y) for x, y in pl) + ' Z'
            f.write('<path d="%s" fill="none" stroke="%s" stroke-width="0.4"%s/>\n'
                    % (d, '#1767ed' if mark else 'black', ' stroke-dasharray="2 1.5"' if mark else ''))
        seen = set()
        for label, pl, _ in loops:
            if label not in seen:
                seen.add(label); x = min(p[0] for p in pl)
                f.write('<text x="%.1f" y="%.1f" font-size="6" font-family="sans-serif">%s</text>\n' % (x, ymax + 8, label))
        f.write('<text x="0" y="-3" font-size="5" font-family="sans-serif">Print at 100%: this line is 50 mm</text>'
                '<line x1="80" y1="-4" x2="130" y2="-4" stroke="black" stroke-width="0.6"/>\n</svg>\n')


def screw_holes():
    """Through holes for the Chicago screws, the post heads sunk into the cradle floor under the case."""
    zf = SB.z_front()
    return [cyl(H['ScrewHoleD'] / 2, x, y, -100, 50).fuse(cyl(H['ScrewHeadD'] / 2, x, y, zf - H['ScrewHeadT'], zf + 1))
            for x, y in pegs()]


def screws():
    """The Chicago screws: post head in the floor counterbore, barrel through the core and the leather,
    screw head in the foam."""
    zf = SB.z_front(); out = []
    for x, y in pegs():
        zl = rear_z(x, y) - H['LeatherT']
        out += [cyl(4.9, x, y, zf - H['ScrewHeadT'] + 0.1, zf - H['ScrewHeadT'] + 1.6),
                cyl(2.5, x, y, zl, zf - H['ScrewHeadT'] + 0.1), cyl(4.9, x, y, zl - 1.5, zl)]
    return Part.makeCompound(out)


def ring_socket():
    """Through hole for the ring and the counterbore for its flange from the rear."""
    ax, ay = axis(); zr = SB.z_rear(); c = H['SocketClear']
    return cyl(H['SocketD'] / 2 + c, ax, ay, zr - 1, 50).fuse(
        cyl(H['FlangeD'] / 2 + c, ax, ay, zr - 1, zr + H['FlangeT'] + 0.1))


def ring(idia, placed=True):
    """The printed ring about its own axis, z 0 at the plate rear: flange, tube up through the socket and
    proud of the boss, rounded inner top edge, 45 deg outer top chamfer."""
    zt = P['PlateT'] + H['RingBossT'] + H['CollarH']             # plate rear to ring top
    ro, rf, ri = H['SocketD'] / 2, H['FlangeD'] / 2, idia / 2
    s = SB.revolved([(ri, 0), (rf, 0), (rf, H['FlangeT']), (ro, H['FlangeT']), (ro, zt - 1.0), (ro - 1.0, zt),
                     (ri, zt)])
    top = [e for e in s.Edges if abs(e.BoundBox.ZMin - zt) < 1e-6 and abs(e.BoundBox.ZMax - zt) < 1e-6
           and abs(e.BoundBox.XMax - ri) < 1e-3]
    s = SB.try_fillet(s, top, (H['RingTopR'],), 'ring top')
    if not placed:
        return s
    ax, ay = axis()
    return s.translated(V(ax, ay, SB.z_rear()))


def toy_proxy():
    """Flared-base dildo through the ring: base behind the plate, shaft out of the ring."""
    ax, ay = axis(); zr = SB.z_rear(); ri = H['RingID'] / 2 - 0.5
    rb, tb = H['ToyBaseD'] / 2, H['ToyBaseT']
    body = SB.revolved([(0, -tb), (rb, -tb), (rb, -2.0), (ri + 4, 0), (ri, 0), (ri, 120), (ri - 4, 150), (0, 152)])
    return body.translated(V(ax, ay, zr))


def dd_screw():
    """The Double Double screw without the cup socket: its head is against the wearer."""
    tip = P['PlateT'] + P['DDBossT'] + P['ThreadOut']
    s = SB.dd_screw_head().fuse(SB.thread_solid(P['DDScrewHexH'] - 1.0, tip)).removeSplitter()
    return s.common(box(-50, 50, -P['ThreadFlat'], 50, -10, tip + 10)).removeSplitter()


def install():
    """Point the snap backplate builder at this design."""
    SB.cup_centres = lambda: {}
    SB.cup_positions = lambda: {}
    SB.dd_axis = axis
    SB.plan_face = core_face   # the snap builder makes the hard core only; the soft panel does the rest
    SB.keyholes = lambda: [box(-500, -499, 0, 1, 0, 1)]   # nothing to cut: a box far off the part
    if MODE == 'ring':
        P['DDBossD'], P['DDBossT'] = H['RingBossD'], H['RingBossT']
        SB.dd_pocket = ring_socket


def printed_part():
    """The hard core: the flat snap plate under the case and round the toy, filled down to the curved
    rear face (except behind the lever)."""
    zr = SB.z_rear()
    flat = SB.printed_part()
    rs = rear_surface()
    above = rs.extrude(V(0, 0, 80))
    fill = core_plan(-100, zr + 1).common(above).cut(lever_zone(-100, zr + 1)).removeSplitter()
    body = flat.common(core_plan(-100, 100)).fuse([fill] + slot_tabs()).removeSplitter()
    body = body.cut(lever_zone(-100, zr))
    cuts = screw_holes() + [SB.dd_pocket()]
    ax, ay = axis()
    if MODE == 'ring':   # the flat lobe is open to the rear up to the flange, for the toy base
        cuts.append(cyl(lobe_r() + 1, ax, ay, -100, zr).common(core_plan(-100, 100)))
        cuts.append(cyl(H['FlangeD'] / 2 + H['SocketClear'], ax, ay, -100, zr + H['FlangeT'] + 0.1))
    else:
        cuts.append(cyl(P['DDScrewSeatD'] / 2 + P['DDPocketClear'], ax, ay, -100, zr))
    return body.cut(cuts).removeSplitter()


def checks(doc, printed, toy, extra):
    ax, ay = axis(); zr = SB.z_rear()
    bb = printed.BoundBox
    print('CHECK harness core (%s) %.1f x %.1f x %.1f mm, valid %s, solids %d, %.1f cm3' % (
        MODE, bb.XLength, bb.YLength, bb.ZLength, printed.isValid(), len(printed.Solids), printed.Volume / 1000))
    outline = panel_face()
    print('CHECK panel %.1f x %.1f mm in plan, core %.1f mm inside its edge' % (
        outline.BoundBox.XLength, outline.BoundBox.YLength,
        min(v.Point.distanceToPoint(outline.Edges[0].Curve.projectPoint(v.Point)) for v in core_face().Vertexes)))
    case = [doc.getObject(n).Shape for n in SB.MODULE_PARTS]
    print('CHECK toy to the plate: overlap %.4f mm3; to the case: overlap %.4f mm3, gap %.2f mm' % (
        toy.common(printed).Volume, max(toy.common(c).Volume for c in case), min(toy.distToShape(c)[0] for c in case)))
    if MODE == 'ring':
        for d in RING_SIZES:
            r = ring(d)
            print('CHECK ring %.2f mm: valid %s, wall %.2f mm, overlap with the plate %.4f mm3, flange %.2f mm proud of the rear' % (
                d, r.isValid(), (H['SocketD'] - d) / 2, r.common(printed).Volume, zr - r.BoundBox.ZMin))
        print('CHECK ring to the toy: overlap %.4f mm3' % extra.common(toy).Volume)
    else:
        print('CHECK screw in its pocket: overlap %.4f mm3' % extra.common(printed).Volume)
    pd = pad(); pb = pd.BoundBox
    pd_ = pd.translated(V(0, 0, -0.005))   # its front lies on the plate rear; booleans on the shared sheet can fail
    print('CHECK panel valid %s, solids %d, %.1f cm3, %.1f mm thick, reaching %.1f mm behind the flat rear; overlap with the plate %.4f, with the %s %.4f, with the screws %.4f mm3' % (
        pd.isValid(), len(pd.Solids), pd.Volume / 1000, H['PadT'], zr - pb.ZMin, pd_.common(printed).Volume, 'ring' if MODE == 'ring' else 'screw', pd_.common(extra).Volume,
        pd.common(screws()).Volume))
    lever = box(P['LatchX0'], P['LatchX1'], P['LatchRootY'] + 10, SB.plate_top(), zr - 6.3, zr - 0.01)
    print('CHECK room behind the lever pressed 6.3 mm: overlap %.4f mm3 with the core, %.4f with the panel' % (
        lever.common(printed).Volume, lever.common(pd).Volume))
    print('CHECK screws in their holes: overlap %.4f mm3 with the core, %.4f with the case' % (
        screws().common(printed).Volume, max(screws().common(c).Volume for c in case)))
    print('CHECK rear sweep: hip ears %.1f mm, tip %.1f mm, top %.1f mm behind the rear on the toy axis' % (
        zr - rear_z(P['DeviceCx'] + H['WaistTabX'], H['WaistTabY']), zr - pb.ZMin - H['PadT'],
        zr - rear_z(P['DeviceCx'], SB.plate_top())))
    edge = outline.OuterWire
    for (e, d), (b, _) in zip(slot_frames(), slot_bars()):
        f, _ = slot_plan(e, d, SLOT_U[0], SLOT_U[1] + H['SlotT'] + H['SlotBarW'], H['SlotW'] / 2 + 3.25, 0, 1)
        f = f.translated(V(0, 0, SB.z_rear()))
        inside = all(outline.isInside(v.Point, 0.01, True) for v in f.Vertexes)
        print('CHECK strap slot at (%.1f, %.1f), bar %.1f mm in front of the panel: tab inside the panel %s, %.1f mm of foam past it' % (
            b.x - P['DeviceCx'], b.y, H['SlotTunnel'], inside, f.distToShape(edge)[0]))
    jx, jz = SB.ENC.P['jack_axis']
    for r in (3.0, 4.5):
        n = 0.0
        while n < 40 and Part.makeCylinder(r, n + 0.1, V(jx, 0.0, jz), V(0, -1, 0)).common(
                printed.fuse([toy, extra])).Volume < 1e-6:
            n += 0.1
        print('CHECK straight 3.5 mm plug: a %.0f mm body has %.1f mm from the jack face' % (2 * r, n))


def build(mode):
    global MODE
    MODE = mode
    SB.DD = True
    SB.P.clear(); SB.P.update(SB.BASE)
    install()
    stem = 'DTT-Harness-Mount-' + mode.capitalize()
    doc = App.openDocument(SB.MODULE)
    o = doc.getObject('ExplodedView')
    if o is not None:
        o.Visibility = False
    printed = printed_part()
    black, blue = SB.split_colours(printed)
    SB.design_checks(printed, black, blue, None)
    SB.module_checks(doc, printed)
    if mode == 'ring':
        extra, toy = ring(H['RingID']), toy_proxy()
    else:
        extra, toy = SB.dd_placed(dd_screw()), SB.double_double_proxy()
    checks(doc, printed, toy, extra)
    group = doc.addObject('App::Part', 'SnapBackplate'); group.Label = 'Harness mount'
    sheet = doc.addObject('Spreadsheet::Sheet', 'HarnessParameters'); sheet.Label = 'Harness mount parameters'
    for i, (k, (v, note)) in enumerate(PARAMS.items(), 1):
        sheet.set('A%d' % i, k); sheet.set('B%d' % i, '%g' % H[k]); sheet.set('C%d' % i, note)
    bodies = [SB.tagged(doc, 'SnapBackplatePrinted', 'Harness plate - printed, black', black, SB.PLATE_COLOUR),
              SB.tagged(doc, 'SnapBackplateTouch', 'Harness plate - printed, blue touch point', blue, SB.TOUCH_COLOUR)]
    for o in bodies:
        group.addObject(o)
    padshape = pad()
    group.addObject(SB.tagged(doc, 'HarnessPad', 'Front panel - leather over foam, sewn', padshape, PAD_COLOUR))
    group.addObject(SB.tagged(doc, 'HarnessPins', 'Chicago screws x4', screws(), SCREW_COLOUR))
    if mode == 'ring':
        group.addObject(SB.tagged(doc, 'SnapDDScrew', 'Toy ring %.2f mm - printed, black' % H['RingID'], extra, SB.PLATE_COLOUR))
        group.addObject(SB.tagged(doc, 'SnapDoubleDouble', 'Flared-base dildo (proxy)', toy, SB.CUP_COLOUR))
    else:
        group.addObject(SB.tagged(doc, 'SnapDDScrew', 'Double Double screw - printed, black', extra, SB.PLATE_COLOUR))
        group.addObject(SB.tagged(doc, 'SnapDoubleDouble', 'OSSM Double Double 24mm Threaded (proxy)', toy, SB.CUP_COLOUR))
    doc.recompute()
    if os.environ.get('HARNESS_CHECK_ONLY'):   # headless runs print the checks the GUI log drops
        return doc
    os.makedirs(SB.IMAGES, exist_ok=True); os.makedirs(SB.OUT, exist_ok=True)
    out = lambda suffix: os.path.join(SB.OUT, stem + suffix)
    if App.GuiUp:
        import ImportGui
        ImportGui.export(bodies, out('.step'))
    else:
        Part.makeCompound([black, blue]).exportStep(out('.step'))
    meshes = [(printed, ''), (black, '-Black'), (blue, '-Blue')]
    padshape.exportStep(out('-Panel.step'))   # the panel as it curves; it is sewn, not printed
    pattern(padshape, out('-Pattern'))
    if mode == 'ring':
        for d in RING_SIZES:
            r = ring(d, placed=False)
            name = '-Ring-%gin' % round(d / 25.4, 2)
            r.exportStep(out(name + '.step')); meshes.append((r, name))
    else:
        lying = dd_screw().rotated(V(0, 0, 0), V(1, 0, 0), 90).translated(V(0, 0, P['ThreadFlat']))
        lying.exportStep(out('-Screw.step')); meshes.append((lying, '-Screw'))
    import MeshPart
    for shape, suffix in meshes:
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False).write(out(suffix + '.stl'))
    if App.GuiUp:
        render(doc, stem.replace('DTT-', ''))
        render_pad(doc, stem.replace('DTT-', ''))
    doc.saveAs(os.path.join(HERE, stem + '.FCStd'))
    return doc


def render(doc, pic):
    SB.render(doc, pic)
    grey = {'SnapDDScrew': SB.BRACKET_PREVIEW_COLOUR}
    names = ['SnapBackplatePrinted', 'SnapBackplateTouch', 'SnapDDScrew', 'SnapDoubleDouble']
    rear = App.Rotation(V(0, 1, 0), -35).multiply(App.Rotation(V(1, 0, 0), -20))
    SB.preview(doc, pic + '-Exploded.png', names,
               App.Rotation(V(0, 1, 0), 50).multiply(App.Rotation(V(1, 0, 0), -15)),
               moves={'SnapDDScrew': V(0, 0, -40), 'SnapDoubleDouble': V(0, 0, -80 if MODE == 'ring' else 40)},
               colours=grey)
    SB.preview(doc, pic + '-Body-Side.png', names[:3], rear, turned=True, colours=grey)


def render_pad(doc, pic):
    """The panel from the body side, and pulled off the core with its screws."""
    names = ['SnapBackplatePrinted', 'SnapBackplateTouch', 'SnapDDScrew', 'HarnessPad']
    grey = {'SnapDDScrew': SB.BRACKET_PREVIEW_COLOUR}
    SB.preview(doc, pic + '-Pad-Rear.png', names, App.Rotation(V(0, 1, 0), -35).multiply(App.Rotation(V(1, 0, 0), -20)),
               turned=True, colours=grey)
    SB.preview(doc, pic + '-Pad-Exploded.png', names + ['HarnessPins'],
               App.Rotation(V(0, 1, 0), -60).multiply(App.Rotation(V(1, 0, 0), -15)),
               moves={'HarnessPad': V(0, 0, -30), 'HarnessPins': V(0, 0, -15)}, turned=True, colours=grey)


PAD_COLOUR = SB.TOUCH_COLOUR   # touches the wearer, so blue
SCREW_COLOUR = (0.62, 0.63, 0.66)


def main():
    return [build(m.strip()) for m in os.environ.get('HARNESS_VARIANTS', 'ring,thread').split(',')]


DOCUMENT = main()
