"""Cloth sim of the harness on the reference body, to find where the straps want to leave the print.

Run headless from the repository root (needs numpy and scipy in FreeCAD's Python):

    freecadcmd hardware/cad/harness-mount/cloth_sim.py

Position-based dynamics in device coordinates (as render_on_body.py, mm):
- the panel is the flat pattern (shell outline, ring hole) as a triangle mesh: leather barely stretches,
  bends stiffly, and drapes under gravity onto the body. Under the core it is screwed down, so pinned.
- the straps are chains that shrink until taut, so they lie in their natural, shortest line over the
  body and the panel. The belt's buckle is pinned at the back, at hip height; each leg strap's back end
  rides on the belt where its loop goes round it. The front end of every strap slides freely along the
  line of the slot bars round the core and settles where the strap pulls square to it: where the slot
  belongs (SIM_FREE=1). Otherwise the ends are held at the builder's slot bars, for the renders.

It writes harness-sim.json (or harness-sim-free.json) beside this script (the panel mesh and strap paths, which render_on_body.py
draws) and prints where the four strap ends settled."""

import json, math, os, sys
import numpy as np
from scipy.spatial import cKDTree, Delaunay
import FreeCAD as App
import Mesh

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['HARNESS_NO_MAIN'] = '1'
_f = os.path.join(HERE, 'build_harness_mount.py')
B = {'__file__': _f, '__name__': 'harness_builder'}
exec(compile(open(_f).read(), _f, 'exec'), B)
SB, P, H = B['SB'], B['P'], B['H']
SB.P.clear(); SB.P.update(SB.BASE); B['MODE'] = 'ring'; B['install']()

# as render_on_body.py
AX, AY = B['axis']()
Z_REAR, PAD_T = SB.z_rear(), H['PadT']
TILT, BODY_AXIS = 14.0, (-8.0, 117.0)
BODY = os.path.join(HERE, 'reference', 'body-female-lower.obj')
STRAP_T, STRAP_W = 1.6, 25.4
KEEP_OUT_X, KEEP_OUT_Y, KEEP_OUT_Z = 28.0, -90.0, -85.0   # no straps within X of the centre line, below Y and in
                                       # front of Z: the vulva, or a chastity cage. The mons ends at about y -90;
                                       # behind z -85 is the perineum, where the leg straps may cross to the buttock crease
FREE = bool(os.environ.get('SIM_FREE'))
OUT = os.path.join(HERE, 'harness-sim-free.json' if FREE else 'harness-sim.json')

H_PANEL = 5.0          # panel mesh spacing
SEG = 5.0              # strap node spacing
SHRINK = 0.9           # strap rest length per segment, as a fraction of SEG: keeps them taut
WAIST_Y = 95.0         # belt round the back at this device height (buckle pinned there)
LEG_BELT_X = 120.0     # leg straps fixed to the belt this far out from the centre back, past the cheeks
LEG_PATH = [(30, -108, -32), (23, -128, -45), (17, -148, -70), (20, -160, -110),
            (40, -160, -140), (65, -130, -190)]   # start route between the legs, as render_on_body.py
BAR = B['SLOT_U'][1] + H['SlotT'] + H['SlotBarW'] / 2   # slot bar centre past the core edge
GRAVITY = 0.05         # of g on the panel: leather on foam is light for how stiff it is, and the straps hold it
PRESS = 2000.0         # mm/s2 pressing the loose panel toward the skin
FRICTION = 0.9         # of the panel's slip along the skin taken out each step
STRAP_FRICTION = float(os.environ.get('SIM_STRAP_FRICTION', 0.5))   # the straps' (0: they slide to the shortest line)
STEPS, ITERS, DT = int(os.environ.get("SIM_STEPS", 300)), 12, 0.01


# ---------------------------------------------------------------- body

def body():
    m = Mesh.Mesh(BODY)
    y0, z0 = BODY_AXIS
    m.translate(0, -y0, -z0)
    m.rotate(math.radians(-TILT), 0, 0)
    m.translate(AX, AY, Z_REAR - PAD_T - 0.3)
    pts = np.array([(p.x, p.y, p.z) for p in m.Points])
    tri = np.array([f.PointIndices for f in m.Facets])
    return pts, tri


def samples(pts, tri, n=150000, seed=1):
    """Points spread evenly over the skin with their facet normals, for nearest-point collisions."""
    a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    fn = np.cross(b - a, c - a); area = np.linalg.norm(fn, axis=1) / 2
    fn = fn / (np.linalg.norm(fn, axis=1)[:, None] + 1e-12)
    rng = np.random.default_rng(seed)
    k = rng.choice(len(tri), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n); flip = u + v > 1; u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    sp = a[k] + (b[k] - a[k]) * u[:, None] + (c[k] - a[k]) * v[:, None]
    return sp, fn[k]


def ray_hit(pts, tri, o, d):
    """Nearest crossing of the ray with the mesh past o (Moller-Trumbore over every facet)."""
    a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    e1, e2 = b - a, c - a
    pv = np.cross(d, e2); det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-12; inv = 1.0 / np.where(ok, det, 1.0)
    tv = o - a; u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, e1); v = (qv * d).sum(1) * inv; t = (e2 * qv).sum(1) * inv
    t = t[ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-3)]
    return o + d * t.min() if len(t) else None


# ---------------------------------------------------------------- panel

def inside(poly, q):
    """Even-odd point in polygon, vectorised over q (N x 2)."""
    x, y = q[:, 0][:, None], q[:, 1][:, None]
    x0, y0 = poly[:, 0][None], poly[:, 1][None]
    x1, y1 = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0)
    return cross.sum(1) % 2 == 1


def seg_dist(poly, q):
    """Distance from each q to the polygon's edges."""
    a, b = poly, np.roll(poly, -1, axis=0)
    ab = b - a
    t = np.clip(((q[:, None] - a[None]) * ab[None]).sum(2) / ((ab * ab).sum(1)[None] + 1e-12), 0, 1)
    c = a[None] + ab[None] * t[..., None]
    return np.linalg.norm(q[:, None] - c, axis=2).min(1)


def panel_mesh():
    """The flat pattern as triangles: lattice inside, points round every edge."""
    pad = B['pad']()
    rear = max(pad.Faces, key=lambda f: f.Area if f.normalAt(*f.Surface.parameter(f.CenterOfMass)).z < -0.5 else 0)
    outline = np.array([(q.x, q.y) for q in rear.OuterWire.discretize(Distance=H_PANEL)])[:-1]
    r = H['PadBaseHole'] / 2
    hole = np.array([(AX + r * math.cos(t), AY + r * math.sin(t))
                     for t in np.linspace(0, 2 * math.pi, int(2 * math.pi * r / H_PANEL), endpoint=False)])
    bb0, bb1 = outline.min(0), outline.max(0)
    xs = np.arange(bb0[0], bb1[0], H_PANEL); ys = np.arange(bb0[1], bb1[1], H_PANEL * math.sqrt(3) / 2)
    grid = np.array([(x + (j % 2) * H_PANEL / 2, y) for j, y in enumerate(ys) for x in xs])
    keep = inside(outline, grid) & (seg_dist(outline, grid) > 0.6 * H_PANEL) & \
        (np.linalg.norm(grid - (AX, AY), axis=1) > r + 0.6 * H_PANEL)
    q = np.vstack([outline, hole, grid[keep]])
    tri = Delaunay(q).simplices
    c = q[tri].mean(1)
    ok = inside(outline, c) & (np.linalg.norm(c - (AX, AY), axis=1) > r)
    e = q[tri[:, 1]] - q[tri[:, 0]]; f = q[tri[:, 2]] - q[tri[:, 0]]
    ok &= np.abs(e[:, 0] * f[:, 1] - e[:, 1] * f[:, 0]) > 0.05 * H_PANEL ** 2   # no slivers
    tri = tri[ok]
    core = np.array([(v.x, v.y) for v in B['core_face']().OuterWire.discretize(Distance=2.0)])
    pinned = inside(core, q) & (seg_dist(core, q) > 1.0)
    x3 = np.array([(x, y, B['rear_z'](x, y) - PAD_T / 2) for x, y in q])
    return q, tri, x3, pinned


def edges_of(tri):
    e = np.sort(np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
    return np.unique(e, axis=0)


def bend_pairs(tri):
    """Opposite corners of each pair of triangles sharing an edge: a distance there resists folding."""
    owner = {}
    pairs = []
    for t in tri:
        for k in range(3):
            a, b, c = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
            key = (min(a, b), max(a, b))
            if key in owner:
                pairs.append((owner[key], c))
            else:
                owner[key] = c
    return np.array(pairs)


def vertex_normals(x, tri):
    fn = np.cross(x[tri[:, 1]] - x[tri[:, 0]], x[tri[:, 2]] - x[tri[:, 0]])
    vn = np.zeros_like(x)
    for k in range(3):
        np.add.at(vn, tri[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1)[:, None] + 1e-12
    return vn * np.sign(vn[:, 2].sum())   # away from the body (+Z on average)


# ---------------------------------------------------------------- straps

def resample(path, step=SEG):
    path = np.asarray(path, float)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    s = np.linspace(0, d[-1], max(2, int(d[-1] / step) + 1))
    return np.stack([np.interp(s, d, path[:, k]) for k in range(3)], 1)


def bar_line():
    """Where the slot bars can go: the core outline pushed out to the bar centre, at the bar's height."""
    f = B['core_face']().makeOffset2D(BAR, join=0)
    pts = [(q.x, q.y) for q in f.OuterWire.discretize(Distance=1.0)]
    return np.array([(x, y, B['rear_z'](x, y) + H['SlotTabT'] - 1.5) for x, y in pts])


def slide(p, line, mask):
    """The point on the allowed stretch of the bar line nearest p: a strap end with nothing to hold it
    there but the line, so it sits square to the strap's pull."""
    a, b = line[:-1][mask[:-1] & mask[1:]], line[1:][mask[:-1] & mask[1:]]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / ((ab * ab).sum(1) + 1e-12), 0, 1)
    c = a + ab * t[:, None]
    return c[np.argmin(np.linalg.norm(c - p, axis=1))]


# ---------------------------------------------------------------- solver

def distance(x, w, e, rest, k):
    """One Jacobi pass of distance constraints; w is inverse mass (0 = pinned)."""
    d = x[e[:, 1]] - x[e[:, 0]]
    L = np.linalg.norm(d, axis=1) + 1e-12
    wsum = w[e[:, 0]] + w[e[:, 1]] + 1e-12
    c = ((L - rest) / (L * wsum) * k)[:, None] * d
    dx = np.zeros_like(x); n = np.zeros(len(x))
    np.add.at(dx, e[:, 0], c * w[e[:, 0]][:, None]); np.add.at(dx, e[:, 1], -c * w[e[:, 1]][:, None])
    np.add.at(n, e[:, 0], 1); np.add.at(n, e[:, 1], 1)
    x += 1.5 * dx / np.maximum(n, 1)[:, None]


def collide(x, w, tree, sp, sn, off):
    d, i = tree.query(x)
    s = ((x - sp[i]) * sn[i]).sum(1)
    pen = np.where(w > 0, off - s, 0)
    hit = pen > 0
    x[hit] += sn[i][hit] * pen[hit][:, None]
    return hit


def keep_out(x, mask):
    """No strap over the vulva, or a caged penis: below KEEP_OUT_Y, strap centres stay KEEP_OUT_X plus half
    a strap width out from the centre line, in front of KEEP_OUT_Z."""
    lim = KEEP_OUT_X + STRAP_W / 2
    dx = x[:, 0] - AX
    bad = mask & (x[:, 1] < KEEP_OUT_Y) & (x[:, 2] > KEEP_OUT_Z) & (np.abs(dx) < lim)
    x[bad, 0] = AX + np.where(dx[bad] >= 0, lim, -lim)


def ribbon_edges(x, chains, w, tree, sp, sn):
    """The strap is 25 mm wide, not a line: where either edge would sink into the skin (across a crease),
    lift the strap there by as much."""
    off = STRAP_T / 2 + 0.3
    for c in chains:
        p = x[c]
        t = np.gradient(p, axis=0); t /= np.linalg.norm(t, axis=1)[:, None] + 1e-12
        d, i = tree.query(p); n = sn[i]
        b = np.cross(t, n); b /= np.linalg.norm(b, axis=1)[:, None] + 1e-12
        lift = np.zeros(len(c))
        for sgn in (1, -1):
            e = p + b * (sgn * STRAP_W / 2)
            d, j = tree.query(e)
            lift = np.maximum(lift, off - ((e - sp[j]) * sn[j]).sum(1))
        lift[w[c] == 0] = 0
        x[c] += n * np.maximum(lift, 0)[:, None]


def ribbon_normals(x, c, tree, sn):
    d, i = tree.query(x[c])
    return sn[i]


def main():
    pts, tri = body()
    sp, sn = samples(pts, tri)
    front = np.argmin(np.linalg.norm(sp - (AX, AY, Z_REAR), axis=1))
    if sn[front, 2] < 0:
        sn = -sn
    tree = cKDTree(sp)
    g = App.Matrix(); g.rotateX(math.radians(-TILT)); g = g.multVec(V(0, -9810 * GRAVITY, 0)); grav = np.array([g.x, g.y, g.z])

    # panel
    q2, ptri, px, pin = panel_mesh()
    pe = edges_of(ptri); pb = bend_pairs(ptri)
    pe_rest = np.linalg.norm(q2[pe[:, 1]] - q2[pe[:, 0]], axis=1)    # the flat pattern's lengths
    pb_rest = np.linalg.norm(q2[pb[:, 1]] - q2[pb[:, 0]], axis=1)
    pw = np.where(pin, 0.0, 1.0)
    print('SIM panel: %d points, %d triangles, %d pinned under the core' % (len(px), len(ptri), pin.sum()))

    # belt: rays round the body at WAIST_Y from the right hip, round the back, to the left hip
    line = bar_line()
    zs = pts[np.abs(pts[:, 1] - WAIST_Y) < 8][:, 2]; zc = (zs.min() + zs.max()) / 2
    ring = []
    for a in np.arange(70, 291, 3):
        d = np.array([math.sin(math.radians(a)), 0, math.cos(math.radians(a))])
        h = ray_hit(pts, tri, np.array([AX, WAIST_Y, zc]), d)
        if h is not None:
            ring.append(h + d * 2)
    ends = [line[np.argmin(np.linalg.norm(line - (AX + s * 50, WAIST_Y, 0) * np.array([1, 1, 0]), axis=1))] for s in (1, -1)]
    waist = resample([ends[0]] + ring + [ends[1]])
    back = int(np.argmin(np.abs(waist[:, 0] - AX) + np.where(waist[:, 2] < zc, 0, 1e3)))
    # leg straps: from below the ring between the legs to the belt
    legs, leg_belt = [], []
    for s in (1, -1):
        start = line[np.argmin(np.linalg.norm(line[:, :2] - (AX + s * 20, AY - 40), axis=1))]
        j = int(np.argmin(np.abs(waist[:, 0] - (AX + s * LEG_BELT_X)) + np.where(waist[:, 2] < zc, 0, 1e3)))
        leg_belt.append(j)
        legs.append(resample([start] + [(AX + s * x, y, z) for x, y, z in LEG_PATH] + [waist[j]]))

    # one particle system: panel, belt, legs
    parts = [px, waist] + legs
    x = np.vstack(parts); off = np.cumsum([0] + [len(p) for p in parts])
    w = np.concatenate([pw, np.ones(len(x) - len(px))])
    w[off[1] + back] = 0                                       # buckle at the back
    strap = np.zeros(len(x), bool); strap[off[1]:] = True
    chains = [np.arange(off[k], off[k + 1]) for k in range(1, len(parts))]
    se = np.vstack([np.stack([c[:-1], c[1:]], 1) for c in chains])
    sb = np.vstack([np.stack([c[:-2], c[2:]], 1) for c in chains])   # straps resist kinking a little
    E = np.vstack([pe, se]); R = np.concatenate([pe_rest, np.full(len(se), SEG * SHRINK)])
    K = np.concatenate([np.full(len(pe), 1.0), np.full(len(se), 0.6)])
    Bd = np.vstack([pb, sb]); BR = np.concatenate([pb_rest, np.full(len(sb), 2 * SEG * SHRINK)])
    BK = np.concatenate([np.full(len(pb), 0.5), np.full(len(sb), 0.05)])
    offs = np.where(strap, STRAP_T / 2 + 0.3, PAD_T / 2)
    left = (line[:, 0] < AX)
    masks = {'waist': [(line[:, 1] > 30) & ~left, (line[:, 1] > 30) & left],
             'leg': [(line[:, 1] < AY - 15) & ~left, (line[:, 1] < AY - 15) & left]}
    endpoints = [(chains[0][0], masks['waist'][0]), (chains[0][-1], masks['waist'][1]),
                 (chains[1][0], masks['leg'][0]), (chains[2][0], masks['leg'][1])]
    bars = B['slot_bars']()   # right waist, right leg, left waist, left leg
    for (i, _), (b, _) in zip(endpoints, [bars[0], bars[2], bars[1], bars[3]]):
        w[i] = 0   # held at the bar, or moved by sliding only
        if not FREE:
            x[i] = (b.x, b.y, b.z - 1.5)
    for c in chains[1:]:
        w[c[-1]] = 0
    gravity = np.where(strap[:, None] | (w[:, None] == 0), 0, grav[None])   # pinned points stay put
    pidx = np.arange(len(px)); ptree_every = 4

    v = np.zeros_like(x)
    for step in range(STEPS):
        x0 = x.copy()
        d, i = tree.query(x)   # the straps and the wearer's movement press the loose panel onto the skin
        v += (gravity - sn[i] * PRESS * (~strap & (w > 0))[:, None]) * DT
        x += v * DT
        if step % ptree_every == 0:
            pn = vertex_normals(x[pidx], ptri); ptree = cKDTree(x[pidx])
        for it in range(ITERS):
            distance(x, w, E, R, K)
            distance(x, w, Bd, BR, BK)
            for i, mask in endpoints if FREE else []:   # strap ends slide on the bar line to wherever they're pulled
                pull = x[i + (1 if i in (chains[0][0], chains[1][0], chains[2][0]) else -1)]
                x[i] = slide(pull, line, mask)
            for k in range(2):   # each leg strap's loop sits on the belt
                x[chains[1 + k][-1]] = x[chains[0][leg_belt[k]]]
            keep_out(x, strap & (w > 0))
            touch = collide(x, w, tree, sp, sn, offs)
            ribbon_edges(x, chains, w, tree, sp, sn)
            # straps over the panel ride on its front
            sidx = np.where(strap)[0]
            d, i = ptree.query(x[sidx])
            r = x[sidx] - x[pidx][i]
            nrm = pn[i]; s = (r * nrm).sum(1)
            tang = np.linalg.norm(r - nrm * s[:, None], axis=1)
            need = PAD_T / 2 + STRAP_T / 2 + 0.2
            hit = (tang < H_PANEL) & (s < need) & (s > -PAD_T)
            push = (need - s)[hit][:, None] * nrm[hit]
            ws, wp = w[sidx][hit], w[pidx][i[hit]]
            tot = ws + wp + 1e-12
            x[sidx[hit]] += push * (ws / tot)[:, None]
            np.add.at(x, pidx[i[hit]], -push * (wp / tot)[:, None])
        # friction: leather on skin holds where it's pressed, so drop most of the sliding along the skin
        d, i = tree.query(x); n = sn[i]
        dx = x - x0; slip = dx - n * (dx * n).sum(1)[:, None]
        x[touch] -= slip[touch] * np.where(strap, STRAP_FRICTION, FRICTION)[touch][:, None]
        v = (x - x0) / DT * 0.96
        v[w == 0] = 0
        if step % 100 == 0 or step == STEPS - 1:
            msg = ', '.join('(%.1f, %.1f)' % (x[i][0] - AX, x[i][1]) for i, _ in endpoints)
            print('SIM step %d: strap ends %s' % (step, msg)); sys.stdout.flush()

    res = {'panel': {'points': x[pidx].round(3).tolist(), 'triangles': ptri.tolist(), 'flat': q2.round(3).tolist()},
           'waist': x[chains[0]].round(3).tolist(), 'legs': [x[c].round(3).tolist() for c in chains[1:]],
           'waist_n': ribbon_normals(x, chains[0], tree, sn).round(4).tolist(),
           'legs_n': [ribbon_normals(x, c, tree, sn).round(4).tolist() for c in chains[1:]],
           'buckle': int(back), 'leg_belt': [int(j) for j in leg_belt],
           'ends': [{'x': float(x[i][0] - AX), 'y': float(x[i][1]), 'z': float(x[i][2]),
                     'dir': [float(t) for t in (x[i + (1 if k != 1 else -1)] - x[i])[:2] / np.linalg.norm((x[i + (1 if k != 1 else -1)] - x[i])[:2])]}
                    for k, (i, _) in enumerate(endpoints)]}
    with open(OUT, 'w') as f:
        json.dump(res, f)
    for k, c in enumerate(chains):
        L = np.linalg.norm(np.diff(x[c], axis=0), axis=1).sum()
        print('SIM strap %d length %.0f mm' % (k, L))
    for e in res['ends']:
        print('SIM END x %.1f y %.1f, pulling (%.2f, %.2f)' % (e['x'], e['y'], e['dir'][0], e['dir'][1]))


main()
