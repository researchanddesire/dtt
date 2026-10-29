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
Strap slots for 1 in (25 mm) webbing: two upright ones in side wings for the waist strap, and two at
the bottom for jock-style leg straps.

Device coordinates as in the snap backplate: X across, Y along the case (USB-C end at +Y), Z out of the
front face. The wearer is at -Z; the plate prints rear face down.
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
    'SlotLen': (27.0, 'design: slot length, 1.6 mm over the webbing'),
    'SlotT': (4.0, 'design: slot width, for doubled-back webbing up to 2 mm thick'),
    'SlotWeb': (5.0, 'design: plate outside each slot, which carries the strap pull'),
    'SlotEdgeR': (1.0, 'design: rounded slot edges, front and rear, so the webbing does not fray'),
    'WaistSlotDX': (32.0, 'design: waist slot centres either side of the centreline, 2.8 mm outside the sleeve wall'),
    'WaistSlotY': (84.0, 'design: waist slots beside the upper case; the wings stay plate thickness beside the walls'),
    'LegSlotR': (35.0, 'design: leg slots on a circle about the toy axis'),
    'LegSlotDeg': (38.0, 'design: leg slots this far either side of straight down, tangent to the circle'),
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
    'ToyBaseD': (70.0, 'reference proxy (estimate): flared dildo base behind the plate'),
    'ToyBaseT': (6.0, 'reference proxy (estimate)'),
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


def slots():
    """(centre x, centre y, angle of the long axis from Y in deg) for each strap slot."""
    cx = P['DeviceCx']; ax, ay = axis(); r, a = H['LegSlotR'], math.radians(H['LegSlotDeg'])
    out = [(cx - H['WaistSlotDX'], H['WaistSlotY'], 0.0), (cx + H['WaistSlotDX'], H['WaistSlotY'], 0.0)]
    for s in (-1, 1):   # tangent to the circle, so the long axis is square to the strap pull
        out.append((ax + s * r * math.sin(a), ay - r * math.cos(a), 90.0 - s * H['LegSlotDeg']))
    return out


def stadium(x, y, deg, length, width, z0, z1):
    """Round-ended slot in plan, long axis at deg from Y."""
    r = width / 2; h = length / 2 - r
    s = box(-r, r, -h, h, z0, z1).fuse([cyl(r, 0, -h, z0, z1), cyl(r, 0, h, z0, z1)]).removeSplitter()
    return s.rotated(V(0, 0, 0), V(0, 0, 1), deg).translated(V(x, y, 0))


def plan_face():
    """The snap backplate outline (case grown by the wall, out to the plate top), a body running on past
    the jack end to a round end around the toy, and a lobe around every strap slot, blended with the
    flare radius."""
    zr = SB.z_rear(); t = 1.0; top = SB.plate_top(); cx = P['DeviceCx']
    xl, xr = SB.outer_x('L'), SB.outer_x('R')
    parts = [SB.case_face(P['WallClear'] + P['RailT'], zr).extrude(V(0, 0, t)),
             box(xl, xr, P['DeviceTopY'] - 10, top, zr, zr + t)]
    ax, ay = axis()
    hw = SB.ENC.half_width(P['DeviceBottomY']) + P['WallClear'] + P['RailT']
    rb = max(hw, (H['RingBossD'] if MODE == 'ring' else P['DDBossD']) / 2 + 2.0)
    parts += [box(cx - hw, cx + hw, ay, P['DeviceBottomY'] + 10, zr, zr + t), cyl(rb, cx, ay, zr, zr + t)]
    w = H['SlotT'] + 2 * H['SlotWeb']
    for x, y, deg in slots():
        parts.append(stadium(x, y, deg, H['SlotLen'] + 2 * H['SlotWeb'], w, zr, zr + t))
    ys = H['WaistSlotY']; L = H['SlotLen'] / 2 + H['SlotWeb']    # bridge the waist lobes to the plate top
    parts.append(box(cx - H['WaistSlotDX'], cx + H['WaistSlotDX'], ys - L + w / 2, top, zr, zr + t))
    return SB.round_face(SB.flat_face(parts, zr), P['FlareR'], P['CornerR'])


ELEVATION = SB.elevation_solid


def elevation_solid():
    """The sleeve's side elevation only over the sleeve's own footprint; the strap wings stay plate
    thickness all along, beside the walls too."""
    zr, zf = SB.z_rear(), SB.z_front()
    foot = SB.case_face(P['WallClear'] + P['RailT'], zr - 2).extrude(V(0, 0, 60))
    return ELEVATION().common(foot).fuse(box(-SB.FAR / 2, SB.FAR / 2, -SB.FAR, SB.FAR, zr - 1, zf)).removeSplitter()


def slot_cuts():
    zr, zf = SB.z_rear(), SB.z_front()
    return [stadium(x, y, deg, H['SlotLen'], H['SlotT'], zr - 1, zf + 1) for x, y, deg in slots()]


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
    SB.plan_face = plan_face
    SB.elevation_solid = elevation_solid
    SB.keyholes = lambda: [box(-500, -499, 0, 1, 0, 1)]   # nothing to cut: a box far off the part
    if MODE == 'ring':
        P['DDBossD'], P['DDBossT'] = H['RingBossD'], H['RingBossT']
        SB.dd_pocket = ring_socket


def printed_part():
    body = SB.printed_part().cut(slot_cuts()).removeSplitter()
    zf, zr = SB.z_front(), SB.z_rear()
    bxs = []
    for x, y, deg in slots():
        bb = stadium(x, y, deg, H['SlotLen'] + 0.2, H['SlotT'] + 0.2, zr - 1, zf + 1).BoundBox
        bxs.append((bb.XMin, bb.XMax, bb.YMin, bb.YMax))
    for z, k, side in ((zf, 1.0, 'front'), (zr, 0.8, 'rear')):
        for i, bx in enumerate(bxs):   # one slot at a time, smaller if a round fails
            for r in (H['SlotEdgeR'] * k, H['SlotEdgeR'] * k * 0.6):
                s = SB.fillet_edges_in(body, [bx], r, z, 'strap slot %d, %s, R%.2f' % (i, side, r))
                if s is not body:
                    body = s; break
    return body


def checks(doc, printed, toy, extra):
    ax, ay = axis(); zr = SB.z_rear()
    bb = printed.BoundBox
    print('CHECK harness plate (%s) %.1f x %.1f x %.1f mm, valid %s, solids %d, %.1f cm3' % (
        MODE, bb.XLength, bb.YLength, bb.ZLength, printed.isValid(), len(printed.Solids), printed.Volume / 1000))
    outline = plan_face()
    for i, (x, y, deg) in enumerate(slots()):
        sl = stadium(x, y, deg, H['SlotLen'], H['SlotT'], zr, zr + 1)
        f = [g for g in sl.Faces if abs(g.CenterOfMass.z - zr) < 1e-6][0]
        print('CHECK strap slot %d web to the plate edge %.2f mm' % (i, min(f.distToShape(e)[0] for e in outline.Edges)))
    case = [doc.getObject(n).Shape for n in SB.MODULE_PARTS]
    for s in slot_cuts()[:2]:
        print('CHECK waist slot to the case: gap %.2f mm' % min(s.distToShape(c)[0] for c in case[:3]))
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


def main():
    return [build(m.strip()) for m in os.environ.get('HARNESS_VARIANTS', 'ring,thread').split(',')]


DOCUMENT = main()
