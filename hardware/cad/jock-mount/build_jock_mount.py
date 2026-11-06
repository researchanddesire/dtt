"""Build the DTT jock mount: the snap backplate's slide-in cradle, worn on a jockstrap's waistband
instead of stuck to a wall.

Run from the repository root:
    freecadcmd hardware/cad/jock-mount/build_jock_mount.py
It reuses build_snap_backplate.py (standard version: sleeve, lips, ledges, U lever and teeth) and
DTT-Enclosed.FCStd read-only, drops the suction-cup keyholes and adds an ear with a long band slot on
each side. The jockstrap's waistband, up to 50 mm wide, threads through both slots behind the plate. A
3 mm adhesive-backed foam pad (or a TPU print of it) softens the back. The script saves
DTT-Jock-Mount.FCStd beside itself, the exports in hardware/production-exports/cad/jock-mount/ and
preview meshes in build/ for render_jock_mount.py.

The case sits on the wearer's pubic mound with its jack end down, so the distance sensor at that end
looks straight out over the base of the penis, as it looks out from the wall in normal use. The USB-C
end and the lever are up.

Device coordinates as in the snap backplate: X across, Y along (USB-C end at +Y, worn up), Z out of the
front face; the body is at -Z and the part prints rear face down.
"""
import math, os, sys
import FreeCAD as App
import Part

os.environ['SNAP_NO_MAIN'] = '1'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
CAD = os.path.join(ROOT, 'hardware', 'cad')
HERE = os.path.join(CAD, 'jock-mount')
BUILD = os.path.join(HERE, 'build')
OUT = os.path.join(ROOT, 'hardware', 'production-exports', 'cad', 'jock-mount')
sys.path.insert(0, os.path.join(CAD, 'snap-backplate'))
import build_snap_backplate as S

V, box = S.V, S.box

# name: (value, basis)
PARAMS = {
    'BandW': (50.0, 'design: widest waistband that passes the slots (2 in); narrower bands slide less if tight'),
    'BandClear': (2.0, 'design: slot length over the band width'),
    'BandY': (47.0, 'design: slot centre, mid case, so the plate does not tip about the band'),
    'SlotT': (4.0, 'design: slot width across the band, for elastic up to about 3 mm thick'),
    'SlotR': (1.0, 'design: slot end radius'),
    'EarWeb': (2.6, 'design: plate between the slot and the sleeve wall'),
    'EarRim': (3.2, 'design: outer bar the band wraps round'),
    'EarR': (4.0, 'design: convex ear corners'),
    'EarBlendR': (5.0, 'design: concave blend from the ear into the plate'),
    'BodyR': (120.0, 'assumed: radius of the pubic mound and lower belly across the hips; the back wraps it. Measure a few wearers'),
    'BodyRLong': (300.0, 'assumed: radius of the mound from the penis base up to the belly (sagittal); the back wraps it too'),
    'BodyApexY': (50.0, 'assumed: where the back touches the mound first, mid plate; above and below it the back curves away'),
    'PadT': (3.0, 'design: adhesive-backed EVA or neoprene foam, or a TPU 95A print of the pad'),
    'PadInset': (1.5, 'design: pad edge inside the plate edge, so the bed chamfer and the edge stay clean'),
    'PadLeverClear': (1.0, 'design: pad notch round the lever and its slots, so the tab can still be pressed'),
    'PadNotchR': (2.0, 'design: notch corners'),
    'RootEdgeR': (3.0, 'design: round along the back of the bottom edge, which sits on the base of the penis'),
    'Tilt': (15.0, 'design (Lucy): the cradle leans out at the bottom so the sensor beam points this far up, over an erect shaft'),
}
J = {k: v for k, (v, _) in PARAMS.items()}
PLATE_COLOUR, TOUCH_COLOUR = S.PLATE_COLOUR, S.TOUCH_COLOUR
PAD_COLOUR = (0.30, 0.31, 0.34)
BAND_COLOUR = (0.55, 0.56, 0.60)


def slot_len():
    return J['BandW'] + J['BandClear']


def ear_x(y, side):
    """Sleeve outer face at y."""
    t = S.P['WallClear'] + S.P['RailT']
    return S.side_x(y, side) - t if side == 'L' else S.side_x(y, side) + t


def ears_and_slots():
    """Plan boxes (x0, x1, y0, y1) of the two ears and their slots."""
    yc, L = J['BandY'], slot_len(); ears, slots = [], []
    for side, s in (('L', -1), ('R', 1)):
        ys = (yc - L / 2, yc, yc + L / 2)                  # the sides curve, so take the outermost point
        x_in = min(ear_x(y, side) for y in ys) if s < 0 else max(ear_x(y, side) for y in ys)
        x0 = x_in + s * J['EarWeb']; x1 = x0 + s * J['SlotT']
        xo = x1 + s * J['EarRim']
        ears.append((min(x_in - s * 4, xo), max(x_in - s * 4, xo), yc - L / 2 - J['EarRim'], yc + L / 2 + J['EarRim']))
        slots.append((min(x0, x1), max(x0, x1), yc - L / 2, yc + L / 2))
    return ears, slots


def rounded_rect(x0, x1, y0, y1, z, r):
    f = Part.Face(Part.makePolygon([V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)]))
    return S.round_face(f, 0, r) if r else f


def outline():
    """Rear outline of the whole part: the plate with the ears blended in."""
    zr = S.z_rear(); ears, _ = ears_and_slots()
    plan = [S.plan_face().extrude(V(0, 0, 1))] + [box(x0, x1, y0, y1, zr, zr + 1) for x0, x1, y0, y1 in ears]
    return S.round_face(S.flat_face(plan, zr), J['EarBlendR'], J['EarR'])


def pivot():
    """The cradle tilts about the top of its plate rear, which stays on the body."""
    return V(S.P['DeviceCx'], S.plate_top(), S.z_rear())


def tilt(shape, sign=1):
    """From the cradle's own frame to the worn one (sign -1 goes back)."""
    return shape.rotated(pivot(), V(1, 0, 0), -sign * J['Tilt'])


def cradle_frame():
    S.DD = False
    S.P.clear(); S.P.update(S.BASE); S.P.update({k: v for k, (v, _) in S.STANDARD.items()})
    S.cup_centres = lambda: {}                            # no suction cups: no keyholes, no cup proxies
    S.keyholes = lambda: []


def printed_part():
    """The worn part: the cradle tilted, on a body-side base that wraps the body and carries the band ears."""
    cradle_frame()
    base = tilt(S.printed_part())
    zr, zf = S.z_rear(), S.z_front()
    ears, slots = ears_and_slots()
    # Ears: a shell PlateT thick that wraps the body, so they curve back round it.
    t = zf - zr
    plate = outline().translated(V(0, 0, -20)).extrude(V(0, 0, t + 40)).common(shell(0.0, t))
    inside = S.ENC.offset_face(S.plan_face(), -0.5).translated(V(0, 0, -20)).extrude(V(0, 0, t + 40))
    b = J['EarBlendR'] + 2.0
    near = Part.makeCompound([box(x0 - b, x1 + b, max(y0 - b, S.y_end() + 1), min(y1 + b, S.plate_top() - 1),
                                  zr - 20, zf + 1) for x0, x1, y0, y1 in ears])
    plate = plate.cut(inside).common(near)               # only the ears and their blends; the lever slots stay open
    # Under the sleeve, the tilted plate rear is filled down to the body: a wedge, thick at the bottom.
    # Under the lever it is left open, so the lever still flexes and has room to be pressed.
    fill = tilt(S.plan_face().translated(V(0, 0, -60)).extrude(V(0, 0, 60.01))).cut(body())
    fill = fill.cut(tilt(lever_keepout(0.5).translated(V(0, 0, -40)).extrude(V(0, 0, 80))))
    fill = fill.common(shell(0.0, 200.0))                 # nothing inside the body or below it
    on_body = lambda e: all(body().distToShape(Part.Vertex(v.Point))[0] < 0.05 for v in e.Vertexes)
    root = [e for e in fill.Edges if e.BoundBox.YMax < J['BodyApexY'] - 30 and on_body(e)
            and abs(e.BoundBox.XMax - e.BoundBox.XMin) > 5]
    fill = S.try_fillet(fill, root, (J['RootEdgeR'], J['RootEdgeR'] / 2), 'bottom edge, body side')
    part = base.fuse([plate, fill]).removeSplitter()
    return part.cut([rounded_rect(x0, x1, y0, y1, zr - 20, J['SlotR']).extrude(V(0, 0, t + 40))
                     for x0, x1, y0, y1 in slots]).removeSplitter()


def _torus(r):
    """The wearer's mound and belly, grown outwards by r: a torus about an axis along X, so the back curves
    BodyR across the hips and BodyRLong from the penis base up, touching the plate rear at BodyApexY."""
    R, Rl = J['BodyR'], J['BodyRLong']
    c = V(S.P['DeviceCx'], J['BodyApexY'], S.z_rear() - Rl)
    return Part.makeTorus(Rl - R, R + r, c, V(1, 0, 0))


def body():
    return _torus(0.0)


def shell(z0, z1):
    """The space z0..z1 out from the body surface (measured along its normal)."""
    return _torus(z1).cut(_torus(z0))


def lever_keepout(clear):
    """Plan face round the lever and its slots, grown by clear."""
    g = S.P['LatchSlot'] + clear
    yn = S.P['LatchRootY'] - S.P['LatchReliefD'] / 2 - clear
    return rounded_rect(S.P['LatchX0'] - g, S.P['LatchX1'] + g, yn, S.FAR, S.z_rear() - 30, J['PadNotchR'])


def pad_face():
    """The foam pad in plan: the plate outline inset, without the band ears, and notched round the
    lever. It is also the cutting template; on the curve the pad is about 2 % longer across, which the
    foam takes up."""
    f = S.ENC.offset_face(S.plan_face(), -J['PadInset'])   # under the plate only, not round the band ears
    f = f.cut(lever_keepout(J['PadLeverClear']).translated(V(0, 0, 30)))
    assert len(f.Faces) == 1
    return f.Faces[0]


def pad():
    """The pad as worn, wrapped round the body under the tilted plate."""
    return tilt(pad_face().translated(V(0, 0, -60)).extrude(V(0, 0, 70))).common(shell(-J['PadT'], 0.0))


def pad_template():
    """The pad outline as it lies on the body: the plan face foreshortened by the tilt."""
    m = App.Matrix(); m.scale(1, math.cos(math.radians(J['Tilt'])), 1)
    p = pivot()
    return pad_face().translated(-p).transformGeometry(m).translated(V(p.x, p.y, 0) - V(0, 0, 0)).translated(
        V(0, 0, -S.z_rear()))


def band_proxy():
    """A waistband threaded through both slots, for the previews only: round the body, onto the front of
    each outer bar, down through the slot and across behind the plate, on the pad."""
    zr, zf = S.z_rear(), S.z_front(); t = 1.6; T = zf - zr; p = J['PadT']
    _, slots = ears_and_slots(); (_, _, y0, y1) = slots[0]
    ya, yb = y0 + 0.6, y1 - 0.6; cx = S.P['DeviceCx']
    parts = [shell(-p - t, -p).common(box(cx - 100, cx + 100, ya, yb, zr - 100, zr + 1))]
    for x0, x1, _, _ in slots:
        s = 1 if x0 > cx else -1
        xi, xo = (x0, x1) if s > 0 else (x1, x0)          # slot inner and outer edge
        xe = xo + s * J['EarRim']
        xs = sorted((xi + s * 0.6, xi + s * (0.6 + t)))
        parts.append(shell(-p - t, T + 0.2 + t).common(box(xs[0], xs[1], ya, yb, zr - 30, zf + 10)))
        xb = sorted((xi + s * 0.6, xe + s * (0.4 + t)))
        parts.append(shell(T + 0.2, T + 0.2 + t).common(box(xb[0], xb[1], ya, yb, zr - 30, zf + 10)))
        xd = sorted((xe + s * 0.4, xe + s * (0.4 + t)))
        parts.append(shell(-p - t, T + 0.2 + t).common(box(xd[0], xd[1], ya, yb, zr - 30, zf + 10)))
    return Part.makeCompound(parts)


def checks(doc, printed, black, blue, foam):
    # the snap backplate's checks run in the cradle's own frame, against the case as modelled
    S.design_checks(tilt(printed, -1), tilt(black, -1), tilt(blue, -1), None)
    S.module_checks(doc, tilt(printed, -1))
    zr = S.z_rear(); _, slots = ears_and_slots()
    pf = pad_face()
    print('CHECK pad: valid %s, %.0f cm2, overlap with the part %.4f mm3' % (
        foam.isValid(), pf.Area / 100, foam.common(printed).Volume))
    for x0, x1, y0, y1 in slots:
        hole = rounded_rect(x0, x1, y0, y1, zr - 20, J['SlotR']).extrude(V(0, 0, 20.1))
        print('CHECK band slot %.1f x %.1f: pad overlap %.4f mm3, plate overlap %.4f mm3' % (
            x1 - x0, y1 - y0, hole.common(foam).Volume, hole.common(printed).Volume))
    lever = tilt(box(S.P['LatchX0'], S.P['LatchX1'], S.P['LatchRootY'], S.FAR, zr - 30, zr))
    print('CHECK pad clear of the lever: overlap %.4f mm3' % lever.common(foam).Volume)
    for y0, what in ((S.y_end() + 3, 'bottom edge, on the penis base'), (J['BodyApexY'], 'apex'),
                     (S.plate_top() - 1, 'lever tab, room to press')):
        y = tilt(Part.Vertex(V(S.P['DeviceCx'], y0, zr))).Point.y
        seg = Part.LineSegment(V(S.P['DeviceCx'], y, zr - 30), V(S.P['DeviceCx'], y, zr + 1)).toShape()
        low = min(v.Point.z for v in seg.common(printed).Vertexes)
        gap = body().distToShape(Part.Vertex(V(S.P['DeviceCx'], y, low)))[0]
        print('CHECK centreline at Y %.0f (%s): back %.2f mm off the body' % (y, what, gap))
    case = tilt(Part.makeCompound([doc.getObject(n).Shape for n in S.MODULE_PARTS]))
    bb = printed.optimalBoundingBox()   # tori give loose plain bounding boxes
    eb = case.optimalBoundingBox()
    print('CHECK worn: part %.1f x %.1f x %.1f mm; case front %.1f to %.1f mm off the body at the plate apex '
          '(pad included), beam %.0f deg up' % (bb.XLength, bb.YLength, bb.ZLength, eb.ZMin - (zr - J['PadT']),
                                               eb.ZMax - (zr - J['PadT']), J['Tilt']))


def tagged(doc, name, label, shape, colour):
    o = doc.addObject('Part::Feature', name); o.Label = label; o.Shape = shape
    if App.GuiUp:
        o.ViewObject.ShapeColor = colour
    return o


def mesh(shape, path, fine=True):
    import MeshPart
    MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02 if fine else 0.05, AngularDeflection=0.2 if fine else 0.3,
                           Relative=False).write(path)


def main():
    doc = App.openDocument(S.MODULE)
    o = doc.getObject('ExplodedView')
    if o is not None:
        o.Visibility = False
    printed = printed_part()
    black, blue = (tilt(c) for c in S.split_colours(tilt(printed, -1)))   # the touch region is in the cradle frame
    foam = pad(); band = band_proxy()
    checks(doc, printed, black, blue, foam)
    worn = App.Placement(V(0, 0, 0), App.Rotation(V(1, 0, 0), -J['Tilt']), pivot())
    for o in doc.RootObjects:                             # the case as worn, tilted with the cradle
        if hasattr(o, 'Placement') and o.Name != 'ExplodedView':
            o.Placement = worn.multiply(o.Placement)
    group = doc.addObject('App::Part', 'JockMount'); group.Label = 'Jock mount'
    for name, label, shape, colour in (
            ('JockMountPrinted', 'Jock mount - printed, black', black, PLATE_COLOUR),
            ('JockMountTouch', 'Jock mount - printed, blue touch point', blue, TOUCH_COLOUR),
            ('JockMountPad', 'Back pad - 3 mm adhesive foam or TPU', foam, PAD_COLOUR),
            ('JockMountBand', 'Waistband (proxy)', band, BAND_COLOUR)):
        group.addObject(tagged(doc, name, label, shape, colour))
    doc.recompute()
    os.makedirs(OUT, exist_ok=True); os.makedirs(BUILD, exist_ok=True)
    stem = os.path.join(OUT, 'DTT-Jock-Mount')
    Part.makeCompound([black, blue]).exportStep(stem + '.step')
    for shape, suffix in ((printed, ''), (black, '-Black'), (blue, '-Blue')):
        mesh(shape, stem + suffix + '.stl')
    # the pad lies on its back for printing in TPU, and its outline is the cutting template for foam
    flat = foam.translated(V(0, 0, -foam.BoundBox.ZMin))
    flat.exportStep(stem + '-Pad.step'); mesh(flat, stem + '-Pad.stl')
    import importDXF
    pd = App.newDocument('JockPad'); pf = pd.addObject('Part::Feature', 'Pad')
    pf.Shape = Part.Compound(pad_template().Wires)
    pd.recompute(); importDXF.export([pf], stem + '-Pad.dxf'); App.closeDocument(pd.Name)
    cx = S.P['DeviceCx']                                  # a patch of the wearer, for the side preview
    skin = shell(-J['PadT'] - 12, -J['PadT']).common(box(cx - 95, cx + 95, -45, 150, S.z_rear() - 45, S.z_rear()))
    for shape, name in ((black, 'mount-black'), (blue, 'mount-blue'), (foam, 'pad'), (band, 'band'), (skin, 'body')):
        mesh(shape, os.path.join(BUILD, name + '.stl'))
    for n in S.MODULE_PARTS:
        mesh(tilt(doc.getObject(n).Shape), os.path.join(BUILD, n + '.stl'), fine=False)
    doc.saveAs(os.path.join(HERE, 'DTT-Jock-Mount.FCStd'))
    return doc


if not os.environ.get('JOCK_NO_MAIN'):
    DOCUMENT = main()
