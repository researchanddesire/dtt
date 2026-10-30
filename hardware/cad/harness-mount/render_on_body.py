"""Renders the O-ring harness mount worn on a plain crash-test-dummy lower body, with a 1 in waist belt and
two leg straps, to show how it belts on. Run under the FreeCAD GUI after build_harness_mount.py:

    xvfb-run -a freecad render_on_body.FCMacro   (a macro that execs this file)

The dummy is a stand-in, sized like an adult and shaped so its front meets the panel, not a body scan."""

import math, os
import FreeCAD as App
import FreeCADGui as Gui
import Part

V = App.Vector
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(HERE, 'images')
SOURCE = os.path.join(HERE, 'DTT-Harness-Mount-Ring.FCStd')

AX, AY = 21.0, -33.8          # toy axis of the ring version (build_harness_mount.axis())
Z_REAR, PAD_T = -15.1, 5.0    # flat plate rear and pad thickness
PAD_RX, PAD_RUP, PAD_RDOWN = 120.0, 1500.0, 65.0
WAIST = (62.0, 84.0)          # panel hip ear x offset from the axis, y
LEG_R, LEG_DEG = 37.0, 38.0
STRAP_W, STRAP_T = 25.4, 1.6

DUMMY = (0.93, 0.72, 0.16)    # crash-test yellow
JOINT = (0.22, 0.22, 0.24)
WEBBING = (0.07, 0.07, 0.08)
HARDWARE = (0.45, 0.46, 0.50)


def sag(r, d):
    return r - math.sqrt(max(r * r - d * d, 0.0))


def rear_z(x, y):
    dy = y - AY
    return Z_REAR - sag(PAD_RX, x - AX) - sag(PAD_RUP if dy > 0 else PAD_RDOWN, dy)


# ---------------------------------------------------------------- dummy

# (dy from the toy axis, half width, half depth, front z); between -60 and 150 the front follows the pad
ANCHORS = [(-60, 160, 100, None), (-30, 175, 112, None), (0, 176, 113, None), (60, 168, 110, None),
           (120, 155, 104, None), (150, 150, 101, None), (170, 140, 98, -35), (220, 146, 101, -37)]


def front_z(dy):
    return rear_z(AX, AY + dy) - PAD_T - 0.3


def profile(dy):
    for (d0, a0, b0, f0), (d1, a1, b1, f1) in zip(ANCHORS, ANCHORS[1:]):
        if d0 <= dy <= d1:
            f = (dy - d0) / (d1 - d0)
            f0 = front_z(d0) if f0 is None else f0
            f1 = front_z(d1) if f1 is None else f1
            zf = front_z(dy) if -60 <= dy <= 150 else f0 + f * (f1 - f0)
            return a0 + f * (a1 - a0), b0 + f * (b1 - b0), zf
    raise ValueError(dy)


def sections(grow=0.0):
    """Evenly and widely spaced: a smooth loft through close or uneven sections overshoots."""
    return [(AY + dy, a + grow, b + grow, zf + grow) for dy in range(-60, 211, 30)
            for a, b, zf in [profile(dy)]]


def section_wire(y, a, b, zf, n=32):
    """Ellipse in XZ, its front pulled in to the pad's 120 mm curve over the middle, like a pubic mound."""
    zc = zf - b; pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = a * math.sin(t); z = zc + b * math.cos(t)
        if math.cos(t) > 0:
            dx = abs(x); w = 1.0 if dx < 45 else max(0.0, 1 - (dx - 45) / 60.0)
            w = w * w * (3 - 2 * w)
            z -= w * max(0.0, sag(PAD_RX, min(dx, PAD_RX - 1)) - (zf - z))
        pts.append(V(AX + x, y, z))
    c = Part.BSplineCurve(); c.interpolate(pts, PeriodicFlag=True)
    return Part.Wire(c.toShape())


def ellipsoid(c, rx, ry, rz):
    m = App.Matrix(); m.scale(rx, ry, rz)
    return Part.makeSphere(1.0).transformGeometry(m).translated(c)


def torso(grow=0.0):
    """Loft from the hips to the lower ribs, closed below by a rounded pelvis."""
    loft = Part.makeLoft([section_wire(*s) for s in sections(grow)], True, False, False, 3)
    y0, a, b, zf = sections(grow)[0]; zc = zf - b
    parts = [ellipsoid(V(AX, y0, zc), a, 95 + grow, b)]
    return [loft] + parts


def centre_z(y):
    s = sections()
    for (y0, a0, b0, f0), (y1, a1, b1, f1) in zip(s, s[1:]):
        if y0 <= y <= y1:
            f = (y - y0) / (y1 - y0)
            return (f0 - b0) + f * ((f1 - b1) - (f0 - b0))
    return s[-1][3] - s[-1][2]


def thigh(s, grow=0.0):
    top = V(AX + s * 84, AY + 40, -150); d = V(s * 0.08, -1, 0); d.normalize()
    return Part.makeCone(74 + grow, 54 + grow, 450, top, d), top, d


def dummy():
    """The dummy as overlapping solids (fusing the lofted torso with the rest is slow and fragile), and
    its dark joints."""
    legs = [thigh(s) for s in (-1, 1)]
    joints = [Part.makeCylinder(46, 14, top + d * 446, d) for _, top, d in legs]      # knees
    y_top = sections()[-1][0]       # lumbar stub on the cut-off top
    joints.append(Part.makeCylinder(55, 22, V(AX, y_top - 2, centre_z(y_top)), V(0, 1, 0)))
    return torso() + [l[0] for l in legs], Part.makeCompound(joints)


def target(body_out, body, c, n, r=26):
    """Black and yellow quadrant target sticker, wrapped onto the body at c, facing n."""
    n = V(n); n.normalize()
    u = n.cross(V(0, 1, 0)) if abs(n.y) < 0.9 else n.cross(V(1, 0, 0)); u.normalize()
    w = n.cross(u)
    disc = Part.makeCylinder(r, 60, c - n * 30, n)
    skin = body_out.common(disc).cut(body)
    q = []
    for k in (0, 2):
        m = App.Matrix(); m.A11, m.A21, m.A31 = u.x, u.y, u.z; m.A12, m.A22, m.A32 = w.x, w.y, w.z
        m.A13, m.A23, m.A33 = n.x, n.y, n.z
        wedge = Part.makeCylinder(r - 3, 60, V(0, 0, -30), V(0, 0, 1), 90).rotated(V(0, 0, 0), V(0, 0, 1), 90 * k)
        wedge.transformShape(m); wedge.translate(c)
        q.append(wedge)
    ring = Part.makeCylinder(r, 60, c - n * 30, n).cut(Part.makeCylinder(r - 3, 60, c - n * 30, n))
    black = skin.common(ring.fuse(q))
    return black, skin.cut(black)


# ---------------------------------------------------------------- straps

def hit(solids, o, d, start_inside, reach=700.0):
    """Where the ray o + t d first crosses the surface of the union of the solids (its exit if it starts
    inside, else its entry)."""
    d = V(d); d.normalize(); line = Part.LineSegment(o, o + d * reach).toShape()
    ts = []
    for i, sol in enumerate(solids):
        for v in line.section(sol).Vertexes:
            if not any(o2.isInside(v.Point, 0.01, False) for j, o2 in enumerate(solids) if j != i):
                ts.append((v.Point - o).dot(d))
    ts = sorted(t for t in ts if t > 1e-3)
    if not ts:
        raise RuntimeError('ray missed: %s %s' % (o, d))
    return o + d * ts[0], d


def on_surface(shape, pts):
    """(point, outward normal) lying STRAP_T/2 off the surface, from (origin, direction, inside?) rays."""
    out = []
    for o, d, ins in pts:
        p, dd = hit(shape, o, d, ins)
        nrm = dd if ins else dd * -1
        out.append((p + nrm * (STRAP_T / 2 + 0.6), nrm))
    return out


def strip(path, width=STRAP_W, align=None, step=5.0):
    """Webbing along a list of (point, surface normal): thin rectangles laid on the surface every step mm
    along a spline through the points, joined by a ruled loft (a smooth one overshoots on the tight
    turns)."""
    pts = [p for p, _ in path]
    c = Part.BSplineCurve(); c.interpolate(pts)
    us = [c.parameter(p) for p in pts]
    n_seg = max(2, int(c.length() / step))
    wires, w_prev = [], None
    for k in range(n_seg + 1):
        u = us[0] + (us[-1] - us[0]) * k / n_seg
        i = max(j for j in range(len(us) - 1) if us[j] <= u + 1e-9) if u < us[-1] else len(us) - 2
        f = (u - us[i]) / (us[i + 1] - us[i])
        n = path[i][1] * (1 - f) + path[i + 1][1] * f
        p = c.value(u); t = c.tangent(u)[0]
        if align:
            w = V(align[i]) * (1 - f) + V(align[i + 1]) * f
        else:
            w = t.cross(n)
        w.normalize()
        if w_prev is not None and w.dot(w_prev) < 0:
            w = w * -1
        w_prev = w
        n = w.cross(t); n.normalize()
        hw, ht = w * (width / 2), n * (STRAP_T / 2)
        q = [p + hw + ht, p - hw + ht, p - hw - ht, p + hw - ht]
        wires.append(Part.makePolygon(q + [q[0]]))
    return Part.makeLoft(wires, True, True, False)


def belt(body, panel):
    """Round the back at the hip ears' height, each end sewn onto the front of an ear."""
    y = WAIST[1]; zc = centre_z(y); solids = body + [panel]
    front = lambda x: (V(x, y, 200), V(0, 0, -1), False)
    rays = [front(AX + WAIST[0] - 14), front(AX + WAIST[0] - 4)]
    rays += [(V(AX, y, zc), V(math.sin(math.radians(5 * k)), 0, math.cos(math.radians(5 * k))), True)
             for k in range(4, 73)]
    rays += [front(AX - WAIST[0] + 4), front(AX - WAIST[0] + 14)]
    path = on_surface(solids, rays)
    keep = path[:2] + [p for p in path[2:-2] if abs(p[0].x - AX) > WAIST[0] + 8] + path[-2:]
    return strip(keep, align=[V(0, 1, 0)] * len(keep))


def leg_strap(body, panel, s):
    """Sewn onto the front of the panel tip, down into the crease at the top of the inner thigh, round
    under the cheek and up the back to the belt."""
    solids = body + [panel]
    rays = [(V(AX + s * x, y, 200), V(0, 0, -1), False) for x, y in [(14, -62), (17, -72), (23, -88), (23, -100)]]
    y0, a, b, zf = sections()[0]
    for phi, x in [(55, 22), (78, 22), (100, 22), (125, 26), (150, 40)]:      # under the pelvis, between the legs
        f = math.radians(phi)
        rays.append((V(AX + s * x, y0, zf - b), V(0, -math.sin(f), math.cos(f)), True))
    for x, y in [(40, -110), (50, -65), (56, -10), (56, 40), (54, 70)]:
        rays.append((V(AX + s * x, y, centre_z(y)), V(s * 0.3, 0, -1), True))
    return strip(on_surface(solids, rays))


def buckle(body):
    """A ladder-lock slider on the belt at the right hip."""
    y = WAIST[1]; phi = math.radians(62)
    (p, n), = on_surface(body, [(V(AX, y, centre_z(y)), V(math.sin(phi), 0, math.cos(phi)), True)])
    frame = Part.makeBox(40, 32, 4, V(-20, -16, 0)).cut(Part.makeBox(30, 26, 6, V(-15, -13, -1)))
    frame = frame.fuse(Part.makeBox(30, 3, 4, V(-15, -1.5, 0)))
    ang = math.degrees(math.atan2(n.x, n.z))
    frame.rotate(V(0, 0, 0), V(0, 1, 0), ang)
    return frame.translated(p + n * 0.8)


# ---------------------------------------------------------------- scene

def visible(o):
    while o is not None:
        if not o.Visibility:
            return False
        o = o.getParentGeoFeatureGroup()
    return True


def scene(src, turn=None):
    tmp = App.newDocument('OnBody')

    def add(name, shape, colour=None, like=None):
        s = shape.copy()
        if turn is not None:
            s.transformShape(turn)
        o = tmp.addObject('Part::Feature', name); o.Shape = s
        if like is not None:
            o.ViewObject.ShapeAppearance = like.ViewObject.ShapeAppearance
            o.ViewObject.Transparency = like.ViewObject.Transparency
        if colour is not None:
            o.ViewObject.ShapeColor = colour
        o.ViewObject.DisplayMode = 'Shaded'
        o.ViewObject.Deviation = 0.05
        return o

    for o in src.Objects:
        if o.TypeId.startswith('Part::') and visible(o) and not o.Shape.isNull() and o.Name not in ('HarnessPins',):
            add(o.Name, o.Shape, like=o,
                colour=(0.62, 0.63, 0.67) if o.Name in ('SnapDDScrew', 'SnapDoubleDouble') else None)
    for n, (shape, col) in PARTS.items():
        add(n, shape, col)
    tmp.recompute()
    return tmp


def shoot(src, fname, cam, turned=False):
    turn = None
    if turned:
        turn = App.Placement(V(0, 0, 0), App.Rotation(V(0, 1, 0), 180), V(AX, 0, -130)).toMatrix()
    tmp = scene(src, turn)
    Gui.ActiveDocument = Gui.getDocument(tmp.Name)
    view = Gui.getDocument(tmp.Name).ActiveView
    view.setCameraOrientation(cam); view.fitAll(); Gui.updateGui(); view.fitAll(); Gui.updateGui()
    view.saveImage(os.path.join(IMAGES, fname), 1600, 1600, 'Current')
    App.closeDocument(tmp.Name)


def main():
    global PARTS
    pv = App.ParamGet('User parameter:BaseApp/Preferences/View')
    pv.SetBool('ShowNaviCube', False); pv.SetBool('ShowAxisCross', False)
    pv.SetBool('Gradient', True); pv.SetBool('Simple', False)
    rgb = lambda r, g, b: (int(r * 255) << 24) | (int(g * 255) << 16) | (int(b * 255) << 8)
    pv.SetUnsigned('BackgroundColor2', rgb(0.93, 0.93, 0.95))
    pv.SetUnsigned('BackgroundColor3', rgb(0.70, 0.71, 0.75))

    src = App.openDocument(SOURCE)
    panel = src.getObject('HarnessPad').Shape
    body, joints = dummy()
    skin = torso(0.7)[0]
    stickers_b, stickers_y = [], []
    for s in (-1, 1):
        y = AY + 15
        (p, n), = on_surface(body, [(V(AX, y, centre_z(y)), V(s, 0, 0), True)])
        b, w = target(skin, body[0], p, n); stickers_b.append(b); stickers_y.append(w)
    PARTS = {
        'Dummy': (Part.makeCompound(body), DUMMY), 'DummyJoints': (joints, JOINT),
        'TargetBlack': (Part.makeCompound(stickers_b), JOINT), 'TargetYellow': (Part.makeCompound(stickers_y), (0.98, 0.86, 0.1)),
        'WaistBelt': (belt(body, panel), WEBBING),
        'LegStraps': (Part.makeCompound([leg_strap(body, panel, s) for s in (-1, 1)]), WEBBING),
        'Buckle': (buckle(body), HARDWARE),
    }
    pic = 'Harness-Mount-Ring-On-Body'
    shoot(src, pic + '-Front.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)))
    shoot(src, pic + '-Side.png', App.Rotation(V(0, 1, 0), 90).multiply(App.Rotation(V(1, 0, 0), -4)))
    shoot(src, pic + '-Back.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)), turned=True)
    App.closeDocument(src.Name)


main()
