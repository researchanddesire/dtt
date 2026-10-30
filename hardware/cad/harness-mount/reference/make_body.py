"""Make the reference body for the on-body renders: the MakeHuman base mesh (CC0) with its average young
female targets applied, cut to the lower body (waist to above the knees, no arms), holes capped,
in mm, smoothed once (Catmull-Clark). Writes body-female-lower.obj beside this script. Needs network access to GitHub.

    python3 hardware/cad/harness-mount/reference/make_body.py

MakeHuman axes match the device's: Y up, Z out of the front. The bust is cut off, and the mesh has no
genital detail, so the renders stay safe for work."""

import os, urllib.request
import numpy as np

SRC = 'https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/'
HERE = os.path.dirname(os.path.abspath(__file__))
Y_RANGE = (-360.0, 260.0)   # mm in MakeHuman's frame: above the knees to the waist
X_MAX = 220.0               # drops the arms, which hang out wide in the A-pose


def fetch(path):
    return urllib.request.urlopen(SRC + path).read().decode()


def largest_piece(faces):
    parent = {}
    def root(i):
        while parent.setdefault(i, i) != i:
            i = parent[i]
        return i
    for f in faces:
        for i in f[1:]:
            parent[root(i)] = root(f[0])
    sizes = {}
    for f in faces:
        sizes[root(f[0])] = sizes.get(root(f[0]), 0) + 1
    big = max(sizes, key=sizes.get)
    return [f for f in faces if root(f[0]) == big]


def subdivide(v, faces):
    """One Catmull-Clark step; the open edges (the cuts) stay on their planes."""
    n = len(v); fp = np.array([v[f].mean(0) for f in faces])
    edges = {}
    for k, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            edges.setdefault((min(a, b), max(a, b)), []).append(k)
    ekey = list(edges); eidx = {e: n + len(faces) + j for j, e in enumerate(ekey)}
    ep = np.array([(v[a] + v[b] + fp[fs].sum(0)) / (2 + len(fs)) if len(fs) == 2 else (v[a] + v[b]) / 2
                   for (a, b), fs in edges.items()])
    vf = [[] for _ in range(n)]; ve = [[] for _ in range(n)]; vb = [[] for _ in range(n)]
    for k, f in enumerate(faces):
        for i in f:
            vf[i].append(k)
    for (a, b), fs in edges.items():
        for i, o in ((a, b), (b, a)):
            ve[i].append((v[i] + v[o]) / 2)
            if len(fs) == 1:
                vb[i].append(v[o])
    nv = v.copy()
    for i in range(n):
        if vb[i]:
            nv[i] = 0.75 * v[i] + 0.125 * sum(vb[i][:2])
        elif vf[i]:
            m = len(vf[i]); nv[i] = (fp[vf[i]].mean(0) + 2 * np.mean(ve[i], 0) + (m - 3) * v[i]) / m
    out = []
    for k, f in enumerate(faces):
        for j, i in enumerate(f):
            a, b = f[j - 1], f[(j + 1) % len(f)]
            out.append([i, eidx[(min(i, b), max(i, b))], n + k, eidx[(min(a, i), max(a, i))]])
    return np.vstack([nv, fp, ep]), out


def main():
    verts, faces, group = [], [], None
    for line in fetch('3dobjs/base.obj').splitlines():
        if line.startswith('v '):
            verts.append([float(t) for t in line.split()[1:4]])
        elif line.startswith('g '):
            group = line.split()[1]
        elif line.startswith('f ') and group == 'body':
            faces.append([int(t.split('/')[0]) - 1 for t in line.split()[1:]])
    v = np.array(verts)
    for race in ('african', 'asian', 'caucasian'):   # MakeHuman's default: female, young, races mixed evenly
        for line in fetch('targets/macrodetails/%s-female-young.target' % race).splitlines():
            if line and line[0] != '#':
                p = line.split(); v[int(p[0])] += np.array([float(t) for t in p[1:4]]) / 3
    v *= 100.0   # decimetres to mm
    lo, hi = Y_RANGE   # faces that reach into the range, their outside corners pulled onto the cut planes
    keep = [f for f in faces if all(abs(v[i, 0]) <= X_MAX for i in f)
            and any(lo < v[i, 1] < hi for i in f)]
    v[:, 1] = np.clip(v[:, 1], lo, hi)
    keep = [f for f in keep if len({tuple(np.round(v[i], 3)) for i in f}) >= 3]
    keep = largest_piece(keep)   # the torso, not bits of the arms
    v, keep = subdivide(v, keep)
    count = {}
    for f in keep:
        for a, b in zip(f, f[1:] + f[:1]):
            count[(a, b)] = count.get((a, b), 0) + 1
    border = {a: b for (a, b) in count if (b, a) not in count}   # edges with one face, in face order
    caps = []
    while border:
        a = next(iter(border)); loop = [a]
        while border.get(loop[-1]) is not None and border[loop[-1]] != a:
            loop.append(border.pop(loop[-1]))
        border.pop(loop[-1], None)
        if len(loop) < 3:
            continue
        c = len(v) + len(caps); caps.append(v[loop].mean(0))
        keep += [[c, loop[(k + 1) % len(loop)], loop[k]] for k in range(len(loop))]   # flat fan, facing out
    v = np.vstack([v] + [np.array(caps)]) if caps else v
    used = sorted({i for f in keep for i in f}); new = {o: n for n, o in enumerate(used)}
    with open(os.path.join(HERE, 'body-female-lower.obj'), 'w') as out:
        out.write('# MakeHuman base mesh hm08 (CC0, makehumancommunity.org), average young female,\n'
                  '# lower body only, mm, Y up, Z forward. Made by make_body.py.\n')
        for i in used:
            out.write('v %.2f %.2f %.2f\n' % tuple(v[i]))
        for f in keep:
            out.write('f %s\n' % ' '.join(str(new[i] + 1) for i in f))
    print('%d vertices, %d faces, %d caps' % (len(used), len(keep), len(caps)))


if __name__ == '__main__':
    main()
