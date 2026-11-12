"""Moldability check on STL parts: draft, undercuts and wall thickness.

    python3 dfm_check.py part.stl [--pull z|x|y|-x...] [--png out.png] [--view dir]

Each triangle is classed against the pull axis (both halves of the tool move
along it, one each way):
  red      undercut: the ray along the pull, on the side the face looks to,
           hits the part, so neither half can release it (needs a slide,
           lifter or pass-through core)
  orange   no draft (under 0.4 degrees)
  yellow   0.4 to 1 degree (0.5 is the rib and post draft)
  green    1 degree or more
  grey     flat to the pull
Wall thickness: a ray inward along each face's normal. Over 2.6 mm is flagged
as thick (sink, voids); under 0.8 as thin (short shots).
"""
import argparse
import json
import math

import numpy as np
import trimesh

COL = {"undercut": (0.85, 0.12, 0.12), "nodraft": (0.98, 0.55, 0.05), "low": (0.95, 0.85, 0.15),
       "ok": (0.25, 0.70, 0.30), "flat": (0.62, 0.66, 0.70)}
AX = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}


def analyse(mesh, pull=(0, 0, 1), thick=2.6, thin=0.8):
    pull = np.asarray(pull, float) / np.linalg.norm(pull)
    n = mesh.face_normals
    c = mesh.triangles_center
    a = mesh.area_faces
    d = n @ pull
    draft = np.degrees(np.arcsin(np.clip(np.abs(d), 0, 1)))
    ray = trimesh.ray.ray_pyembree.RayMeshIntersector(mesh) if trimesh.ray.has_embree else mesh.ray
    eps = 1e-3
    o = c + n * eps
    up = ray.intersects_any(o, np.tile(pull, (len(c), 1)))
    dn = ray.intersects_any(o, np.tile(-pull, (len(c), 1)))
    side = np.where(d > 1e-3, ~up, np.where(d < -1e-3, ~dn, ~up | ~dn))
    cls = np.full(len(c), "ok", dtype=object)
    cls[draft < 0.9] = "low"
    cls[draft < 0.4] = "nodraft"
    cls[draft > 85] = "flat"
    cls[~side] = "undercut"
    # wall thickness: first hit inward
    oi = c - n * eps
    loc, idx, _ = ray.intersects_location(oi, -n, multiple_hits=False)
    t = np.full(len(c), np.nan)
    t[idx] = np.linalg.norm(loc - oi[idx], axis=1)
    res = {k: float(a[cls == k].sum()) for k in COL}
    tv = ~np.isnan(t)
    res["thick_area"] = float(a[tv & (t > thick)].sum())
    res["thin_area"] = float(a[tv & (t < thin)].sum())
    res["area"] = float(a.sum())
    res["wall_median"] = float(np.median(t[tv])) if tv.any() else None
    res["wall_p95"] = float(np.percentile(t[tv], 95)) if tv.any() else None
    return cls, t, res


def colours(cls):
    return np.array([COL[k] for k in cls], np.float32)


def thick_colours(t, nominal=1.6):
    # blue thin, green nominal, red thick
    out = np.zeros((len(t), 3), np.float32) + 0.7
    v = ~np.isnan(t)
    r = np.clip((t[v] - 0.8) / (3.2 - 0.8), 0, 1)
    import matplotlib
    out[v] = matplotlib.colormaps["turbo"](r)[:, :3]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl", nargs="+")
    ap.add_argument("--pull", default="z")
    ap.add_argument("--json")
    a = ap.parse_args()
    s = a.pull.lstrip("-")
    pull = AX[s]
    allres = {}
    for f in a.stl:
        m = trimesh.load(f, force="mesh")
        _, _, res = analyse(m, pull)
        allres[f] = res
        print(f, json.dumps({k: round(v, 1) if isinstance(v, float) else v for k, v in res.items()}))
    if a.json:
        json.dump(allres, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
