"""Build the DTT screw-mount geometry inside DTT.FCStd.

Run from the repository root under the FreeCAD GUI (needed to keep colours):
    freecad hardware/cad/screw-mount/build_screw_mount.py
or headless with xvfb-run. Edit dimensions in the `MountParameters` spreadsheet;
the housing bosses, inserts, standoffs and plate follow it through expressions.
Re-run this script to refresh exploded copies, exports and previews.
"""
import math, os, sys
import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) if '__file__' in globals() else os.getcwd()
CAD = os.path.join(ROOT, 'hardware', 'cad')
DOC = os.path.join(CAD, 'DTT.FCStd')
TAG = 'ScrewMount'

# alias, value, unit, note  ('verified' rows come from the KiCad source or measured parts)
PARAMS = [
    ('Source', None, None, 'Hole centres from the rev4 KiCad source via PCBTransform'),
    ('HoleTLx', 2.416667, 'mm', 'verified: @HOLE0 x 130.000'),
    ('HoleTRx', 39.583333, 'mm', 'verified: @HOLE1 x 167.166667'),
    ('HoleTy', 76.0, 'mm', 'verified: @HOLE0/@HOLE1 y 75.9861'),
    ('HoleBLx', 3.3, 'mm', 'verified: @HOLE3 x 130.883333'),
    ('HoleBRx', 38.7, 'mm', 'verified: @HOLE2 x 166.283333'),
    ('HoleBy', 27.5, 'mm', 'verified: @HOLE2/@HOLE3 y 124.4861'),
    ('PCBTopZ', -3.5, 'mm', 'verified: assembly datum'),
    ('PCBThickness', 1.6, 'mm', 'verified: fabrication stack-up'),
    ('BossFaceZ', -3.63, 'mm', 'verified: housing rim bearing plane (CAD PCB overlaps it 0.13 mm as a fit item)'),
    ('PCBHoleD', 2.9, 'mm', 'design: M2.5 medium clearance'),
    ('Housing', None, None, 'Printed boss for an M2.5 heat-set insert'),
    ('BossR', 3.1, 'mm', 'design'),
    ('BossContactR', 2.5, 'mm', 'design: matches PCB F.Cu keepout r2.75'),
    ('BossChamferH', 0.6, 'mm', 'design'),
    ('BossTopZ', 6.0, 'mm', 'design'),
    ('InsertHoleD', 3.2, 'mm', 'supplier: M2.5 x 4 heat-set insert hole'),
    ('InsertHoleDepth', 5.0, 'mm', 'design: insert length + 1.0 mm thread run-out'),
    ('InsertOD', 3.6, 'mm', 'supplier: knurl diameter'),
    ('InsertL', 4.0, 'mm', 'supplier'),
    ('InsertRecess', 0.2, 'mm', 'design: set below boss face'),
    ('Standoff', None, None, 'M2.5 male-female brass hex standoff'),
    ('StandoffAF', 5.0, 'mm', 'supplier'),
    ('StandoffL', 6.0, 'mm', 'design: PCB back to plate front'),
    ('StandoffMaleL', 6.0, 'mm', 'supplier'),
    ('StandoffFemaleDepth', 5.0, 'mm', 'supplier: minimum full-thread depth (check)'),
    ('Plate', None, None, 'Backplate and suction-cup proxy'),
    ('PlateT', 4.0, 'mm', 'assumed: measure the existing plate'),
    ('PlateW', 90.0, 'mm', 'assumed: photo-based proxy'),
    ('PlateH', 120.0, 'mm', 'assumed: photo-based proxy'),
    ('PlateCornerR', 8.0, 'mm', 'assumed'),
    ('PlateCx', 21.0, 'mm', 'design: plate centred on the device'),
    ('PlateCy', 47.0, 'mm', 'design: plate centred on the device'),
    ('PlateHoleD', 2.9, 'mm', 'design: M2.5 clearance'),
    ('CsinkD', 5.0, 'mm', 'design: 90 deg countersink for ISO 10642 M2.5'),
    ('PlateScrewL', 8.0, 'mm', 'design: PlateT + 4 mm thread engagement'),
    ('CupUpperDx', 24.0, 'mm', 'assumed: upper cups either side of centre'),
    ('CupUpperDy', 40.0, 'mm', 'assumed: above plate centre'),
    ('CupLowerDy', -40.0, 'mm', 'assumed: below plate centre'),
    ('CupD', 40.0, 'mm', 'assumed: suction cup diameter'),
    ('CupH', 8.0, 'mm', 'assumed: cup height from plate rear to wall, seated'),
    ('StudNeckD', 5.0, 'mm', 'assumed: cup stud neck'),
    ('StudNeckL', 3.0, 'mm', 'assumed: neck length, plate rear to head'),
    ('StudHeadD', 9.0, 'mm', 'assumed: cup stud head'),
    ('StudHeadT', 2.5, 'mm', 'assumed'),
    ('KeyholeD', 10.0, 'mm', 'design: StudHeadD + 1.0'),
    ('KeySlotW', 5.4, 'mm', 'design: StudNeckD + 0.4'),
    ('KeySlotL', 8.0, 'mm', 'design: entry centre to locked centre, upward'),
]


def spreadsheet(doc):
    sheet = doc.getObject('MountParameters')
    if sheet is None:
        sheet = doc.addObject('Spreadsheet::Sheet', 'MountParameters')
        sheet.Label = 'Screw mount parameters'
        sheet.set('A1', 'Parameter'); sheet.set('B1', 'Value'); sheet.set('C1', 'Unit'); sheet.set('D1', 'Basis')
    present = {sheet.getAlias('B%d' % r) for r in range(2, 200) if sheet.getAlias('B%d' % r)}
    row = 2
    while sheet.getContents('A%d' % row):
        row += 1
    for alias, value, unit, note in PARAMS:
        if alias in present or value is None and any(sheet.getContents('A%d' % r) == alias for r in range(2, row)):
            continue
        sheet.set('A%d' % row, alias)
        if value is not None:
            sheet.set('B%d' % row, '=%g %s' % (value, unit) if unit else str(value))
            sheet.setAlias('B%d' % row, alias)
            sheet.set('C%d' % row, unit)
        sheet.set('D%d' % row, note)
        row += 1
    doc.recompute()
    return sheet


def tagged(obj):
    if 'MountRole' not in obj.PropertiesList:
        obj.addProperty('App::PropertyString', 'MountRole', TAG, 'Created by build_screw_mount.py')
        obj.setEditorMode('MountRole', 1)
    obj.MountRole = TAG
    return obj


def remove_tagged(doc):
    names = [o.Name for o in doc.Objects if getattr(o, 'MountRole', '') == TAG]
    for name in names:
        if doc.getObject(name) is not None:
            doc.removeObject(name)


def prim(doc, kind, name, label, exprs):
    obj = tagged(doc.addObject(kind, name)); obj.Label = label
    for prop, expr in exprs.items():
        obj.setExpression(prop, expr)
    return obj


HOLES = [('TL', 'HoleTLx', 'HoleTy'), ('TR', 'HoleTRx', 'HoleTy'), ('BL', 'HoleBLx', 'HoleBy'), ('BR', 'HoleBRx', 'HoleBy')]


def build_housing(doc):
    base = doc.getObject('Part__Feature001')
    base.Label = 'Outer Body base solid'
    old = {'TL': (3.0, 76.0), 'TR': (39.0, 76.0), 'BL': (3.3, 27.5), 'BR': (38.7, 27.5)}   # 0408LTFB pilot holes
    adds = []
    for key, xs, ys in HOLES:
        boss = prim(doc, 'Part::Cylinder', 'Boss' + key, 'Insert boss ' + key, {
            'Radius': 'MountParameters.BossR',
            'Height': 'MountParameters.BossTopZ - MountParameters.BossFaceZ - MountParameters.BossChamferH',
            'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys,
            'Placement.Base.z': 'MountParameters.BossFaceZ + MountParameters.BossChamferH'})
        foot = prim(doc, 'Part::Cone', 'BossFoot' + key, 'Insert boss foot ' + key, {
            'Radius1': 'MountParameters.BossContactR', 'Radius2': 'MountParameters.BossR',
            'Height': 'MountParameters.BossChamferH',
            'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys,
            'Placement.Base.z': 'MountParameters.BossFaceZ'})
        adds += [boss, foot]
        if key in old:
            fill = tagged(doc.addObject('Part::Cylinder', 'PilotFill' + key)); fill.Label = 'Retired pilot fill ' + key
            fill.Radius = 1.95; fill.Height = 15.0
            fill.Placement.Base = App.Vector(old[key][0], old[key][1], -3.33)
            adds.append(fill)
    fuse = tagged(doc.addObject('Part::MultiFuse', 'HousingBossFuse')); fuse.Label = 'Outer Body with insert bosses'
    fuse.Shapes = [base] + adds; fuse.Refine = True
    holes = []
    for key, xs, ys in HOLES:
        h = prim(doc, 'Part::Cylinder', 'InsertHole' + key, 'Insert hole ' + key, {
            'Radius': 'MountParameters.InsertHoleD / 2', 'Height': 'MountParameters.InsertHoleDepth + 0.01 mm',
            'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys,
            'Placement.Base.z': 'MountParameters.BossFaceZ - 0.01 mm'})
        holes.append(h)
    hole_fuse = tagged(doc.addObject('Part::MultiFuse', 'InsertHoles')); hole_fuse.Label = 'Insert holes'
    hole_fuse.Shapes = holes
    body = tagged(doc.addObject('Part::Cut', 'OuterBody')); body.Label = 'Outer Body'
    body.Base = fuse; body.Tool = hole_fuse; body.Refine = True
    doc.getObject('FusedPrintBody').Base = body
    for o in adds + holes + [fuse, hole_fuse]:
        o.Visibility = False
    base.Visibility = False
    return body


def build_hardware(doc):
    group = doc.getObject('Fasteners')
    for name in ('PCBMountScrew1', 'PCBMountScrew2', 'PCBMountScrew3', 'PCBMountScrew4'):
        if doc.getObject(name):
            doc.removeObject(name)
    group.Label = 'Fasteners'
    made = []
    for i, (key, xs, ys) in enumerate(HOLES, 1):
        at = {'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys}
        outer = prim(doc, 'Part::Cylinder', 'InsertBody' + key, 'Insert body ' + key, dict(at, **{
            'Radius': 'MountParameters.InsertOD / 2', 'Height': 'MountParameters.InsertL',
            'Placement.Base.z': 'MountParameters.BossFaceZ + MountParameters.InsertRecess'}))
        bore = prim(doc, 'Part::Cylinder', 'InsertBore' + key, 'Insert bore ' + key, dict(at, **{
            'Radius': '1.25 mm', 'Height': 'MountParameters.InsertL + 0.02 mm',
            'Placement.Base.z': 'MountParameters.BossFaceZ + MountParameters.InsertRecess - 0.01 mm'}))
        insert = tagged(doc.addObject('Part::Cut', 'HeatSetInsert%d' % i))
        insert.Label = 'Heat-set insert %d - M2.5 x 4' % i; insert.Base = outer; insert.Tool = bore
        hexa = prim(doc, 'Part::Prism', 'StandoffHex' + key, 'Standoff hex ' + key, dict(at, **{
            'Circumradius': 'MountParameters.StandoffAF / sqrt(3)', 'Height': 'MountParameters.StandoffL',
            'Placement.Base.z': 'MountParameters.PCBTopZ - MountParameters.PCBThickness - MountParameters.StandoffL'}))
        hexa.Polygon = 6
        male = prim(doc, 'Part::Cylinder', 'StandoffStud' + key, 'Standoff stud ' + key, dict(at, **{
            'Radius': '1.25 mm', 'Height': 'MountParameters.StandoffMaleL',
            'Placement.Base.z': 'MountParameters.PCBTopZ - MountParameters.PCBThickness'}))
        socket = prim(doc, 'Part::Cylinder', 'StandoffSocket' + key, 'Standoff socket ' + key, dict(at, **{
            'Radius': '1.0 mm', 'Height': 'MountParameters.StandoffFemaleDepth',
            'Placement.Base.z': 'MountParameters.PCBTopZ - MountParameters.PCBThickness - MountParameters.StandoffL - 0.01 mm'}))
        body = tagged(doc.addObject('Part::Fuse', 'StandoffBody' + key)); body.Label = 'Standoff body ' + key
        body.Base = hexa; body.Tool = male
        standoff = tagged(doc.addObject('Part::Cut', 'Standoff%d' % i))
        standoff.Label = 'Standoff %d - M2.5 M-F hex' % i; standoff.Base = body; standoff.Tool = socket
        for o in (outer, bore, hexa, male, socket, body):
            o.Visibility = False
        made += [insert, standoff]
    for o in made:
        group.addObject(o)
    backing = doc.getObject('LoopBacking')
    if backing:
        for o in list(backing.Group):
            doc.removeObject(o.Name)
        doc.removeObject(backing.Name)
    return made


CUPS = [('UL', '-MountParameters.CupUpperDx', 'MountParameters.CupUpperDy'),
        ('UR', 'MountParameters.CupUpperDx', 'MountParameters.CupUpperDy'),
        ('LO', '0 mm', 'MountParameters.CupLowerDy')]
PLATE_FRONT = 'MountParameters.PCBTopZ - MountParameters.PCBThickness - MountParameters.StandoffL'


def build_plate(doc):
    group = doc.getObject('Backplate') or doc.addObject('App::Part', 'Backplate')
    group.Label = 'Backplate'
    tagged(group)
    blank = prim(doc, 'Part::Box', 'PlateBlank', 'Plate blank', {
        'Length': 'MountParameters.PlateW', 'Width': 'MountParameters.PlateH', 'Height': 'MountParameters.PlateT',
        'Placement.Base.x': 'MountParameters.PlateCx - MountParameters.PlateW / 2',
        'Placement.Base.y': 'MountParameters.PlateCy - MountParameters.PlateH / 2',
        'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT'})
    corners = []
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        # corner trim: a box minus a cylinder at each corner
        cb = prim(doc, 'Part::Box', 'PlateCornerBox%d' % i, 'Plate corner box %d' % i, {
            'Length': 'MountParameters.PlateCornerR + 0.01 mm', 'Width': 'MountParameters.PlateCornerR + 0.01 mm',
            'Height': 'MountParameters.PlateT + 0.02 mm',
            'Placement.Base.x': 'MountParameters.PlateCx %s MountParameters.PlateW / 2 %s' % ('-' if sx < 0 else '+', '- 0.01 mm' if sx < 0 else '- MountParameters.PlateCornerR'),
            'Placement.Base.y': 'MountParameters.PlateCy %s MountParameters.PlateH / 2 %s' % ('-' if sy < 0 else '+', '- 0.01 mm' if sy < 0 else '- MountParameters.PlateCornerR'),
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.01 mm'})
        cc = prim(doc, 'Part::Cylinder', 'PlateCornerArc%d' % i, 'Plate corner arc %d' % i, {
            'Radius': 'MountParameters.PlateCornerR', 'Height': 'MountParameters.PlateT + 0.04 mm',
            'Placement.Base.x': 'MountParameters.PlateCx %s (MountParameters.PlateW / 2 - MountParameters.PlateCornerR)' % ('-' if sx < 0 else '+'),
            'Placement.Base.y': 'MountParameters.PlateCy %s (MountParameters.PlateH / 2 - MountParameters.PlateCornerR)' % ('-' if sy < 0 else '+'),
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.02 mm'})
        trim = tagged(doc.addObject('Part::Cut', 'PlateCornerTrim%d' % i)); trim.Base = cb; trim.Tool = cc
        trim.Label = 'Plate corner trim %d' % i
        corners += [cb, cc, trim]
    cutters = [c for c in corners if c.TypeId == 'Part::Cut']
    for key, xs, ys in HOLES:
        at = {'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys}
        cutters.append(prim(doc, 'Part::Cylinder', 'PlateHole' + key, 'Plate screw hole ' + key, dict(at, **{
            'Radius': 'MountParameters.PlateHoleD / 2', 'Height': 'MountParameters.PlateT + 0.2 mm',
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.1 mm'})))
        cutters.append(prim(doc, 'Part::Cone', 'PlateCsink' + key, 'Plate countersink ' + key, dict(at, **{
            'Radius1': 'MountParameters.CsinkD / 2 + 0.1 mm', 'Radius2': 'MountParameters.PlateHoleD / 2',
            'Height': '(MountParameters.CsinkD - MountParameters.PlateHoleD) / 2 + 0.1 mm',
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.1 mm'})))
    for key, dx, dy in CUPS:
        cx = 'MountParameters.PlateCx + ' + dx
        cy = 'MountParameters.PlateCy + ' + dy
        cutters.append(prim(doc, 'Part::Cylinder', 'KeyEntry' + key, 'Keyhole entry ' + key, {
            'Radius': 'MountParameters.KeyholeD / 2', 'Height': 'MountParameters.PlateT + 0.2 mm',
            'Placement.Base.x': cx, 'Placement.Base.y': cy + ' - MountParameters.KeySlotL',
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.1 mm'}))
        cutters.append(prim(doc, 'Part::Box', 'KeySlot' + key, 'Keyhole slot ' + key, {
            'Length': 'MountParameters.KeySlotW', 'Width': 'MountParameters.KeySlotL',
            'Height': 'MountParameters.PlateT + 0.2 mm',
            'Placement.Base.x': cx + ' - MountParameters.KeySlotW / 2', 'Placement.Base.y': cy + ' - MountParameters.KeySlotL',
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.1 mm'}))
        cutters.append(prim(doc, 'Part::Cylinder', 'KeyEnd' + key, 'Keyhole locked end ' + key, {
            'Radius': 'MountParameters.KeySlotW / 2', 'Height': 'MountParameters.PlateT + 0.2 mm',
            'Placement.Base.x': cx, 'Placement.Base.y': cy,
            'Placement.Base.z': PLATE_FRONT + ' - MountParameters.PlateT - 0.1 mm'}))
        # front pocket so the stud head seats when the plate is thicker than the neck
        cutters.append(prim(doc, 'Part::Box', 'KeyPocket' + key, 'Keyhole head pocket ' + key, {
            'Length': 'MountParameters.StudHeadD + 0.6 mm', 'Width': 'MountParameters.KeySlotL + MountParameters.StudHeadD + 0.6 mm',
            'Height': 'max(MountParameters.PlateT - MountParameters.StudNeckL; 0 mm) + 0.1 mm',
            'Placement.Base.x': cx + ' - (MountParameters.StudHeadD + 0.6 mm) / 2',
            'Placement.Base.y': cy + ' - MountParameters.KeySlotL - (MountParameters.StudHeadD + 0.6 mm) / 2',
            'Placement.Base.z': PLATE_FRONT + ' - max(MountParameters.PlateT - MountParameters.StudNeckL; 0 mm)'}))
    tool = tagged(doc.addObject('Part::MultiFuse', 'PlateCutters')); tool.Label = 'Plate cutters'; tool.Shapes = cutters
    plate = tagged(doc.addObject('Part::Cut', 'BackplatePlate')); plate.Label = 'Backplate - printed'
    plate.Base = blank; plate.Tool = tool; plate.Refine = True
    for o in [blank, tool] + corners + cutters:
        o.Visibility = False
    group.addObject(plate)
    parts = [plate]
    for key, dx, dy in CUPS:
        cx = 'MountParameters.PlateCx + ' + dx
        cy = 'MountParameters.PlateCy + ' + dy
        rear = PLATE_FRONT + ' - MountParameters.PlateT'
        skirt = prim(doc, 'Part::Cone', 'CupSkirt' + key, 'Cup skirt ' + key, {
            'Radius1': 'MountParameters.CupD / 2', 'Radius2': 'MountParameters.CupD / 5',
            'Height': 'MountParameters.CupH',
            'Placement.Base.x': cx, 'Placement.Base.y': cy, 'Placement.Base.z': rear + ' - MountParameters.CupH'})
        neck = prim(doc, 'Part::Cylinder', 'CupNeck' + key, 'Cup neck ' + key, {
            'Radius': 'MountParameters.StudNeckD / 2', 'Height': 'MountParameters.StudNeckL',
            'Placement.Base.x': cx, 'Placement.Base.y': cy, 'Placement.Base.z': rear})
        head = prim(doc, 'Part::Cylinder', 'CupHead' + key, 'Cup head ' + key, {
            'Radius': 'MountParameters.StudHeadD / 2', 'Height': 'MountParameters.StudHeadT',
            'Placement.Base.x': cx, 'Placement.Base.y': cy,
            'Placement.Base.z': rear + ' + MountParameters.StudNeckL'})
        cup = tagged(doc.addObject('Part::MultiFuse', 'SuctionCup' + key))
        cup.Label = 'Suction cup %s (proxy)' % {'UL': 'upper left', 'UR': 'upper right', 'LO': 'lower'}[key]
        cup.Shapes = [skirt, neck, head]; cup.Refine = True
        for o in (skirt, neck, head):
            o.Visibility = False
        group.addObject(cup); parts.append(cup)
    for i, (key, xs, ys) in enumerate(HOLES, 1):
        at = {'Placement.Base.x': 'MountParameters.' + xs, 'Placement.Base.y': 'MountParameters.' + ys}
        rear = PLATE_FRONT + ' - MountParameters.PlateT'
        csk = prim(doc, 'Part::Cone', 'ScrewHead' + key, 'Screw head ' + key, dict(at, **{
            'Radius1': 'MountParameters.CsinkD / 2 - 0.25 mm', 'Radius2': '1.25 mm',
            'Height': '(MountParameters.CsinkD - 0.5 mm - 2.5 mm) / 2', 'Placement.Base.z': rear}))
        shank = prim(doc, 'Part::Cylinder', 'ScrewShank' + key, 'Screw shank ' + key, dict(at, **{
            'Radius': '1.0 mm', 'Height': 'MountParameters.PlateScrewL', 'Placement.Base.z': rear}))
        screw = tagged(doc.addObject('Part::Fuse', 'PlateScrew%d' % i))
        screw.Label = 'Plate screw %d - M2.5 x 8 countersunk' % i; screw.Base = csk; screw.Tool = shank
        csk.Visibility = shank.Visibility = False
        doc.getObject('Fasteners').addObject(screw); parts.append(screw)
    return parts


def update_board(doc, step):
    board = doc.getObject('BoardRev4')
    shape = Part.read(step)
    board.Shape = shape
    board.Placement = App.Placement(App.Vector(-127.583333, 151.9861, -5.1), App.Rotation())


EXPLODE = {  # source object -> z offset in the exploded view
    'OuterBody': 45.0,
    'HeatSetInsert1': 28.0, 'HeatSetInsert2': 28.0, 'HeatSetInsert3': 28.0, 'HeatSetInsert4': 28.0,
    'BoardRev4': 0.0,
    'Standoff1': -14.0, 'Standoff2': -14.0, 'Standoff3': -14.0, 'Standoff4': -14.0,
    'BackplatePlate': -34.0,
    'SuctionCupUL': -48.0, 'SuctionCupUR': -48.0, 'SuctionCupLO': -48.0,
    'PlateScrew1': -62.0, 'PlateScrew2': -62.0, 'PlateScrew3': -62.0, 'PlateScrew4': -62.0,
}
RETIRED = ('PCBMountScrew1', 'PCBMountScrew2', 'PCBMountScrew3', 'PCBMountScrew4', 'LoopVelcro', 'Part__Feature001')


def build_exploded(doc):
    view = doc.getObject('ExplodedView')
    for name in RETIRED + tuple(EXPLODE):
        old = doc.getObject('Exploded_' + name)
        if old is not None:
            doc.removeObject(old.Name)
    doc.recompute()
    for o in list(view.Group):  # plain labels instead of FreeCAD's auto-numbered duplicates
        src = doc.getObject(o.Name.replace('Exploded_', '', 1))
        if src is not None:
            o.Label = src.Label + ' - exploded'
    for name, dz in EXPLODE.items():
        src = doc.getObject(name)
        copy = tagged(doc.addObject('Part::Feature', 'Exploded_' + name))
        copy.Label = src.Label + ' - exploded'
        shape = src.Shape.copy()
        shape.translate(App.Vector(0, 0, dz))
        copy.Shape = shape
        copy.Visibility = False
        view.addObject(copy)
        style(copy, src)


COLOURS = {'OuterBody': (0.53, 0.13, 0.67), 'BackplatePlate': (0.30, 0.30, 0.33),
           'HeatSetInsert': (0.80, 0.62, 0.25), 'Standoff': (0.85, 0.70, 0.30),
           'PlateScrew': (0.65, 0.65, 0.68), 'SuctionCup': (0.80, 0.85, 0.90)}


def style(obj, src=None):
    vo = getattr(obj, 'ViewObject', None)
    if vo is None:
        return
    key = next((k for k in COLOURS if (src or obj).Name.startswith(k)), None)
    if src is not None and getattr(src, 'ViewObject', None) is not None and key is None:
        vo.ShapeColor = src.ViewObject.ShapeColor
    elif key:
        vo.ShapeColor = COLOURS[key]
    if (src or obj).Name.startswith('SuctionCup'):
        vo.Transparency = 35


STEP_GROUPS = [('Housing', ['Cover___V3_v5', 'Body']), ('PCBA', ['PCBA']), ('OLEDModule', ['OLEDModule']),
               ('DistanceSensor', ['DistanceSensor']), ('BatteryAssembly', ['BatteryAssembly']),
               ('Fasteners', ['Fasteners']), ('Backplate', ['Backplate']), ('CableHarness', ['CableHarness'])]


def visible_leaves(obj):
    if not obj.Visibility and obj.TypeId != 'App::Part':
        return []
    if obj.TypeId == 'App::Part':
        return [leaf for child in obj.Group for leaf in visible_leaves(child)]
    if obj.TypeId == 'PartDesign::Body':
        return [obj]
    if obj.TypeId == 'App::Link':
        return [obj]
    return [obj] if hasattr(obj, 'Shape') and not obj.Shape.isNull() else []


def export_step(doc, path):
    import Import
    prefs = App.ParamGet('User parameter:BaseApp/Preferences/Document')
    duplicate = prefs.GetBool('DuplicateLabels', False)
    prefs.SetBool('DuplicateLabels', True)   # keep part names identical to the assembly labels
    root = doc.addObject('App::Part', 'DTTExport')
    temp = [root]
    for label, sources in STEP_GROUPS:
        group = doc.addObject('App::Part', 'Export' + label); group.Label = label
        root.addObject(group); temp.append(group)
        for src in sources:
            for leaf in visible_leaves(doc.getObject(src)):
                shape = leaf.LinkedObject.Shape.copy() if leaf.TypeId == 'App::Link' else leaf.Shape.copy()
                if leaf.TypeId == 'App::Link':
                    shape.Placement = leaf.Placement.multiply(shape.Placement)
                part = doc.addObject('Part::Feature', 'Export_' + leaf.Name)
                part.Shape = shape; part.Label = leaf.Label
                group.addObject(part); temp.append(part)
                style(part, leaf.LinkedObject if leaf.TypeId == 'App::Link' else leaf)
    doc.recompute()
    Import.export([root], path)
    names = [t.Label for t in temp if t.TypeId == 'Part::Feature']
    for t in reversed(temp):
        doc.removeObject(t.Name)
    prefs.SetBool('DuplicateLabels', duplicate)
    return names


def export_parts(doc, out):
    import Mesh, MeshPart, importDXF
    os.makedirs(out, exist_ok=True)
    plate = doc.getObject('BackplatePlate'); body = doc.getObject('OuterBody')
    for obj, stem in ((body, 'DTT-Outer-Body'), (plate, 'DTT-Backplate')):
        obj.Shape.exportStep(os.path.join(out, stem + '.step'))
        mesh = MeshPart.meshFromShape(Shape=obj.Shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False)
        mesh.write(os.path.join(out, stem + '.stl'))
    # Plate drawing, 1:1 in device XY: through-features at mid-thickness plus countersink outlines.
    bb = plate.Shape.BoundBox
    wires = plate.Shape.slice(App.Vector(0, 0, 1), (bb.ZMin + bb.ZMax) / 2)
    section = Part.Compound(wires); section.translate(App.Vector(0, 0, -section.BoundBox.ZMin))
    sheet = doc.getObject('MountParameters')
    sinks = Part.Compound([Part.makeCircle(float(sheet.CsinkD) / 2, App.Vector(float(getattr(sheet, xs)), float(getattr(sheet, ys)), 0))
                           for _, xs, ys in HOLES])
    objs = []
    for name, shape in (('Plate_outline_and_through_holes', section), ('Countersink_90deg_rear_face', sinks)):
        o = doc.addObject('Part::Feature', name); o.Shape = shape; objs.append(o)
    importDXF.export(objs, os.path.join(out, 'DTT-Backplate.dxf'))
    for o in objs:
        doc.removeObject(o.Name)


def write_3mf(doc, path):
    """Body + diffuser print-in-place file: two materials, rim plane on the bed."""
    import MeshPart, zipfile
    from xml.sax.saxutils import quoteattr
    parts = [(doc.getObject('OuterBody'), 'Outer Body', 0), (doc.getObject('IntegratedDiffuser'), 'Diffuser - white - print with outer body', 1)]
    out = ['<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" unit="millimeter" xml:lang="en-US"><resources>'
           '<basematerials id="1"><base name="Outer Body" displaycolor="#8721ABFF" /><base name="White Diffuser" displaycolor="#F5F5F0FF" /></basematerials>']
    for oid, (obj, name, index) in enumerate(parts, 2):
        mesh = MeshPart.meshFromShape(Shape=obj.Shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False)
        pts, tris = mesh.Topology
        out.append('<object id="%d" type="model" name=%s pid="1" pindex="%d"><mesh><vertices>' % (oid, quoteattr(name), index))
        out.append(''.join('<vertex x="%.6g" y="%.6g" z="%.6g" />' % (p.x, p.y, p.z) for p in pts))
        out.append('</vertices><triangles>')
        out.append(''.join('<triangle v1="%d" v2="%d" v3="%d" />' % t for t in tris))
        out.append('</triangles></mesh></object>')
    lift = -doc.getObject('OuterBody').Shape.BoundBox.ZMin
    out.append('<object id="4" type="model" name="DTT Outer Body - print together"><components><component objectid="2" /><component objectid="3" /></components></object>'
               '</resources><build><item objectid="4" transform="1 0 0 0 1 0 0 0 1 0 0 %.6g" /></build></model>' % lift)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" /><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" /></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" /></Relationships>')
        z.writestr('3D/3dmodel.model', ''.join(out))


TOP_GROUPS = ['Cover___V3_v5', 'Part', 'PCBA', 'Offboard', 'CableHarness', 'Fasteners', 'Backplate', 'ExplodedView']
VIEWS = {  # image -> visible top-level groups
    'DTT-Assembled.png': ['Cover___V3_v5', 'Part', 'PCBA', 'Offboard', 'CableHarness', 'Fasteners', 'Backplate'],
    'DTT-Internal-Assembly.png': ['PCBA', 'Offboard', 'CableHarness', 'Fasteners'],
    'DTT-Exploded.png': ['ExplodedView'],
}


def render_previews(doc):
    import FreeCADGui as Gui
    App.ParamGet('User parameter:BaseApp/Preferences/View').SetBool('ShowNaviCube', False)
    App.ParamGet('User parameter:BaseApp/Preferences/View').SetBool('ShowAxisCross', False)
    gdoc = Gui.getDocument(doc.Name)
    view = gdoc.ActiveView or gdoc.mdiViewsOfType('Gui::View3DInventor')[0]
    saved = {n: doc.getObject(n).Visibility for n in TOP_GROUPS}
    explode_saved = {o.Name: o.Visibility for o in doc.getObject('ExplodedView').Group}
    for image, groups in VIEWS.items():
        for n in TOP_GROUPS:
            doc.getObject(n).Visibility = n in groups
        for o in doc.getObject('ExplodedView').Group:
            o.Visibility = image == 'DTT-Exploded.png'
        view.viewIsometric(); view.fitAll()
        view.saveImage(os.path.join(CAD, image), 1400, 1400, 'White')
    # Rear view: plate, cups and screw heads as seen from the wall.
    for n in TOP_GROUPS:
        doc.getObject(n).Visibility = n in VIEWS['DTT-Assembled.png']
    view.setCameraOrientation(App.Rotation(App.Vector(0, 1, 0), 180)); view.fitAll()   # from the wall side, device top up
    view.saveImage(os.path.join(CAD, 'screw-mount', 'DTT-Backplate-Rear.png'), 1400, 1400, 'White')
    view.viewRight(); view.fitAll()
    view.saveImage(os.path.join(CAD, 'screw-mount', 'DTT-Mount-Side.png'), 1400, 1400, 'White')
    for n, v in saved.items():
        doc.getObject(n).Visibility = v
    for n, v in explode_saved.items():
        doc.getObject(n).Visibility = v


def main():
    doc = App.openDocument(DOC) if App.ActiveDocument is None or not (App.ActiveDocument.FileName or '').endswith('DTT.FCStd') else App.ActiveDocument
    remove_tagged(doc)
    spreadsheet(doc)
    body = build_housing(doc)
    doc.getObject('Cover___V3_v5').addObject(body)
    build_hardware(doc)
    build_plate(doc)
    step = os.environ.get('DTT_BOARD_STEP')
    if step:
        update_board(doc, step)
    doc.recompute()
    body.Visibility = True
    for o in doc.Objects:
        if getattr(o, 'MountRole', '') == TAG and o.TypeId != 'App::Part' and o.Visibility:
            style(o)
    build_exploded(doc)
    doc.recompute()
    if os.environ.get('DTT_EXPORT', '1') == '1':
        exports = os.path.join(ROOT, 'hardware', 'production-exports', 'cad')
        names = export_step(doc, os.path.join(CAD, 'DTT.step'))
        print('STEP parts:', len(names))
        export_parts(doc, os.path.join(exports, 'screw-mount'))
        write_3mf(doc, os.path.join(exports, 'integrated-diffuser', 'DTT-Outer-Body-Print-in-Place.3mf'))
    doc.recompute()
    if App.GuiUp and os.environ.get('DTT_PREVIEWS', '1') == '1':
        render_previews(doc)
    doc.save()
    return doc


if __name__ == '__main__' or True:
    DOCUMENT = main()
