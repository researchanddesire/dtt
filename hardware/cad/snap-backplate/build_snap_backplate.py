"""Build the click-in backplate concept around the unmodified DTT module.

Run from the repository root under the FreeCAD GUI (needed for colours and previews):
    freecad hardware/cad/snap-backplate/build_snap_backplate.py
or headless with xvfb-run. It opens hardware/cad/DTT.FCStd, adds the backplate and
saves the result as hardware/cad/snap-backplate/DTT-Snap-Backplate-Concept.FCStd.
DTT.FCStd itself is not modified. Edit PARAMS below and re-run to change the concept.

Device coordinates: X across the module, Y along it (USB-C end at +Y), Z out of the
front face. The PCB rear face is Z -5.1. Plate positions are given from the device
centreline and from the device ends.
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
    'DeviceBottomY': (1.0, 'verified: housing jack end'),
    'DeviceTopY': (93.0, 'verified: housing USB-C end'),
    'HousingTopZ': (14.17, 'verified: front face'),
    # plate outline: the reference proxy's upper section, then a narrow body around the module
    'PlateT': (4.0, 'reference proxy (estimate)'),
    'PlateW': (75.0, 'reference proxy: upper width'),
    'PlateTopR': (5.0, 'reference proxy'),
    'DeviceTopInset': (17.0, 'reference proxy: plate top to housing top end'),
    'UpperH': (36.0, 'design: height of the wide upper section, encloses the upper keyholes'),
    'BodyW': (54.0, 'design: housing width plus 5 mm each side'),
    'BottomMargin': (5.0, 'design: plate bottom below the housing jack end, under the end stops'),
    'BottomR': (12.0, 'design'),
    'ShoulderR': (6.0, 'design: fillet where the upper section meets the body'),
    # track: the module slides in from the USB-C end and rests on the bottom end stops
    'RestGap': (2.6, 'design: plate front to PCB rear; PCB screw heads and the lower cup head pass under the PCB'),
    'WallClear': (0.2, 'design: clearance to the housing sides'),
    'RailT': (2.0, 'design: rail wall thickness'),
    'HookEngage': (0.6, 'design: rail lip overlap onto the top chamfer'),
    'SkidW': (2.0, 'design: skids under the PCB, between the screw-head and connector tracks'),
    'StopT': (2.0, 'design: end stop thickness'),
    'StopTopZ': (-1.0, 'design: end stops reach 2.5 mm up the housing'),
    # flexure latch: a tongue cut into the plate, teeth snap behind the PCB at the USB-C end
    'LatchX0': (9.0, 'design: tongue left edge'),
    'LatchX1': (33.0, 'design: tongue right edge'),
    'LatchRootY': (66.0, 'design: tongue root, under the module'),
    'LatchEndY': (104.0, 'design: tongue free end, the press tab'),
    'LatchSlot': (1.5, 'design: cut around the tongue'),
    'LatchT': (2.0, 'design: tongue thickness, thinned from the rear'),
    'ToothW': (5.0, 'design: each tooth; both sit outside the USB-C plug overmold'),
    'ToothRise': (1.2, 'design: tooth top above the PCB rear, catches the board edge'),
    'ToothClear': (0.2, 'design: tooth stop face to the module end'),
    'ToothFlat': (1.0, 'design'),
    'RampAngle': (30.0, 'design: lead-in ramp, degrees from the plate'),
    # cups, keyhole travel and head size from the reference proxy
    'TopCupX': (28.5, 'reference proxy: from the centreline'),
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
}
P = {k: v for k, (v, _) in PARAMS.items()}

# Housing side profile: (y0, y1, outer x left, outer x right, chamfer start z, chamfer inset)
SECTIONS = {'bottom': (4.0, 24.0, 2.0, 40.0, 13.18, 0.99),
            'mid': (26.4, 56.6, 0.0, 42.0, 13.18, 0.99),
            'wide': (58.4, 88.0, -1.0, 43.0, 12.18, 1.41)}
# Rails (section, y0, y1), both sides. The module slides toward -Y, so a rail is only ever
# passed by its own section or narrower ones. The wide rails stop short of the S1 switch,
# which protrudes from the right side at Y 79.4 and above.
RAILS = [('bottom', 6.0, 22.0), ('mid', 28.0, 55.0), ('wide', 60.0, 77.0)]
# Skids under the PCB (X ranges), run Y 4 to the tongue root. They sit between the tracks swept by
# the PCB screw heads (X 0.6-5.7, 36.3-41.4) and clear of the J5 and J2/J6 through-hole parts.
SKIDS = [(11.0, 13.0), (29.0, 31.0)]
# End stops (device X ranges) at the jack end, either side of the 3.5 mm jack.
BOTTOM_STOPS = [(7.0, 14.0), (28.0, 35.0)]


def plate_top():
    return P['DeviceTopY'] + P['DeviceTopInset']


def z_front():
    return P['PCBRearZ'] - P['RestGap']


def prism(points_xy, z0, z1):
    pts = [App.Vector(x, y, z0) for x, y in points_xy]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(App.Vector(0, 0, z1 - z0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def cyl(r, x, y, z0, z1):
    return Part.makeCylinder(r, z1 - z0, App.Vector(x, y, z0))


def plate_shape():
    zf = z_front(); zr = zf - P['PlateT']
    cx, top = P['DeviceCx'], plate_top()
    bot = P['DeviceBottomY'] - P['BottomMargin']
    w, tr = P['PlateW'] / 2, P['PlateTopR']
    bw, br = P['BodyW'] / 2, P['BottomR']
    ys = top - P['UpperH']
    parts = [box(cx - w, cx + w, ys, top - tr, zr, zf), box(cx - w + tr, cx + w - tr, top - tr, top, zr, zf),
             box(cx - bw, cx + bw, bot + br, ys + 1, zr, zf), box(cx - bw + br, cx + bw - br, bot, bot + br, zr, zf)]
    for s in (-1, 1):
        parts += [cyl(tr, cx + s * (w - tr), top - tr, zr, zf), cyl(br, cx + s * (bw - br), bot + br, zr, zf)]
    outline = parts[0].fuse(parts[1:]).removeSplitter()
    face = [f for f in outline.Faces if abs(f.CenterOfMass.z - zr) < 1e-6][0]
    r = P['ShoulderR']
    face = face.makeOffset2D(r, join=0).makeOffset2D(-r, join=0)   # fillet the shoulders
    face = face.makeOffset2D(-3.0, join=0).makeOffset2D(3.0, join=0)   # round the shoulder corners
    return face.extrude(App.Vector(0, 0, P['PlateT']))


def cup_centres():
    cx, yt = P['DeviceCx'], plate_top() - P['TopCupDrop']
    return {'UL': (cx - P['TopCupX'], yt), 'UR': (cx + P['TopCupX'], yt),
            'L': (cx, P['LowCupY'])}


def keyholes():
    zf = z_front(); zr = zf - P['PlateT']
    cut = []
    w = P['KeySlotW'] / 2
    for key, (sx, sy) in cup_centres().items():
        ey = sy - (P['LowSlot'] if key == 'L' else P['TopSlot'])
        cut += [cyl(P['KeyEntryD'] / 2, sx, ey, zr - 1, zf + 1), cyl(w, sx, sy, zr - 1, zf + 1),
                box(sx - w, sx + w, ey, sy, zr - 1, zf + 1)]
    return cut


def latch_cut():
    """U-shaped cut that frees the tongue, plus the rear thinning that makes it flex."""
    zf = z_front(); zr = zf - P['PlateT']; g = P['LatchSlot']
    x0, x1, y0, y1 = P['LatchX0'], P['LatchX1'], P['LatchRootY'], P['LatchEndY']
    u = box(x0 - g, x1 + g, y0, y1 + g, zr - 1, zf + 1).cut(box(x0, x1, y0 - 1, y1, zr - 2, zf + 2))
    return [u, box(x0, x1, y0, y1, zr - 1, zf - P['LatchT'])]


def latch_teeth():
    zf = z_front()
    zt = P['PCBRearZ'] + P['ToothRise']
    ys = P['DeviceTopY'] + P['ToothClear']
    yf = ys + P['ToothFlat']
    yr = yf + (zt - zf) / math.tan(math.radians(P['RampAngle']))
    prof = [(ys, zf - 0.01), (ys, zt), (yf, zt), (yr, zf - 0.01)]
    teeth = []
    for xa in (P['LatchX0'], P['LatchX1'] - P['ToothW']):
        pts = [App.Vector(xa, y, z) for y, z in prof]
        teeth.append(Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(App.Vector(P['ToothW'], 0, 0)))
    return teeth


def cup_shape(x, y):
    zf = z_front(); zr = zf - P['PlateT']
    rim = zr - P['CupDepth']
    hgt = P['CupDepth'] - P['CupRearGap']
    outside = Part.makeCone(P['CupD'] / 2, P['CupShoulderR'], hgt, App.Vector(x, y, rim))
    inside = Part.makeCone(P['CupD'] / 2 - P['CupWall'], P['CupShoulderR'] - P['CupWall'], hgt - 1.5,
                           App.Vector(x, y, rim - 0.1))
    stem = cyl(P['StemD'] / 2, x, y, zr - P['CupRearGap'] - 0.5, zf + P['HeadGap'])
    head = cyl(P['HeadD'] / 2, x, y, zf + P['HeadGap'], zf + P['HeadGap'] + P['HeadT'])
    return outside.cut(inside).fuse([stem, head]).removeSplitter()


def rail(side, sec, ya, yb):
    """Rail wall rising from the plate with a lip over the housing's top chamfer."""
    _, _, xl, xr, zc, inset = SECTIONS[sec]
    zf = z_front(); c, t = P['WallClear'], P['RailT']
    s = -1 if side == 'L' else 1
    wall = xl if side == 'L' else xr
    inner = wall + s * c
    outer = inner + s * t
    slope = (P['HousingTopZ'] - zc) / inset
    tip = wall - s * (P['HookEngage'] - c)       # lip tip X, over the chamfer
    z_tip = zc + P['HookEngage'] * slope + c
    prof = [(outer, zf), (inner, zf), (inner, zc + c), (tip, z_tip), (tip, P['HousingTopZ'] + 1.2),
            (outer, P['HousingTopZ'] + 1.2)]
    pts = [App.Vector(x, ya, z) for x, z in prof]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(App.Vector(0, yb - ya, 0))


def cradle():
    zf = z_front(); parts = []
    for sec, ya, yb in RAILS:
        for side in 'LR':
            parts.append(rail(side, sec, ya, yb))
    for xa, xb in SKIDS:
        parts.append(box(xa, xb, P['DeviceBottomY'] + 3, P['LatchRootY'] - 2, zf - 0.01, P['PCBRearZ']))
    c, t = P['WallClear'], P['StopT']
    for xa, xb in BOTTOM_STOPS:
        parts.append(box(xa, xb, P['DeviceBottomY'] - c - t, P['DeviceBottomY'] - c, zf - 0.01, P['StopTopZ']))
    return parts + latch_teeth()


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


def main():
    doc = App.openDocument(os.path.join(CAD, 'DTT.FCStd'))
    # The concept replaces the hook-and-loop backing; hide it and the exploded copies.
    for n in ('LoopBacking', 'ExplodedView'):
        o = doc.getObject(n)
        if o is not None:
            o.Visibility = False
    zf = z_front()
    plate = plate_shape().cut(keyholes() + latch_cut())
    printed = plate.fuse(cradle()).removeSplitter()
    group = doc.addObject('App::Part', 'SnapBackplate'); group.Label = 'Snap backplate concept'
    parameter_sheet(doc)
    group.addObject(tagged(doc, 'SnapBackplatePrinted', 'Snap backplate - printed', printed, (0.30, 0.30, 0.33)))
    for key, (x, y) in cup_centres().items():
        group.addObject(tagged(doc, 'SnapCup' + key, 'Suction cup %s (proxy)' % key, cup_shape(x, y), (0.75, 0.80, 0.85), 35))
    doc.recompute()
    os.makedirs(HERE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    printed.exportStep(os.path.join(OUT, 'DTT-Snap-Backplate.step'))
    import MeshPart
    MeshPart.meshFromShape(Shape=printed, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False).write(
        os.path.join(OUT, 'DTT-Snap-Backplate.stl'))
    if App.GuiUp:
        render(doc)
    doc.saveAs(os.path.join(HERE, 'DTT-Snap-Backplate-Concept.FCStd'))
    return doc


def render(doc):
    import FreeCADGui as Gui
    App.ParamGet('User parameter:BaseApp/Preferences/View').SetBool('ShowNaviCube', False)
    App.ParamGet('User parameter:BaseApp/Preferences/View').SetBool('ShowAxisCross', False)
    view = Gui.getDocument(doc.Name).ActiveView
    # show the housing see-through so the arms can be seen gripping it
    doc.getObject('Cover___V3_v5').Visibility = True
    doc.getObject('Part__Feature001').ViewObject.Transparency = 55
    tops = [o for o in doc.RootObjects if o.TypeId == 'App::Part']
    saved = {o.Name: o.Visibility for o in tops}
    view.viewIsometric(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Assembled.png'), 1400, 1400, 'White')
    for o in tops:
        o.Visibility = o.Name == 'SnapBackplate'
    housing = doc.getObject('Cover___V3_v5'); housing.Visibility = False
    view.viewIsometric(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Front.png'), 1400, 1400, 'White')
    view.setCameraOrientation(App.Rotation(App.Vector(0, 1, 0), 180)); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Rear.png'), 1400, 1400, 'White')
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    housing.Visibility = True
    view.viewRight(); view.fitAll()
    view.saveImage(os.path.join(HERE, 'Snap-Backplate-Side.png'), 1400, 1400, 'White')


if __name__ == '__main__' or True:
    DOCUMENT = main()
