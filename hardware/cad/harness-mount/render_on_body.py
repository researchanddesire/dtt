"""Renders the O-ring harness mount worn on a reference body, with its straps and hardware as BUILD.md lists. Run under the FreeCAD GUI after build_harness_mount.py:

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
STRAP_W, STRAP_T = 25.4, 1.6

SKIN = (0.80, 0.74, 0.69)     # plain mannequin
WEBBING = (0.07, 0.07, 0.08)
DIFFUSER = (0.96, 0.96, 0.94)   # printed white, over the LEDs


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


def draped(m, pad):
    """The soft panel as it lies on the body: the builder's panel outline and holes, but its back on the
    skin instead of on the builder's fitted curve (leather and foam follow the body)."""
    rear = max(pad.Faces, key=lambda f: f.Area if f.normalAt(*f.Surface.parameter(f.CenterOfMass)).z < -0.5 else 0)
    plan = plan_prism(rear.OuterWire)
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


NORMALS = {}


def normals(m):
    """Mesh points and vertex normals (area weighted)."""
    if id(m) not in NORMALS:
        pts = np.array([(p.x, p.y, p.z) for p in m.Points]); tri = np.array([f.PointIndices for f in m.Facets])
        fn = np.cross(pts[tri[:, 1]] - pts[tri[:, 0]], pts[tri[:, 2]] - pts[tri[:, 0]])
        vn = np.zeros_like(pts)
        for k in range(3):
            np.add.at(vn, tri[:, k], fn)
        NORMALS[id(m)] = pts, vn / (np.linalg.norm(vn, axis=1)[:, None] + 1e-12), tri
    return NORMALS[id(m)]


def normal_at(m, p, r=18.0):
    """Skin normal near p, averaged over a patch, so a strap across a crease doesn't flip about."""
    pts, vn, _ = normals(m)
    n = vn[((pts - np.array(tuple(p))) ** 2).sum(1) < r * r].sum(0)
    return V(*(n / np.linalg.norm(n)))


def skin(m, x, y, lift=STRAP_T / 2 + 0.6, panel=None):
    """(point, normal) on the front of the body (or the panel) at x, y, lifted off it."""
    p = hit(m, panel, V(x, y, 300), V(0, 0, -1))
    n = normal_at(m, p)
    return p + n * lift, n


def surface_path(m, targets):
    """Shortest path along the mesh edges through the vertices nearest the targets, as (point, normal)."""
    import heapq
    pts, vn, tri = normals(m)
    if 'nbr' not in NORMALS:
        nbr = [set() for _ in pts]
        for t in tri:
            for i in range(3):
                nbr[t[i]].add(t[i - 1]); nbr[t[i - 1]].add(t[i])
        NORMALS['nbr'] = nbr
    nbr = NORMALS['nbr']
    ids = [int(np.argmin(((pts - np.array(tuple(t))) ** 2).sum(1))) for t in targets]
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
    out, last = [], None   # every 28 mm or so, so the spline smooths the zigzag along the edges
    for i in route:
        if last is None or np.linalg.norm(pts[i] - pts[last]) > 28 or i == route[-1]:
            q = V(*pts[i]); n = normal_at(m, q); out.append((q + n * (STRAP_T / 2 + 0.6), n)); last = i
    return out


def to_skin(m, q, lift):
    """The nearest point on the skin to q, lifted off it, and the normal there."""
    pts, _, _ = normals(m)
    v = V(*pts[int(np.argmin(((pts - np.array(tuple(q))) ** 2).sum(1)))])
    n = normal_at(m, v)
    return v + n * lift, n


def length(path):
    return sum((b[0] - a[0]).Length for a, b in zip(path, path[1:]))


def along(path, d):
    """(point, tangent, normal) at distance d along a (point, normal) path."""
    for a, b in zip(path, path[1:]):
        seg = (b[0] - a[0]).Length
        if d <= seg or b is path[-1]:
            f = min(d / seg, 1.0); t = b[0] - a[0]; t.normalize()
            n = a[1] * (1 - f) + b[1] * f; n.normalize()
            return a[0] + (b[0] - a[0]) * f, t, n
        d -= seg


def part(path, d0, d1, lift=0.0):
    """The stretch of a path between two distances along it, lifted off it (a strap end doubled back)."""
    total = length(path); d1 = min(d1, total)
    k = max(2, int((d1 - d0) / 5))
    out = []
    for i in range(k + 1):
        p, t, n = along(path, d0 + (d1 - d0) * i / k)
        out.append((p + n * lift, n))
    return out


# ---------------------------------------------------------------- hardware
# Each is built in a local frame: X across the strap, Y along it, Z out of the body.

METAL = (0.70, 0.71, 0.74)
PLASTIC = (0.10, 0.10, 0.11)
ROD = 1.75                    # 3.5 mm wire


def tri_glide():
    """1 in slide (tri-glide), centred."""
    f = Part.makeBox(33, 24, 3, V(-16.5, -12, -1.5))
    for y in (-9.5, 2.5):
        f = f.cut(Part.makeBox(27, 7, 5, V(-13.5, y, -3)))
    return f


def side_release():
    """1 in side-release buckle, centred on the join: socket toward +Y, plug toward -Y."""
    sock = Part.makeBox(31, 30, 9, V(-15.5, 0, -2))
    plug = Part.makeBox(27, 22, 6, V(-13.5, -22, -1)).fuse(Part.makeBox(33, 6, 6, V(-16.5, -22, -1)))
    out = []
    for b in (sock, plug):
        try:
            b = b.makeFillet(1.5, b.Edges)
        except Exception:
            pass
        out.append(b)
    return Part.makeCompound(out)


def place(shape, p, t, n):
    """Local X across, Y along t, Z along n, origin at p."""
    z = V(n); z.normalize()
    y = t - z * t.dot(z); y.normalize()
    x = y.cross(z)
    mtx = App.Matrix(x.x, y.x, z.x, p.x, x.y, y.y, z.y, p.y, x.z, y.z, z.z, p.z, 0, 0, 0, 1)
    s = shape.copy(); s.transformShape(mtx)
    return s


# ---------------------------------------------------------------- the rig
# Panel: leather shell, foam, lining, edge stitched; plain, no hardware on it.
# Straps start at four slots printed on the core, over the panel front, so the foam is between them and the
# skin. Waist: two straps, each under its bar, up through the slot and back to a slide on itself, meeting
# at a side-release buckle at the back.
# Legs: 1 in elastic, sewn round the lower bar, down the leg crease, under the cheek, up to a slide and round
# the belt in a sewn loop that slides along it, jockstrap style.

WAIST_BAR = (38.0, 95.0, 1.0, 0.0)     # strap bars on the printed core: (x out from the axis, y, direction
LEG_BAR = (20.0, -70.8, 0.0, -1.0)    # out); as slot_bars() in the builder prints them
BACK_RING_X = 66.0                    # where the leg straps loop round the belt, x out from the centre back
LEG_PATH = [(30, -108, -32), (23, -128, -45), (17, -148, -70), (20, -160, -110),
            (40, -160, -140), (65, -130, -190), (76, -40, -215)]
LENGTHS = {}


def slot_strap(m, panel, core, s, bar, reach):
    """A strap from its bar on the core: up out of the slot, over the bar and out along the panel front
    to reach mm past the bar. Returns the path and its end (point, t, n)."""
    x, y, dx, dy = bar
    d = V(s * dx, dy, 0); d.normalize()
    top = hit(m, core.fuse(panel), V(AX + s * x, y, 300), V(0, 0, -1))
    n = normal_at(m, top)
    lift = STRAP_T / 2 + 0.3
    path = [(top - d * 7 - n * 2, n), (top - d * 3 + n * lift, n), (top + n * lift, n), (top + d * 3 + n * lift, n)]
    for u in range(9, int(reach) + 1, 5):
        q = V(AX + s * x, y, 0) + d * u
        p, nn = skin(m, q.x, q.y, lift + 0.3, panel)
        path.append((p, nn))
    t = path[-1][0] - path[-2][0]; t.normalize()
    return path, (path[-1][0], t, path[-1][1])


def belt(m, panel, tips):
    """Round the back from one hip slot to the other, at the slots' height."""
    y = WAIST_BAR[1]; zc = centre_z(m, y, 120)
    rays = [(V(AX, y, zc), V(math.sin(math.radians(a)), 0, math.cos(math.radians(a))), True)
            for a in range(60, 301, 4)]
    path = [q for q in on_surface(m, None, rays) if abs(q[0].x - AX) > abs(tips[1][0].x - AX) + 6 or q[0].z < zc]
    path.sort(key=lambda q: math.atan2(q[0].x - AX, q[0].z - zc) % (2 * math.pi))
    return path


def rig(m, panel, core):
    """All the straps and hardware, as {name: (shape, colour)}; strap lengths go to LENGTHS."""
    metal, black, plastic = [], [], []
    hips = [slot_strap(m, panel, core, s, WAIST_BAR, 58) for s in (1, -1)]
    legs = [slot_strap(m, panel, core, s, LEG_BAR, 14) for s in (1, -1)]
    bp = hips[0][0] + belt(m, panel, [hips[0][1], hips[1][1]]) + hips[1][0][::-1]
    total = length(bp)
    black.append(strip(bp))
    for d0, d1, sign in ((4, 74, 1), (total - 74, total - 4, -1)):          # ends back through a slide
        tail = part(bp, d0, d1, STRAP_T + 0.2)
        black.append(strip(tail))
        p, t, n = along(bp, d0 + 52 if sign > 0 else d1 - 52)
        metal.append(place(tri_glide(), p + n * (2 * STRAP_T + 1.0), t, n))
    zc = centre_z(m, WAIST_BAR[1], 120)
    mid = min(range(len(bp)), key=lambda i: abs(bp[i][0].x - AX) + (0 if bp[i][0].z < zc else 1e3))
    dm = length(bp[:mid + 1])
    p, t, n = along(bp, dm)
    plastic.append(place(side_release(), p + n * 2.5, t, n))
    LENGTHS['waist (each side, slot to buckle, + 150 to adjust)'] = round(dm + 150)
    for k, s in enumerate((1, -1)):
        i = min(range(len(bp)), key=lambda i: abs(bp[i][0].x - (AX + s * BACK_RING_X)) + (0 if bp[i][0].z < zc else 1e3))
        p, t, n = along(bp, length(bp[:i + 1]))
        up = V(0, 1, 0) - n * n.y; up.normalize()
        # the leg strap, from its slot round the leg, up through its slide and looped round the belt
        front, (tip, tt, tn) = legs[k]
        under, _ = to_skin(m, p - up * 20 - n * 2, 0.0)
        back = surface_path(m, [V(AX + s * x, y, z) for x, y, z in LEG_PATH] + [under])
        over = STRAP_T + 0.6                                             # on the belt's outer face
        lp = front + back + [(p - up * 13 + n * over, n), (p + n * over, n),
                                                  (p + up * 11 + n * over, n), (p + up * 15 + n * 0.2, up)]
        black.append(strip(lp))
        L = length(lp)
        black.append(strip(part(lp, 4, 30, STRAP_T + 0.2)))                 # sewn back on itself at the slot
        black.append(strip(part(lp, L - 140, L - 50, STRAP_T + 0.2)))     # doubled back through the slide
        p2, t2, n2 = along(lp, L - 110)
        metal.append(place(tri_glide(), p2 + n2 * (2 * STRAP_T + 1.0), t2, n2))
        LENGTHS['leg strap (each, elastic, both loops + 120 to adjust)'] = round(L + 32 + 60 + 120)
    return {'Webbing': (Part.makeCompound(black), WEBBING),
            'Hardware': (Part.makeCompound(metal), METAL), 'Buckle': (Part.makeCompound(plastic), PLASTIC)}


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
        if (o.TypeId.startswith('Part::') and visible(o) or o.Name == 'Diffuser') and not o.Shape.isNull() \
                and o.Name not in ('HarnessPins', 'HarnessPad'):
            add(o.Name, o.Shape, like=o, colour=DIFFUSER if o.Name == 'Diffuser' else
                (0.62, 0.63, 0.67) if o.Name in ('SnapDDScrew', 'SnapDoubleDouble') else None)
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


def shoot(src, fname, cam, turned=False, focus=None):
    turn = None
    if turned:
        turn = App.Placement(V(0, 0, 0), App.Rotation(V(0, 1, 0), 180), V(AX, 0, -130)).toMatrix()
    tmp = scene(src, turn)
    Gui.ActiveDocument = Gui.getDocument(tmp.Name)
    view = Gui.getDocument(tmp.Name).ActiveView
    view.setCameraOrientation(cam); view.fitAll(); Gui.updateGui(); view.fitAll(); Gui.updateGui()
    if focus is not None:   # (centre, height): a close-up
        from pivy import coin
        node = view.getCameraNode(); c, h = focus
        back = node.orientation.getValue().multVec(coin.SbVec3f(0, 0, 1))
        node.position.setValue(coin.SbVec3f(c.x, c.y, c.z) + back * 600); node.height.setValue(h)
        node.focalDistance.setValue(600); Gui.updateGui()
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
    LEATHER = tuple(src.getObject('HarnessPad').ViewObject.ShapeColor[:3])
    PARTS = {'Panel': (panel, LEATHER)}
    PARTS.update(rig(MESH, panel, src.getObject('SnapBackplatePrinted').Shape))
    with open(os.environ.get('HARNESS_LENGTHS', os.devnull), 'w') as f:   # for the cut list
        f.writelines('%s: %d mm\n' % kv for kv in LENGTHS.items())
    pic = 'Harness-Mount-Ring-On-Body'
    shoot(src, pic + '-Front.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)))
    shoot(src, pic + '-Side.png', App.Rotation(V(0, 1, 0), 90).multiply(App.Rotation(V(1, 0, 0), -4)))
    shoot(src, pic + '-Low.png', App.Rotation(V(0, 1, 0), 35).multiply(App.Rotation(V(1, 0, 0), 30)))
    shoot(src, pic + '-Detail.png', App.Rotation(V(0, 1, 0), 22).multiply(App.Rotation(V(1, 0, 0), 14)),
          focus=(V(AX, 25, 0), 250))
    shoot(src, pic + '-Back.png', App.Rotation(V(0, 1, 0), 28).multiply(App.Rotation(V(1, 0, 0), -8)), turned=True)
    App.closeDocument(src.Name)


main()
