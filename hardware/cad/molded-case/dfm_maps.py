"""Render draft/undercut maps for a set of STL parts.

    python3 dfm_maps.py out.png "Title" part.stl:pull[:view] ...
view is 'in' (from the open side) or 'out'.
"""
import sys

import trimesh

import dfm_check as D
import mrender as M

LEG = [(D.COL["undercut"], "undercut"), (D.COL["nodraft"], "no draft"), (D.COL["low"], "0.4-1 deg"),
       (D.COL["ok"], ">= 1 deg"), (D.COL["flat"], "flat to pull")]


def views(spec):
    f, pull, *rest = spec.split(":")
    m = trimesh.load(f, force="mesh")
    cls, t, res = D.analyse(m, D.AX[pull.lstrip("-")])
    return m, cls, res


if __name__ == "__main__":
    out, title, *specs = sys.argv[1:]
    paths = []
    for i, s in enumerate(specs):
        m, cls, res = views(s)
        name = s.split(":")[0].split("/")[-1].replace(".stl", "")
        for j, d in enumerate([(-1, 1.2, -1.1), (-1, 1.2, 0.9)]):
            p = f"/tmp/dfm_{i}_{j}.png"
            M.render([M.part(m, face_colors=D.colours(cls))], p, size=(800, 640), dir_=d,
                     title=f"{name}  undercut {res['undercut']:.0f} mm²" if j == 0 else None,
                     legend=LEG if (i == 0 and j == 1) else None)
            paths.append(p)
    M.grid(paths, out, cols=2)
    print(out)
