"""Renders the O-ring harness mount worn on a reference body, with a 1 in waist belt and two leg straps,
to show how it belts on. Run under the FreeCAD GUI after build_harness_mount.py:

    xvfb-run -a freecad render_on_body.FCMacro   (a macro that execs this file)

The body is reference/body-female-lower.obj: the MakeHuman CC0 average young female, lower body only (see
reference/make_body.py). The panel's curve was fitted to it with the harness tilted TILT deg, so it lies
on the lower belly and the mons; the toy then points that much below level when standing."""

import math, os
import numpy as np
import FreeCAD as App
import FreeCADGui as Gui
import Mesh
import Part

V = App.Vector
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(HERE, 'images')
SOURCE = os.path.join(HERE, 'DTT-Harness-Mount-Ring.FCStd')
BODY = os.path.join(HERE, 'reference', 'body-female-lower.obj')

AX, AY = 21.0, -33.8          # toy axis of the ring version (build_harness_mount.axis())
Z_REAR, PAD_T = -15.1, 5.0    # flat core rear and panel thickness
TILT = 14.0                   # harness tilt on the body, deg: the top lies back on the belly
BODY_AXIS = (-8.0, 117.0)     # body (y, front z) under the toy axis in the mesh frame: over the pubic bone
WAIST = (62.0, 84.0)          # panel hip ear x offset from the axis, y
STRAP_W, STRAP_T = 25.4, 1.6
LEG_W = 30.0                  # leg straps behind: soft, lined

SKIN = (0.80, 0.74, 0.69)     # plain mannequin
WEBBING = (0.07, 0.07, 0.08)
HARDWARE = (0.45, 0.46, 0.50)


# ---------------------------------------------------------------- body

def body():
    """The reference mesh in device coordinates: tilted back TILT deg about the point under the toy axis,
    its front there on the back of the panel."""
    m = Mesh.Mesh(BODY)
    y0, z0 = BODY_AXIS
    m.translate(0, -y0, -z0)
    m.rotate(math.radians(-TILT), 0, 0)
    m.translate(AX, AY, Z_REAR - PAD_T - 0.3)
    return m


def centre_z(m, y, half=60.0):
    """Middle of the torso's depth at height y."""
    zs = [p.z for p in m.Points if abs(p.y - y) < 8 and abs(p.x - AX) < half]
    return (min(zs) + max(zs)) / 2


# ---------------------------------------------------------------- panel

def plan_prism(wire, z0=-400.0, h=800.0):
    pts = [V(q.x, q.y, z0) for q in wire.discretize(240)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, h))


def lobe(s):
    """Plan of one leg strap's front, cut in one piece with the panel: out of its lower side, down the
    leg crease beside the vulva to the top of the inner thigh."""
    pts = [V(AX + s * x, y, -400) for x, y in JOCK_LOBE]
    c = Part.BSplineCurve(); c.interpolate(pts, PeriodicFlag=True)
    return Part.Face(Part.Wire(c.toShape())).extrude(V(0, 0, 800))


JOCK_LOBE = [(26, -42), (44, -44), (49, -62), (45, -86), (36, -110), (28, -130), (21, -136), (17, -128),
             (21, -108), (27, -86), (29, -66), (25, -52)]


def draped(m, pad):
    """The soft panel as it lies on the body, in one piece with the fronts of the leg straps: the builder's
    panel outline and holes, but its back on the skin instead of on the builder's fitted curve (leather
    and foam follow the body)."""
    rear = max(pad.Faces, key=lambda f: f.Area if f.normalAt(*f.Surface.parameter(f.CenterOfMass)).z < -0.5 else 0)
    plan = plan_prism(rear.OuterWire).fuse([lobe(-1), lobe(1)]).removeSplitter()
    bb = plan.BoundBox; bb = App.BoundBox(bb.XMin, bb.YMin, 0, bb.XMax, bb.YMax, 0)
    xs = [bb.XMin - 6 + 6 * i for i in range(int(bb.XLength / 6) + 3)]
    ys = [bb.YMin - 6 + 6 * j for j in range(int(bb.YLength / 6) + 3)]
    sheet = Part.BSplineSurface()
    def skin(x, y):   # outside the plan, between the legs, held up so the sheet doesn't ripple
        ts = [t for t in ray_mesh(m, V(x, y, 300), V(0, 0, -1)) if t > 0]
        z = 300 - min(ts) if ts else -1e9
        return z if plan.isInside(V(x, y, 0), 0.5, True) else max(z, -55.0)
    zs = np.array([[skin(x, y) for y in ys] for x in xs])
    pad_ = np.pad(zs, 1, mode='edge')   # one 3 x 3 smoothing pass: the leather bridges the mesh's facets
    zs = sum(pad_[1 + i:1 + i + len(xs), 1 + j:1 + j + len(ys)] for i in (-1, 0, 1) for j in (-1, 0, 1)) / 9
    sheet.interpolate([[V(x, y, zs[a, b] + 0.3) for b, y in enumerate(ys)] for a, x in enumerate(xs)])
    layer = sheet.toShape().extrude(V(0, 0, PAD_T))
    out = layer.common(plan)
    for w in rear.Wires:
        if not w.isSame(rear.OuterWire):
            out = out.cut(plan_prism(w))
    return out


# ---------------------------------------------------------------- straps

TRIS = {}


def ray_mesh(m, o, d):
    """Distances along the ray to every crossing with the mesh, both ways through the facets."""
    if id(m) not in TRIS:
        TRIS[id(m)] = np.array([[tuple(p) for p in f.Points] for f in m.Facets])
    tri = TRIS[id(m)]; a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    o, d = np.array(tuple(o)), np.array(tuple(d))
    e1, e2 = b - a, c - a
    pv = np.cross(d, e2); det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-12; inv = 1.0 / np.where(ok, det, 1.0)
    tv = o - a; u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, e1); v = (qv * d).sum(1) * inv; t = (e2 * qv).sum(1) * inv
    return t[ok & (u >= 0) & (v >= 0) & (u + v <= 1)]


def hit(m, panel, o, d):
    """First crossing of the ray o + t d with the body mesh or (for rays from outside) the panel."""
    d = V(d); d.normalize()
    ts = list(ray_mesh(m, o, d))
    if panel is not None:
        line = Part.LineSegment(o, o + d * 700).toShape()
        ts += [(v.Point - o).dot(d) for v in line.section(panel).Vertexes]
    ts = sorted(t for t in ts if t > 1e-3)
    if not ts:
        raise RuntimeError('ray missed: %s %s' % (o, d))
    return o + d * ts[0]


def on_surface(m, panel, rays):
    """(point, outward normal) STRAP_T/2 off the surface, from (origin, direction, inside?) rays."""
    out = []
    for o, d, ins in rays:
        d = V(d); d.normalize()
        p = hit(m, None if ins else panel, o, d)
        n = d if ins else d * -1
        out.append((p + n * (STRAP_T / 2 + 0.6), n))
    return out


def strip(path, width=STRAP_W, align=None, step=5.0, thick=STRAP_T, soft=False):
    """Webbing along a list of (point, surface normal): thin sections laid on the surface every step mm
    along a spline through the points, joined by a ruled loft (a smooth one overshoots on the tight
    turns). width may be a function of the distance along; soft gives rolled, rounded edges."""
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
        wd = width(c.length(us[0], u)) if callable(width) else width
        hw, ht = w * (wd / 2), n * (thick / 2)
        if soft:   # a flattened superellipse: flat faces, round edges
            q = [p + hw * (math.copysign(abs(math.cos(a)) ** 0.25, math.cos(a)))
                 + ht * (math.copysign(abs(math.sin(a)) ** 0.6, math.sin(a)))
                 for a in [2 * math.pi * j / 16 for j in range(16)]]
        else:
            q = [p + hw + ht, p - hw + ht, p - hw - ht, p + hw - ht]
        wires.append(Part.makePolygon(q + [q[0]]))
    return Part.makeLoft(wires, True, True, False)


def belt(m, panel):
    """Round the back at the hip ears' height, each end sewn onto the front of an ear."""
    y = WAIST[1]; zc = centre_z(m, y, 120)
    front = lambda x: (V(x, y, 200), V(0, 0, -1), False)
    rays = [front(AX + WAIST[0] - 14), front(AX + WAIST[0] - 4)]
    rays += [(V(AX, y, zc), V(math.sin(math.radians(5 * k)), 0, math.cos(math.radians(5 * k))), True)
             for k in range(4, 73)]
    rays += [front(AX - WAIST[0] + 4), front(AX - WAIST[0] + 14)]
    path = on_surface(m, panel, rays)
    keep = path[:2] + [p for p in path[2:-2] if abs(p[0].x - AX) > WAIST[0] + 8] + path[-2:]
    return strip(keep, align=[V(0, 1, 0)] * len(keep))


# leg strap waypoints (x out from the toy axis, y, z), between them the shortest path over the skin
# in the leg crease beside the vulva, round the top of the inner thigh into the cheek's fold
LEG_PATH = [(36, -88, -22), (30, -108, -32), (23, -128, -45), (17, -148, -70), (20, -160, -110),
            (40, -160, -140), (65, -130, -190), (76, -40, -215), (70, 40, -200), (66, 80, -195)]


def surface_path(m, targets):
    """Shortest path along the mesh edges through the vertices nearest the targets, as (point, normal)."""
    import heapq
    pts = np.array([(p.x, p.y, p.z) for p in m.Points]); tri = np.array([f.PointIndices for f in m.Facets])
    fn = np.cross(pts[tri[:, 1]] - pts[tri[:, 0]], pts[tri[:, 2]] - pts[tri[:, 0]])
    vn = np.zeros_like(pts)
    for k in range(3):
        np.add.at(vn, tri[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1)[:, None] + 1e-12
    nbr = [set() for _ in pts]
    for t in tri:
        for i in range(3):
            nbr[t[i]].add(t[i - 1]); nbr[t[i - 1]].add(t[i])
    ids = [int(np.argmin(((pts - t) ** 2).sum(1))) for t in targets]
    route = [ids[0]]
    for a, b in zip(ids, ids[1:]):
        dist, prev, q = {a: 0.0}, {}, [(0.0, a)]
        while q:
            d, i = heapq.heappop(q)
            if i == b:
                break
            if d > dist[i]:
                continue
            for j in nbr[i]:
                nd = d + np.linalg.norm(pts[i] - pts[j])
                if nd < dist.get(j, 1e18):
                    dist[j] = nd; prev[j] = i; heapq.heappush(q, (nd, j))
        seg = [b]
        while seg[-1] != a:
            seg.append(prev[seg[-1]])
        route += seg[::-1][1:]
    for i in route:   # normals averaged over an 18 mm patch, so a strap across a crease doesn't flip about
        n = vn[((pts - pts[i]) ** 2).sum(1) < 18.0 ** 2].sum(0); vn[i] = n / np.linalg.norm(n)
    out, last = [], None   # every 20 mm or so, so the spline smooths the zigzag along the edges
    for i in route:
        if last is None or np.linalg.norm(pts[i] - pts[last]) > 28 or i == route[-1]:
            n = V(*vn[i]); out.append((V(*pts[i]) + n * (STRAP_T / 2 + 0.6), n)); last = i
    return out


def leg_strap(m, panel, s):
    """From under the end of the panel's leg lobe round the top of the inner thigh, cupping the cheek in
    its fold, and up the outside of the back to the belt, jock style (Joque, Aslan Jaguar)."""
    path = surface_path(m, [V(AX + s * x, y, z) for x, y, z in [(33, -104, -26)] + LEG_PATH[2:]])
    return strip(path, width=LEG_W, thick=2.6, soft=True)


def buckle(m, panel):
    """A ladder-lock slider on the belt at the right hip."""
    y = WAIST[1]; phi = math.radians(62)
    (p, n), = on_surface(m, panel, [(V(AX, y, centre_z(m, y, 120)), V(math.sin(phi), 0, math.cos(phi)), True)])
    frame = Part.makeBox(40, 32, 4, V(-20, -16, 0)).cut(Part.makeBox(30, 26, 6, V(-15, -13, -1)))
    frame = frame.fuse(Part.makeBox(30, 3, 4, V(-15, -1.5, 0)))
    frame.rotate(V(0, 0, 0), V(0, 1, 0), math.degrees(math.atan2(n.x, n.z)))
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
        if o.TypeId.startswith('Part::') and visible(o) and not o.Shape.isNull() and o.Name not in ('HarnessPins', 'HarnessPad'):
            add(o.Name, o.Shape, like=o,
                colour=(0.62, 0.63, 0.67) if o.Name in ('SnapDDScrew', 'SnapDoubleDouble') else None)
    for n, (shape, col) in PARTS.items():
        add(n, shape, col)
    m = MESH.copy()
    if turn is not None:
        m.transform(turn)
    o = tmp.addObject('Mesh::Feature', 'Body'); o.Mesh = m
    o.ViewObject.ShapeColor = SKIN
    o.ViewObject.CreaseAngle = 80.0
    o.ViewObject.Lighting = 'Two side'
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
    global PARTS, MESH, LEATHER
    pv = App.ParamGet('User parameter:BaseApp/Preferences/View')
    pv.SetBool('ShowNaviCube', False); pv.SetBool('ShowAxisCross', False)
    pv.SetBool('Gradient', True); pv.SetBool('Simple', False)
    rgb = lambda r, g, b: (int(r * 255) << 24) | (int(g * 255) << 16) | (int(b * 255) << 8)
    pv.SetUnsigned('BackgroundColor2', rgb(0.93, 0.93, 0.95))
    pv.SetUnsigned('BackgroundColor3', rgb(0.70, 0.71, 0.75))

    src = App.openDocument(SOURCE)
    MESH = body()
    panel = draped(MESH, src.getObject('HarnessPad').Shape)
    LEATHER = tuple(src.getObject('HarnessPad').ViewObject.ShapeColor[:3])   # leg straps cut with the panel
    PARTS = {
        'Panel': (panel, LEATHER),
        'WaistBelt': (belt(MESH, panel), WEBBING),
        'LegStraps': (Part.makeCompound([leg_strap(MESH, panel, s) for s in (-1, 1)]), LEATHER),
        'Buckle': (buckle(MESH, panel), HARDWARE),
    }
    pic = 'Harness-Mount-Ring-On-Body'
    shoot(src, pic + '-Front.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)))
    shoot(src, pic + '-Side.png', App.Rotation(V(0, 1, 0), 90).multiply(App.Rotation(V(1, 0, 0), -4)))
    shoot(src, pic + '-Low.png', App.Rotation(V(0, 1, 0), 35).multiply(App.Rotation(V(1, 0, 0), 30)))
    shoot(src, pic + '-Back.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)), turned=True)
    App.closeDocument(src.Name)


main()
