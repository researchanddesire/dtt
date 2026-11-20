#!/usr/bin/env python3
"""Route dtt_v2.kicad_pcb: negotiated-congestion grid A* on both layers.

Run after build_dtt_v2.py with KiCad 7+ Python, numpy, scipy and a C compiler:
    python3 route_dtt_v2.py
GND is routed last like any other net, then the pours on both layers are
stitched together with vias.
    python3 route_dtt_v2.py --reuse   # redo the post-processing on the last paths
"""
import ctypes
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
PCB = HERE / 'dtt_v2.kicad_pcb'

RES = 0.05                 # grid pitch, mm
PAD = 1.0                  # grid margin around the board, mm
MARGIN = 0.04              # extra clearance for grid rounding, mm
CLEARANCE = 0.2
EDGE_CLEARANCE = 0.3
HOLE_CLEARANCE = 0.25
VIA_D, VIA_DRILL = 0.6, 0.3
COST = dict(step=10, diag=14, via=120, turn=6, back=4)   # back: per-cell cost on B.Cu
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
NARROW = 0.2               # default track width; power nets neck to it near pads
NECK = 1.0                 # how far from a pad a power track may neck down, mm
ROUNDS = 40                # negotiation rounds
PRES0, PRES_GROW, HIST = 4, 1.5, 6   # congestion costs per cell
STITCH = 2.5               # GND stitching via pitch, mm


def load_astar():
    lib = HERE / 'build' / 'libastar.so'
    src = HERE / 'astar.c'
    if not lib.exists() or lib.stat().st_mtime < src.stat().st_mtime:
        lib.parent.mkdir(exist_ok=True)
        subprocess.run(['cc', '-O2', '-shared', '-fPIC', '-o', str(lib), str(src)], check=True)
    so = ctypes.CDLL(str(lib))
    so.route.restype = ctypes.c_int
    return so


def mm(v):
    return pcbnew.FromMM(float(v))


def edt(mask):
    """Distance (mm) from every cell to the nearest set cell of mask."""
    return ndimage.distance_transform_edt(~mask) * RES


class Grid:
    def __init__(self, board):
        # PAD of grid outside the board, so the straight edges are obstacles too.
        bb = board.GetBoardEdgesBoundingBox()
        self.ox, self.oy = pcbnew.ToMM(bb.GetX()) - PAD, pcbnew.ToMM(bb.GetY()) - PAD
        self.W = int(round((pcbnew.ToMM(bb.GetWidth()) + 2 * PAD) / RES))
        self.H = int(round((pcbnew.ToMM(bb.GetHeight()) + 2 * PAD) / RES))

    def px(self, x, y):           # mm -> pixel coordinates (float)
        return ((x - self.ox) / RES - 0.5, (y - self.oy) / RES - 0.5)

    def mm(self, cx, cy):          # cell centre -> mm
        return (self.ox + (cx + 0.5) * RES, self.oy + (cy + 0.5) * RES)

    def raster(self, poly_set):
        img = Image.new('L', (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        for i in range(poly_set.OutlineCount()):
            o = poly_set.Outline(i)
            pts = [self.px(pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y))
                   for k in range(o.PointCount())]
            if len(pts) >= 3:
                d.polygon(pts, fill=1, outline=1)
        return np.array(img) > 0


class Router:
    def __init__(self, board):
        self.board = board
        self.g = g = Grid(board)
        self.so = load_astar()
        self.padcode = np.full((2, g.H, g.W), -1, np.int32)  # pad copper, net code per cell
        self.pads = {}             # net code -> list of (2, H, W) masks, one per pad
        self.paths = {}            # net code -> routed paths
        self.copper = {}           # net code -> (2, H, W) mask of routed copper
        self.neck = {}             # net code -> cells routed at NARROW width
        self.width = {}
        self.hist = np.zeros((2, g.H, g.W), np.float32)
        self._hard = {}
        self._read_board()

    def _read_board(self):
        g, b = self.g, self.board
        for t in list(b.GetTracks()):
            b.Delete(t)
        self.holecode = np.full((g.H, g.W), -1, np.int32)    # pad holes, net code per cell
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.HasHole():
                    ps = pcbnew.SHAPE_POLY_SET()
                    pad.TransformHoleToPolygon(ps, 0, mm(0.005))
                    self.holecode[g.raster(ps)] = max(pad.GetNetCode(), 0)
                m = np.zeros((2, g.H, g.W), bool)
                for li, layer in enumerate(LAYERS):
                    if pad.IsOnLayer(layer):
                        ps = pcbnew.SHAPE_POLY_SET()
                        pad.TransformShapeToPolygon(ps, layer, 0, mm(0.005))
                        m[li] = g.raster(ps)
                code = pad.GetNetCode()
                self.padcode[m] = code if code > 0 else 0
                if code > 0:
                    self.pads.setdefault(code, []).append(m)
        edge = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(edge)
        self.outside_dist = edt(~g.raster(edge))
        self.keep_t = np.zeros((g.H, g.W), bool)
        self.keep_v = np.zeros((g.H, g.W), bool)
        for z in list(b.Zones()) + [z for fp in b.GetFootprints() for z in fp.Zones()]:
            if z.GetIsRuleArea():
                m = g.raster(z.Outline())
                if z.GetDoNotAllowTracks():
                    self.keep_t |= m
                if z.GetDoNotAllowVias():
                    self.keep_v |= m
        self.hole_dist = edt(self.holecode >= 0)
        self.pad_dist = edt((self.padcode >= 0).any(axis=0))

    def net_class(self, code):
        return {'Power': 0.4}.get(self.board.FindNet(code).GetNetClassName(), NARROW)

    # ------------------------------------------------------------ obstacles
    def hard(self, code, width):
        """Cells a track centreline / via centre can never use: other nets' pads,
        board edge, holes, keepouts."""
        key = (code, width)
        if key not in self._hard:
            self._hard[key] = self._hard_calc(code, width)
        bt, bv = self._hard[key]
        return bt.copy(), bv.copy()

    def _hard_calc(self, code, width):
        hw, vr = width / 2, VIA_D / 2
        other = (self.padcode != code) & (self.padcode != -1)
        dist = np.stack([edt(o) for o in other])
        bt = dist < hw + CLEARANCE + MARGIN
        bt |= (self.outside_dist < hw + EDGE_CLEARANCE + MARGIN)[None]
        other_holes = edt((self.holecode != code) & (self.holecode >= 0))
        bt |= (other_holes < hw + HOLE_CLEARANCE + MARGIN)[None]
        bt |= self.keep_t[None]
        bv = dist.min(axis=0) < vr + CLEARANCE + MARGIN
        bv |= self.outside_dist < vr + EDGE_CLEARANCE + MARGIN
        bv |= self.hole_dist < VIA_DRILL / 2 + HOLE_CLEARANCE + vr + MARGIN
        bv |= self.pad_dist < vr + MARGIN                 # no via in pad
        bv |= self.keep_v
        return bt, bv

    def others(self, code):
        out = np.zeros_like(self.padcode, bool)
        for c, m in self.copper.items():
            if c != code:
                out |= m
        return out

    def soft(self, code, width):
        """Cells where a track / via of this net would violate clearance to
        other nets' routed copper."""
        dist = np.stack([edt(x) for x in self.others(code)])
        st = dist < width / 2 + CLEARANCE + MARGIN
        sv = dist.min(axis=0) < VIA_D / 2 + CLEARANCE + MARGIN
        return st, sv

    def soft_necked(self, code):
        st, sv = self.soft(code, self.width[code])
        if self.neck[code].any():
            sn, _ = self.soft(code, NARROW)
            st = np.where(self.neck[code], sn, st)
        return st, sv

    # -------------------------------------------------------------- routing
    def astar(self, bt, bv, src, tgt, cost, costv):
        g = self.g
        ys, xs = np.nonzero(tgt.any(axis=0))
        out = np.zeros(200000, np.int32)
        P = lambda a: a.ctypes.data_as(ctypes.c_void_p)
        arrs = [np.ascontiguousarray(a, np.uint8) for a in (bt, bv, src, tgt)]
        arrs += [np.ascontiguousarray(np.minimum(a, 60000), np.uint16) for a in (cost, costv)]
        n = self.so.route(g.W, g.H, *[P(a) for a in arrs],
                          COST['step'], COST['diag'], COST['via'], COST['turn'],
                          int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()),
                          P(out), len(out))
        if n < 0:
            return None
        cells = out[:n][::-1]
        L, rem = cells // (g.W * g.H), cells % (g.W * g.H)
        return list(zip(L.tolist(), (rem % g.W).tolist(), (rem // g.W).tolist()))

    def route_net(self, code, pres):
        width = self.net_class(code)
        self.width[code] = width
        pads = self.pads[code]
        bt, bv = self.hard(code, width)
        neck = self.neck_mask(code, width)
        bt &= ~neck
        self.neck[code] = neck
        st, sv = self.soft_necked(code)
        cost = self.hist + pres * st
        cost[1] += COST['back']
        costv = pres * sv + self.hist.max(axis=0)
        paths = []
        connected = [0]
        tree = pads[0].copy()
        while len(connected) < len(pads):
            rest = [i for i in range(len(pads)) if i not in connected]
            path = self.astar(bt, bv, tree, np.any([pads[i] for i in rest], axis=0), cost, costv)
            if path is None:
                return None
            paths.append(path)
            for l, x, y in path:
                tree[l, y, x] = True
            for i in rest:          # the path ends in a pad and may cross others
                if any(pads[i][l, y, x] for l, x, y in path):
                    connected.append(i)
                    tree |= pads[i]
        return paths

    def neck_mask(self, code, width):
        """Cells where a wide net may neck down to NARROW: near its own pads
        (fine-pitch parts), where only the wide track would be blocked."""
        bt, _ = self.hard(code, width)
        if width <= NARROW:
            return np.zeros_like(bt)
        bn, _ = self.hard(code, NARROW)
        near = np.stack([edt(m) < NECK for m in np.any(self.pads[code], axis=0)])
        return bt & ~bn & near

    def blocked_cells(self, code):
        """Path cells of this net that sit on a hard obstacle."""
        bt, bv = self.hard(code, self.width[code])
        bt &= ~self.neck[code]
        bad = []
        for path in self.paths[code]:
            for i, (l, x, y) in enumerate(path):
                if bt[l, y, x] or (i and path[i - 1][0] != l and bv[y, x]):
                    bad.append((l, x, y))
        return bad

    def seg_width(self, code, l, x, y):
        return NARROW if self.neck[code][l, y, x] else self.width[code]

    def footprint(self, code, paths):
        """Copper of the routed paths, as a (2, H, W) mask."""
        g = self.g
        out = np.zeros((2, g.H, g.W), bool)
        vr = VIA_D / 2 / RES
        for li in range(2):
            img = Image.new('L', (g.W, g.H), 0)
            d = ImageDraw.Draw(img)
            for path in paths:
                for (l0, x0, y0), (l1, x1, y1) in zip(path, path[1:]):
                    if l0 == l1 == li:
                        r = min(self.seg_width(code, l0, x0, y0),
                                self.seg_width(code, l1, x1, y1)) / 2 / RES
                        d.line([(x0, y0), (x1, y1)], fill=1, width=max(1, int(round(2 * r))))
                        d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=1)
                        d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=1)
                    elif l0 != l1:
                        d.ellipse([x0 - vr, y0 - vr, x0 + vr, y0 + vr], fill=1)
            out[li] = np.array(img) > 0
        return out

    def conflicts(self, code):
        """Path cells of this net that violate clearance to other routed copper."""
        st, sv = self.soft_necked(code)
        bad = []
        for path in self.paths[code]:
            for i, (l, x, y) in enumerate(path):
                if st[l, y, x] or (i and path[i - 1][0] != l and sv[y, x]):
                    bad.append((l, x, y))
        return bad

    def negotiate(self, order, name, todo=None, pres=PRES0):
        todo = list(order if todo is None else todo)
        for rnd in range(ROUNDS):
            for c in todo:
                self.copper.pop(c, None)
                paths = self.route_net(c, pres)
                if paths is None:
                    raise SystemExit(f'{name(c)}: no path even ignoring other nets')
                self.paths[c] = paths
                self.copper[c] = self.footprint(c, paths)
            todo, n = [], 0
            for c in order:
                bad = self.conflicts(c)
                if bad:
                    todo.append(c)
                    n += len(bad)
                    for l, x, y in bad:
                        self.hist[l, max(0, y - 4):y + 5, max(0, x - 4):x + 5] += HIST
            print(f'round {rnd}: {len(todo)} nets in conflict ({n} cells) '
                  f'{[name(c) for c in todo][:8]}', flush=True)
            if not todo:
                return True
            pres *= PRES_GROW
        return False


def simplify(router, code, path):
    """Drop collinear points; keep layer and width changes."""
    pts = [(l, x, y, router.seg_width(code, l, x, y)) for l, x, y in path]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        if a[0] == b[0] == c[0] and a[3] == b[3] == c[3]:
            if (np.sign(b[1] - a[1]), np.sign(b[2] - a[2])) == \
               (np.sign(c[1] - b[1]), np.sign(c[2] - b[2])):
                continue
        out.append(b)
    out.append(pts[-1])
    return out


def emit(board, router, code, paths):
    grid = router.g
    net = board.FindNet(code)
    for path in paths:
        pts = simplify(router, code, path)
        for (l0, x0, y0, w0), (l1, x1, y1, w1) in zip(pts, pts[1:]):
            a = grid.mm(x0, y0)
            if l0 != l1:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
                v.SetWidth(mm(VIA_D))
                v.SetDrill(mm(VIA_DRILL))
                v.SetNet(net)
                board.Add(v)
                continue
            e = grid.mm(x1, y1)
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(mm(e[0]), mm(e[1])))
            t.SetWidth(mm(min(w0, w1)))
            t.SetLayer(LAYERS[l0])
            t.SetNet(net)
            board.Add(t)


def octilinear(p, q, diag_first):
    """Cells from p to q (exclusive of p) along a 45/90 degree dogleg."""
    (x, y), (qx, qy) = p, q
    dx, dy = qx - x, qy - y
    sx, sy = int(np.sign(dx)), int(np.sign(dy))
    d = min(abs(dx), abs(dy))
    legs = [(sx, sy, d), (sx if abs(dx) > abs(dy) else 0, sy if abs(dy) > abs(dx) else 0,
                          abs(abs(dx) - abs(dy)))]
    if not diag_first:
        legs.reverse()
    out = []
    for ux, uy, n in legs:
        for _ in range(n):
            x, y = x + ux, y + uy
            out.append((x, y))
    return out


def drop_via_hops(path, free, pinned):
    """Undo a short hop to the other layer and back (its two vias would sit
    closer than the hole-to-hole rule) when the original layer is clear and
    no other path of the net branches off inside the hop."""
    path = list(path)
    changes = [k for k in range(1, len(path)) if path[k][0] != path[k - 1][0]]
    for a, b in zip(changes, changes[1:]):
        (_, xa, ya), (_, xb, yb) = path[a], path[b]
        if np.hypot(xb - xa, yb - ya) * RES >= VIA_D + HOLE_CLEARANCE:
            continue
        outer = path[a - 1][0]
        hop = path[a:b]
        if path[b][0] == outer and not (set(hop) & pinned) \
                and all(free[outer, y, x] for _, x, y in hop):
            path[a:b] = [(outer, x, y) for _, x, y in hop]
            path = [p for k, p in enumerate(path) if k == 0 or p != path[k - 1]]
            return drop_via_hops(path, free, pinned)
    return path


def smooth(r, code):
    """Pull each same-layer run of the net's paths tight with 45/90 degree
    doglegs wherever the straighter route stays clear."""
    width = r.width[code]
    bt, _ = r.hard(code, width)
    bt &= ~r.neck[code]
    st, _ = r.soft_necked(code)
    free = ~(bt | st)
    neck = r.neck[code]
    # Later paths branch off earlier ones: keep every path end where it is.
    pinned = {p[0] for p in r.paths[code]} | {p[-1] for p in r.paths[code]}
    new_paths = []
    for path in r.paths[code]:
        path = drop_via_hops(path, free, pinned)
        n = len(path)
        # end[i]: last index of the run (same layer, same neck state) holding i
        key = [(l, neck[l, y, x]) for l, x, y in path]
        end = [0] * n
        end[-1] = n - 1
        for i in range(n - 2, -1, -1):
            same = key[i] == key[i + 1] and path[i + 1] not in pinned
            end[i] = end[i + 1] if same else i + (key[i] == key[i + 1])

        def shortcut(i, j):
            l, x, y = path[i]
            for diag_first in (True, False):
                cells = octilinear((x, y), path[j][1:], diag_first)
                if all(free[l, cy, cx] for cx, cy in cells):
                    return cells
            return None

        out = [path[0]]
        i = 0
        while i < n - 1:
            l = path[i][0]
            best, cells = i + 1, None
            lo, step = i + 1, 2
            while lo + step // 2 <= end[i]:          # grow while shortcuts work
                j = min(i + step, end[i])
                c = shortcut(i, j)
                if c is None:
                    break
                best, cells = j, c
                if j == end[i]:
                    break
                step *= 2
            hi = min(i + step, end[i])
            while hi - best > 1:                      # then bisect the gap
                mid = (best + hi) // 2
                c = shortcut(i, mid)
                if c is None:
                    hi = mid
                else:
                    best, cells = mid, c
            if cells is None:
                out.append(path[i + 1])
                i += 1
            else:
                out.extend((l, cx, cy) for cx, cy in cells)
                i = best
        new_paths.append(out)
    r.paths[code] = new_paths
    r.copper[code] = r.footprint(code, new_paths)


def stitch_gnd(board, r):
    """Stitch the GND pours together on a grid wherever a via fits."""
    g = r.g
    code = board.FindNet('GND').GetNetCode()
    _, bv = r.hard(code, NARROW)
    _, sv = r.soft(code, NARROW)
    near_own = edt(r.copper[code].any(axis=0)) < VIA_D / 2 + 0.3
    step = int(round(STITCH / RES))
    paths = [[(0, x, y), (1, x, y)]
             for y in range(step // 2, g.H, step) for x in range(step // 2, g.W, step)
             if not (bv[y, x] or sv[y, x] or near_own[y, x])]
    emit(board, r, code, paths)


def fill(board):
    board.Save(str(PCB))
    board = pcbnew.LoadBoard(str(PCB))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return board


def drop_dangling_vias(board):
    """Remove GND vias that do not land in the filled pour on both layers."""
    pours = [z for z in board.Zones() if not z.GetIsRuleArea()]
    n = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != 'PCB_VIA' or t.GetNetname() != 'GND':
            continue
        pos = t.GetPosition()
        layers = {z.GetLayer() for z in pours if z.HitTestFilledArea(z.GetLayer(), pos)}
        if layers != set(LAYERS):
            board.Delete(t)
            n += 1
    return n


def main():
    board = pcbnew.LoadBoard(str(PCB))
    r = Router(board)
    name = lambda c: board.FindNet(c).GetNetname()
    gnd = board.FindNet('GND').GetNetCode()
    state = HERE / 'build' / 'route_state.pkl'
    save = lambda: state.write_bytes(pickle.dumps((r.g.ox, r.g.oy, order, r.paths, r.width)))
    if '--reuse' in sys.argv and state.exists():
        # Skip negotiation: reuse the last run's paths (same placement only),
        # re-routing only nets that now sit on an obstacle.
        ox, oy, order, paths, r.width = pickle.loads(state.read_bytes())
        dx, dy = int(round((ox - r.g.ox) / RES)), int(round((oy - r.g.oy) / RES))
        r.paths = {c: [[(l, x + dx, y + dy) for l, x, y in p] for p in ps]
                   for c, ps in paths.items()}
        for c in order:
            r.neck[c] = r.neck_mask(c, r.width[c])
            r.copper[c] = r.footprint(c, r.paths[c])
        bad = [c for c in order if r.blocked_cells(c) or r.conflicts(c)]
        print('re-routing', [name(c) for c in bad], flush=True)
        # A continuation: start with the pressure a converging run has reached.
        ok = r.negotiate(order, name, todo=bad, pres=PRES0 * PRES_GROW ** 12) if bad else True
        if bad:
            save()
    else:
        order = []
        for c, pads in r.pads.items():
            if c == gnd or len(pads) < 2:
                continue
            ys, xs = np.nonzero(np.any(pads, axis=(0, 1)))
            order.append((np.ptp(xs) + np.ptp(ys), c))
        order = [c for _, c in sorted(order)]
        ok = r.negotiate(order, name)
    if gnd not in order:
        # GND last, as tracks as well as pours, so no pad relies on a pour island.
        order.append(gnd)
        ok = r.negotiate(order, name, todo=[gnd]) and ok
        save()
    for _ in range(2):
        for c in order:
            smooth(r, c)
    for c in order:
        emit(board, r, c, r.paths[c])
    stitch_gnd(board, r)
    board = fill(board)
    print(f'dropped {drop_dangling_vias(board)} stitching vias outside the pours')
    board = fill(board)
    board.Save(str(PCB))
    print('routed' if ok else 'routed WITH CONFLICTS')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
