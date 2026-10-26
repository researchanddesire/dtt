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
    ('Plate', None, None, 'Backplate outline from DTT-Backplate-Proxy.FCStd; plate-local origin at bottom centre'),
    ('PlateT', 4.0, 'mm', 'reference proxy: estimated, measure the existing plate'),
    ('PlateH', 200.0, 'mm', 'reference proxy: bottom to top'),
    ('PlateUpperW', 75.0, 'mm', 'reference proxy: width of the straight upper sides'),
    ('PlateTopR', 5.0, 'mm', 'reference proxy: upper corner radius'),
    ('PlateShoulderR', 12.5, 'mm', 'reference proxy: convex lower corner of the upper section'),
    ('PlateWaistW', 50.0, 'mm', 'reference proxy: narrowest width at the waist'),
    ('PlateNeckR', 15.0, 'mm', 'reference proxy: concave waist radius'),
    ('PlatePadD', 80.0, 'mm', 'reference proxy: lower circular pad diameter'),
    ('DeviceTopInset', 17.0, 'mm', 'reference proxy: plate top to housing top'),
    ('DeviceCx', 21.0, 'mm', 'verified: housing centreline'),
    ('DeviceTopY', 93.0, 'mm', 'verified: housing top'),
    ('PlateX0', '=DeviceCx', 'mm', 'derived: plate-local origin in device X'),
    ('PlateY0', '=DeviceTopY + DeviceTopInset - PlateH', 'mm', 'derived: plate-local origin in device Y'),
    ('PlatePadR', '=PlatePadD / 2', 'mm', 'derived'),
    ('PlateNeckX', '=PlateWaistW / 2 + PlateNeckR', 'mm', 'derived: neck circle centre'),
    ('PlateNeckY', '=PlatePadR + sqrt((PlatePadR + PlateNeckR) ^ 2 - PlateNeckX ^ 2)', 'mm', 'derived: neck tangent to pad'),
    ('PlateShoulderX', '=PlateUpperW / 2 - PlateShoulderR', 'mm', 'derived: shoulder circle centre'),
    ('PlateShoulderY', '=PlateNeckY + sqrt((PlateNeckR + PlateShoulderR) ^ 2 - (PlateNeckX - PlateShoulderX) ^ 2)', 'mm', 'derived: shoulder tangent to neck'),
    ('PlateJoinX', '=PlateNeckX - (PlateNeckX - PlateShoulderX) * PlateNeckR / (PlateNeckR + PlateShoulderR)', 'mm', 'derived: neck/shoulder tangent point'),
    ('PlateJoinY', '=PlateNeckY + (PlateShoulderY - PlateNeckY) * PlateNeckR / (PlateNeckR + PlateShoulderR)', 'mm', 'derived: neck/shoulder tangent point'),
    ('PlatePadJoinY', '=PlatePadR + (PlateNeckY - PlatePadR) * PlatePadR / (PlatePadR + PlateNeckR)', 'mm', 'derived: pad/neck tangent point'),
    ('PlateHoleD', 2.9, 'mm', 'design: M2.5 clearance'),
    ('CsinkD', 5.0, 'mm', 'design: 90 deg countersink for ISO 10642 M2.5'),
    ('PlateScrewL', 8.0, 'mm', 'design: PlateT + 4 mm thread engagement'),
    ('Cups', None, None, 'Suction cups and keyholes from DTT-Backplate-Proxy.FCStd'),
    ('TopCupInset', 13.0, 'mm', 'reference proxy: top stem row below the plate top'),
    ('TopEntryX', 16.5, 'mm', 'reference proxy: top entry circles from the centreline'),
    ('LowerStemY', 87.0, 'mm', 'reference proxy: lower stem above the plate bottom'),
    ('KeySlotTravel', 12.0, 'mm', 'reference proxy: entry to retained stem; top slots outward, lower slot down'),
    ('KeyEntryD', 14.0, 'mm', 'reference proxy: head insertion diameter'),
    ('KeySlotW', 9.0, 'mm', 'reference proxy: stem retaining slot width'),
    ('CupD', 35.0, 'mm', 'reference proxy: cup rim diameter'),
    ('CupDepth', 14.0, 'mm', 'reference proxy: plate rear to cup rim'),
    ('CupShoulderR', 5.5, 'mm', 'reference proxy: cup radius behind the stem'),
    ('CupWall', 1.2, 'mm', 'reference proxy'),
    ('CupRearGap', 0.6, 'mm', 'reference proxy: cup shoulder to plate rear'),
    ('StemD', 7.5, 'mm', 'reference proxy: stem through the slot'),
    ('HeadD', 12.0, 'mm', 'reference proxy: retaining head'),
    ('HeadT', 1.8, 'mm', 'reference proxy'),
    ('HeadGap', 0.4, 'mm', 'reference proxy: plate front to head underside'),
]


def spreadsheet(doc):
    sheet = doc.getObject('MountParameters')
    wanted = {alias for alias, value, _, _ in PARAMS if value is not None}
    if sheet is not None:
        present = {sheet.getAlias('B%d' % r) for r in range(2, 200) if sheet.getAlias('B%d' % r)}
        if present - wanted:   # parameter set changed: start again from the defaults below
            doc.removeObject(sheet.Name)
            sheet = None
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
            if isinstance(value, str):
                contents = value
            else:
                contents = '=%g %s' % (value, unit) if unit else str(value)
            sheet.set('B%d' % row, contents)
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


M = 'MountParameters.'
# key, stem centre and entry centre in plate-local coordinates
CUPS = [('UL', '-(%sTopEntryX + %sKeySlotTravel)' % (M, M), '%sPlateH - %sTopCupInset' % (M, M), '-%sTopEntryX' % M, '%sPlateH - %sTopCupInset' % (M, M)),
        ('UR', '%sTopEntryX + %sKeySlotTravel' % (M, M), '%sPlateH - %sTopCupInset' % (M, M), '%sTopEntryX' % M, '%sPlateH - %sTopCupInset' % (M, M)),
        ('LO', '0 mm', M + 'LowerStemY', '0 mm', '%sLowerStemY + %sKeySlotTravel' % (M, M))]
PLATE_FRONT = 'MountParameters.PCBTopZ - MountParameters.PCBThickness - MountParameters.StandoffL'
PLATE_REAR = PLATE_FRONT + ' - MountParameters.PlateT'


def gx(u):
    return '%sPlateX0 + (%s)' % (M, u)


def gy(v):
    return '%sPlateY0 + (%s)' % (M, v)


def plate_prism(doc, kind, name, label, exprs, through=False):
    """Primitive spanning the plate thickness (or slightly beyond it for cutters)."""
    pad = '0.1 mm' if through else '0 mm'
    exprs = dict(exprs)
    exprs['Height'] = '%sPlateT + 2 * %s' % (M, pad)
    exprs['Placement.Base.z'] = '%s - %s' % (PLATE_REAR, pad)
    return prim(doc, kind, name, label, exprs)


def disc(doc, name, label, r, u, v, through=False):
    return plate_prism(doc, 'Part::Cylinder', name, label, {
        'Radius': r, 'Placement.Base.x': gx(u), 'Placement.Base.y': gy(v)}, through)


def rect(doc, name, label, u0, u1, v0, v1, through=False):
    return plate_prism(doc, 'Part::Box', name, label, {
        'Length': '(%s) - (%s)' % (u1, u0), 'Width': '(%s) - (%s)' % (v1, v0),
        'Placement.Base.x': gx(u0), 'Placement.Base.y': gy(v0)}, through)


def build_plate(doc):
    group = doc.getObject('Backplate') or doc.addObject('App::Part', 'Backplate')
    group.Label = 'Backplate'
    tagged(group)
    # Outline: straight upper section with rounded top corners, convex shoulders, concave waist, round lower pad.
    hw, tr = M + 'PlateUpperW / 2', M + 'PlateTopR'
    sx, sy, sr = M + 'PlateShoulderX', M + 'PlateShoulderY', M + 'PlateShoulderR'
    pieces = [
        rect(doc, 'PlateUpper', 'Plate upper section', '-' + hw, hw, sy, M + 'PlateH - ' + tr),
        rect(doc, 'PlateTopEdge', 'Plate top edge', '-(%s - %s)' % (hw, tr), '%s - %s' % (hw, tr), M + 'PlateH - ' + tr, M + 'PlateH'),
        disc(doc, 'PlateTopCornerL', 'Plate top corner L', tr, '-(%s - %s)' % (hw, tr), M + 'PlateH - ' + tr),
        disc(doc, 'PlateTopCornerR', 'Plate top corner R', tr, '%s - %s' % (hw, tr), M + 'PlateH - ' + tr),
        disc(doc, 'PlateShoulderL', 'Plate shoulder L', sr, '-' + sx, sy),
        disc(doc, 'PlateShoulderR', 'Plate shoulder R', sr, sx, sy),
        rect(doc, 'PlateShoulderBridge', 'Plate shoulder bridge', '-' + sx, sx, '%s - %s' % (sy, sr), sy),
        rect(doc, 'PlateWaist', 'Plate waist', '-' + M + 'PlateJoinX', M + 'PlateJoinX', M + 'PlatePadJoinY', M + 'PlateJoinY'),
        disc(doc, 'PlatePad', 'Plate lower pad', M + 'PlatePadR', '0 mm', M + 'PlatePadR'),
    ]
    union = tagged(doc.addObject('Part::MultiFuse', 'PlateOutlineUnion')); union.Label = 'Plate outline union'
    union.Shapes = pieces
    necks = [disc(doc, 'PlateNeck' + side, 'Plate neck ' + side, M + 'PlateNeckR',
                  ('-' if side == 'L' else '') + M + 'PlateNeckX', M + 'PlateNeckY', True) for side in 'LR']
    cutters = list(necks)
    for key, xs, ys in HOLES:
        at = {'Placement.Base.x': M + xs, 'Placement.Base.y': M + ys}
        cutters.append(prim(doc, 'Part::Cylinder', 'PlateHole' + key, 'Plate screw hole ' + key, dict(at, **{
            'Radius': M + 'PlateHoleD / 2', 'Height': M + 'PlateT + 0.2 mm',
            'Placement.Base.z': PLATE_REAR + ' - 0.1 mm'})))
        cutters.append(prim(doc, 'Part::Cone', 'PlateCsink' + key, 'Plate countersink ' + key, dict(at, **{
            'Radius1': M + 'CsinkD / 2 + 0.1 mm', 'Radius2': M + 'PlateHoleD / 2',
            'Height': '(%sCsinkD - %sPlateHoleD) / 2 + 0.1 mm' % (M, M),
            'Placement.Base.z': PLATE_REAR + ' - 0.1 mm'})))
    for key, su, sv, eu, ev in CUPS:
        cutters.append(disc(doc, 'KeyEntry' + key, 'Keyhole entry ' + key, M + 'KeyEntryD / 2', eu, ev, True))
        cutters.append(disc(doc, 'KeyEnd' + key, 'Keyhole retained end ' + key, M + 'KeySlotW / 2', su, sv, True))
        w = M + 'KeySlotW / 2'
        if key == 'LO':
            slot = ('-' + w, w, sv, ev)
        else:
            slot = ((su, eu) if key == 'UL' else (eu, su)) + ('(%s) - %s' % (sv, w), '(%s) + %s' % (sv, w))
        cutters.append(rect(doc, 'KeySlot' + key, 'Keyhole slot ' + key, *slot, through=True))
    tool = tagged(doc.addObject('Part::MultiFuse', 'PlateCutters')); tool.Label = 'Plate cutters'; tool.Shapes = cutters
    plate = tagged(doc.addObject('Part::Cut', 'BackplatePlate')); plate.Label = 'Backplate - printed'
    plate.Base = union; plate.Tool = tool; plate.Refine = True
    for o in [union, tool] + pieces + cutters:
        o.Visibility = False
    group.addObject(plate)
    parts = [plate]
    names = {'UL': 'upper left', 'UR': 'upper right', 'LO': 'lower'}
    for key, su, sv, eu, ev in CUPS:
        at = {'Placement.Base.x': gx(su), 'Placement.Base.y': gy(sv)}
        rim = '%s - %sCupDepth' % (PLATE_REAR, M)
        outside = prim(doc, 'Part::Cone', 'CupOutside' + key, 'Cup outside ' + key, dict(at, **{
            'Radius1': M + 'CupD / 2', 'Radius2': M + 'CupShoulderR',
            'Height': '%sCupDepth - %sCupRearGap' % (M, M), 'Placement.Base.z': rim}))
        inside = prim(doc, 'Part::Cone', 'CupInside' + key, 'Cup inside ' + key, dict(at, **{
            'Radius1': '%sCupD / 2 - %sCupWall' % (M, M), 'Radius2': '%sCupShoulderR - %sCupWall' % (M, M),
            'Height': '%sCupDepth - %sCupRearGap - 1.5 mm' % (M, M), 'Placement.Base.z': rim + ' - 0.1 mm'}))
        bell = tagged(doc.addObject('Part::Cut', 'CupBell' + key)); bell.Label = 'Cup bell ' + key
        bell.Base = outside; bell.Tool = inside
        stem = prim(doc, 'Part::Cylinder', 'CupStem' + key, 'Cup stem ' + key, dict(at, **{
            'Radius': M + 'StemD / 2', 'Height': '%sPlateT + %sCupRearGap + 0.5 mm + %sHeadGap' % (M, M, M),
            'Placement.Base.z': '%s - %sCupRearGap - 0.5 mm' % (PLATE_REAR, M)}))
        head = prim(doc, 'Part::Cylinder', 'CupHead' + key, 'Cup head ' + key, dict(at, **{
            'Radius': M + 'HeadD / 2', 'Height': M + 'HeadT',
            'Placement.Base.z': '%s + %sHeadGap' % (PLATE_FRONT, M)}))
        cup = tagged(doc.addObject('Part::MultiFuse', 'SuctionCup' + key))
        cup.Label = 'Suction cup %s (proxy)' % names[key]
        cup.Shapes = [bell, stem, head]; cup.Refine = True
        for o in (outside, inside, bell, stem, head):
            o.Visibility = False
        group.addObject(cup); parts.append(cup)
    for i, (key, xs, ys) in enumerate(HOLES, 1):
        at = {'Placement.Base.x': M + xs, 'Placement.Base.y': M + ys}
        csk = prim(doc, 'Part::Cone', 'ScrewHead' + key, 'Screw head ' + key, dict(at, **{
            'Radius1': M + 'CsinkD / 2 - 0.25 mm', 'Radius2': '1.25 mm',
            'Height': '(%sCsinkD - 0.5 mm - 2.5 mm) / 2' % M, 'Placement.Base.z': PLATE_REAR}))
        shank = prim(doc, 'Part::Cylinder', 'ScrewShank' + key, 'Screw shank ' + key, dict(at, **{
            'Radius': '1.0 mm', 'Height': M + 'PlateScrewL', 'Placement.Base.z': PLATE_REAR}))
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
