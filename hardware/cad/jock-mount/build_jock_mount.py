"""Build the DTT jock mount: the snap backplate's slide-in cradle, worn on a jockstrap instead of stuck
to a wall.

Run from the repository root:
    freecadcmd hardware/cad/jock-mount/build_jock_mount.py
It reuses build_snap_backplate.py (standard version: sleeve, lips, ledges, U lever and teeth) and
DTT-Enclosed.FCStd read-only, drops the suction-cup keyholes and adds strap features. JOCK_OPTIONS picks
the strap options to build (default: all); each writes STEP/STL exports to
hardware/production-exports/cad/jock-mount/ and STLs for the previews.

The case sits on the wearer's pubic mound with its jack end down, so the distance sensor at that end
looks straight out over the base of the penis, as it looks out from the wall in normal use. The USB-C
end and the lever are up, under the waistband.

Options:
    corners  one 25 mm strap slot in an ear at each corner: waistband through the top pair, leg
             straps through the bottom pair
    tunnels  two hidden 25 mm strap tunnels across the back, in a rear pad that leaves the lever room
    band     one long slot down each side for the jockstrap's own waistband, up to 50 mm wide

Device coordinates as in the snap backplate: X across, Y along (USB-C end at +Y, worn up), Z out of the
front face; the body is at -Z and the part prints rear face down.
"""
import os, sys
import FreeCAD as App
import Part

os.environ['SNAP_AS_LIBRARY'] = '1'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
CAD = os.path.join(ROOT, 'hardware', 'cad')
HERE = os.path.join(CAD, 'jock-mount')
OUT = os.path.join(ROOT, 'hardware', 'production-exports', 'cad', 'jock-mount')
sys.path.insert(0, os.path.join(CAD, 'snap-backplate'))
import build_snap_backplate as S

V, box, cyl = S.V, S.box, S.cyl

# name: (value, basis)
PARAMS = {
    'StrapW': (25.0, 'design: 1 in webbing or elastic, the common harness and jockstrap leg strap width'),
    'StrapClear': (2.0, 'design: slot length over the strap width'),
    'SlotT': (4.0, 'design: slot width across the strap, for webbing or elastic up to about 3 mm thick'),
    'SlotR': (1.0, 'design: slot end radius'),
    'EarWeb': (2.6, 'design: plate between the slot and the sleeve wall'),
    'EarRim': (3.2, 'design: outer bar the strap wraps round'),
    'EarR': (4.0, 'design: convex ear corners'),
    'EarBlendR': (5.0, 'design: concave blend from the ear into the plate'),
    'EarEdgeR': (1.0, 'design: front edges of the ears and slots'),
    'LowEarY': (18.0, 'design: lower slot centre, beside the sensor end; lower, the ear meets the jack-end corner and the plan offset fails'),
    'TopEarY': (86.0, 'design: upper slot centre, beside the USB-C end, clear of the switch cover grip'),
    'BandW': (50.0, 'design: widest jockstrap waistband that passes the band slots (2 in)'),
    'BandY': (47.0, 'design: band slot centre, mid case'),
    'PadT': (4.0, 'design: rear pad under the plate in the tunnels option, room for the lever to press'),
    'TunnelH': (2.6, 'design: strap tunnel height'),
    'TunnelFloor': (1.4, 'design: pad below each tunnel, against the body'),
    'TunnelY': ((3.0, 33.0), 'design: lower edges of the two 27 mm tunnels, either side of a 3 mm rib'),
    'LeverNotch': (1.0, 'design: pad notch clearance around the lever and its slots'),
}
J = {k: v for k, (v, _) in PARAMS.items()}
STRAP_COLOUR = (0.42, 0.43, 0.46)


def slot_len(w):
    return w + J['StrapClear']


def ear_x(y, side):
    """Sleeve outer face at y."""
    t = S.P['WallClear'] + S.P['RailT']
    return S.side_x(y, side) - t if side == 'L' else S.side_x(y, side) + t


def ear_plan(yc, w):
    """Plan boxes of the two ears and their slots centred on yc, for a strap w wide."""
    L = slot_len(w); ears, slots = [], []
    reach = J['EarWeb'] + J['SlotT'] + J['EarRim']
    for side, s in (('L', -1), ('R', 1)):
        ys = (yc - L / 2, yc, yc + L / 2)                  # the sides curve, so take the outermost point
        x_in = min(ear_x(y, side) for y in ys) if s < 0 else max(ear_x(y, side) for y in ys)
        x0 = x_in + s * J['EarWeb']; x1 = x0 + s * J['SlotT']
        xo = x_in + s * reach
        y0, y1 = yc - L / 2 - J['EarRim'], yc + L / 2 + J['EarRim']
        ears.append((min(x_in - s * 4, xo), max(x_in - s * 4, xo), y0, y1))
        slots.append((min(x0, x1), max(x0, x1), yc - L / 2, yc + L / 2))
    return ears, slots


def rounded_slot(x0, x1, y0, y1, z0, z1):
    f = Part.Face(Part.makePolygon([V(x0, y0, z0), V(x1, y0, z0), V(x1, y1, z0), V(x0, y1, z0), V(x0, y0, z0)]))
    return S.round_face(f, 0, min(J['SlotR'], (x1 - x0) / 2 - 0.01)).extrude(V(0, 0, z1 - z0))


def ears_option(printed, rows):
    """Ears off the plate sides, one strap slot in each; rows: [(slot centre y, strap width)]."""
    zr, zf = S.z_rear(), S.z_front()
    ears, slots = [], []
    for yc, w in rows:
        e, s = ear_plan(yc, w); ears += e; slots += s
    plan = [S.plan_face().extrude(V(0, 0, 1))] + [box(x0, x1, y0, y1, zr, zr + 1) for x0, x1, y0, y1 in ears]
    face = S.round_face(S.flat_face(plan, zr), J['EarBlendR'], J['EarR'])
    plate = face.extrude(V(0, 0, zf - zr))
    xl, xr = S.outer_x('L'), S.outer_x('R')
    inside = S.ENC.offset_face(S.plan_face(), -0.5).translated(V(0, 0, -1)).extrude(V(0, 0, zf - zr + 2))
    b = J['EarBlendR'] + 2.0
    near = Part.makeCompound([box(x0 - b, x1 + b, max(y0 - b, S.y_end() + 1), min(y1 + b, S.plate_top() - 1), zr - 1, zf + 1)
                             for x0, x1, y0, y1 in ears])
    plate = plate.cut(inside).common(near)                # only the ears and their blends
    plate = plate.cut([rounded_slot(x0, x1, y0, y1, zr - 1, zf + 1) for x0, x1, y0, y1 in slots]).removeSplitter()
    try:
        bed = [e for e in plate.Edges if abs(e.BoundBox.ZMax - zr) < 1e-6 and abs(e.BoundBox.ZMin - zr) < 1e-6]
        plate = plate.makeChamfer(S.P['BedChamfer'], bed)
    except Exception as ex:
        print('ears: bed chamfer failed: %s' % ex)
    part = printed.fuse(plate).removeSplitter()
    boxes = [(x0 - 0.01, x1 + 0.01, y0 - 0.01, y1 + 0.01) for x0, x1, y0, y1 in ears]
    part = S.fillet_edges_in(part, boxes, J['EarEdgeR'], zf, 'ear edges',
                             exclude=[(xl - 0.3, xr + 0.3, -S.FAR, S.FAR)])
    return part, slots


def lever_notch():
    g = S.P['LatchSlot'] + J['LeverNotch']
    return (S.P['LatchX0'] - g, S.P['LatchX1'] + g, S.P['LatchRootY'] - S.P['LatchReliefD'] / 2 - J['LeverNotch'])


def tunnels_option(printed):
    """A rear pad under the plate, notched round the lever so it can still be pressed, with two strap
    tunnels across it. Each tunnel's floor is the pad against the body; its roof is the plate."""
    zr = S.z_rear(); zp = zr - J['PadT']
    face = S.ENC.offset_face(S.plan_face(), -0.6)
    pad = face.translated(V(0, 0, zp - zr)).extrude(V(0, 0, J['PadT'] + 0.01))
    x0, x1, yn = lever_notch()
    notch = S.round_face(Part.Face(Part.makePolygon([V(x0, yn, zp - 1), V(x1, yn, zp - 1), V(x1, S.FAR, zp - 1),
                                                     V(x0, S.FAR, zp - 1), V(x0, yn, zp - 1)])), 0, 2.0)
    pad = pad.cut(notch.extrude(V(0, 0, J['PadT'] + 2)))
    tz0 = zp + J['TunnelFloor']; tz1 = tz0 + J['TunnelH']
    L = slot_len(J['StrapW']); tunnels = []
    for y0 in J['TunnelY']:
        tunnels.append(box(-S.FAR, S.FAR, y0, y0 + L, tz0, tz1))
    pad = pad.cut(tunnels).removeSplitter()
    try:
        bed = [e for e in pad.Edges if abs(e.BoundBox.ZMax - zp) < 1e-6 and abs(e.BoundBox.ZMin - zp) < 1e-6]
        pad = pad.makeChamfer(S.P['BedChamfer'], bed)
    except Exception as ex:
        print('tunnels: bed chamfer failed: %s' % ex)
    return printed.fuse(pad).removeSplitter(), [(y0, y0 + L, tz0, tz1) for y0 in J['TunnelY']]


def strap_proxies(option, slots):
    """Grey straps through the slots or tunnels, for the previews only."""
    zr, zf = S.z_rear(), S.z_front(); t = 1.2; out = 60.0; straps = []
    if option == 'tunnels':
        for y0, y1, z0, z1 in slots:
            straps.append(box(-out, 42 + out, y0 + 0.5, y1 - 0.5, z0 + 0.6, z0 + 0.6 + t))
        return straps
    cx = S.P['DeviceCx']
    for x0, x1, y0, y1 in slots:
        s = 1 if (x0 + x1) / 2 > cx else -1
        xi, xo = (x0, x1) if s > 0 else (x1, x0)          # slot inner and outer edge
        ya, yb = y0 + 0.5, y1 - 0.5
        xe = xo + s * J['EarRim']                          # ear outer edge
        pieces = [((xi + s * 0.6, xi + s * 0.6 + s * t), (zr - t, zf + t)),       # up through the slot
                  ((xi + s * 0.6, xe + s * (0.6 + t)), (zf + 0.1, zf + 0.1 + t)),  # over the outer bar
                  ((xe + s * 0.6, xe + s * (0.6 + t)), (zr - t, zf + 0.1 + t)),    # down its outer edge
                  ((xi + s * 0.6, xe + s * out), (zr - 0.1 - t, zr - 0.1))]        # away behind, to the body
        for (xa, xb), (za, zb) in pieces:
            straps.append(box(min(xa, xb), max(xa, xb), ya, yb, za, zb))
    return straps


def build_option(option):
    S.DD = False
    S.P.clear(); S.P.update(S.BASE); S.P.update({k: v for k, (v, _) in S.STANDARD.items()})
    S.cup_centres = lambda: {}                            # no suction cups: no keyholes, no cup proxies
    S.keyholes = lambda: []
    print('=== option %s' % option)
    doc = App.openDocument(S.MODULE)
    base = S.printed_part()
    if option == 'corners':
        printed, slots = ears_option(base, [(J['LowEarY'], J['StrapW']), (J['TopEarY'], J['StrapW'])])
    elif option == 'band':
        printed, slots = ears_option(base, [(J['BandY'], J['BandW'])])
    else:
        printed, slots = tunnels_option(base)
    black, blue = S.split_colours(printed)
    S.design_checks(printed, black, blue, None)
    S.module_checks(doc, printed)
    stem = 'DTT-Jock-Mount-' + option.capitalize()
    os.makedirs(OUT, exist_ok=True)
    Part.makeCompound([black, blue]).exportStep(os.path.join(OUT, stem + '.step'))
    import MeshPart
    mesh = lambda s, f: MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.2,
                                               Relative=False).write(f)
    for shape, suffix in ((printed, ''), (black, '-Black'), (blue, '-Blue')):
        mesh(shape, os.path.join(OUT, stem + suffix + '.stl'))
    prev = os.path.join(HERE, 'build', option); os.makedirs(prev, exist_ok=True)
    straps = strap_proxies(option, slots)
    if straps:
        mesh(Part.makeCompound(straps), os.path.join(prev, 'straps.stl'))
    for n in S.MODULE_PARTS:
        o = doc.getObject(n)
        MeshPart.meshFromShape(Shape=o.Shape, LinearDeflection=0.05, AngularDeflection=0.3, Relative=False).write(
            os.path.join(prev, n + '.stl'))
    App.closeDocument(doc.Name)
    return printed


def main():
    return [build_option(o.strip()) for o in os.environ.get('JOCK_OPTIONS', 'corners,tunnels,band').split(',')]


if not os.environ.get('JOCK_AS_LIBRARY'):
    main()
