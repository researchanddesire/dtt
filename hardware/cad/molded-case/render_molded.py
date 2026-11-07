"""Renders for the molded case: python3 render_molded.py (after the build)."""
import glob
import os

import numpy as np
import trimesh

import dfm_check as D
import mrender as M

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, "parts")
REF = os.path.join(HERE, "build")
IMG = os.path.join(HERE, "images")
BLACK, BLUE, WHITE, GREEN, METAL = (0.2, 0.2, 0.22), (0.09, 0.42, 0.93), (0.92, 0.92, 0.88), (0.05, 0.3, 0.15), (0.7, 0.7, 0.72)


def L(name, d=PARTS):
    return trimesh.load(os.path.join(d, name + ".stl"), force="mesh")


def comps(off=(0, 0, 0)):
    out = []
    for f in sorted(glob.glob(os.path.join(REF, "*.stl"))):
        n = os.path.basename(f)[:-4]
        if n.startswith("Cup"):
            continue
        col = GREEN if n == "BoardRev4" else METAL if n.startswith("Screw") else (0.35, 0.35, 0.38)
        if n in ("BatteryPouch",):
            col = (0.75, 0.75, 0.78)
        if n.startswith("Harness") or n.startswith("BatteryLead"):
            col = (0.8, 0.3, 0.2)
        if n == "Part__Feature005":
            col = (0.05, 0.05, 0.08)
        o = off if not n.startswith("Screw") else (off[0], off[1], off[2] * 2.2)
        out.append(M.part(f, col, offset=o))
    return out


def main():
    os.makedirs(IMG, exist_ok=True)
    H, B, C, S, Dif = L("Housing-Black"), L("Housing-Shot2-Blue"), L("Cap-Cups-Black"), L("Switch-Cover-Blue"), L("Diffuser-White")
    cups = [M.part(L("Cup%d" % i, REF), (0.85, 0.85, 0.9), alpha=0.55) for i in (1, 2)]
    shell = [M.part(H, BLACK), M.part(B, BLUE), M.part(S, BLUE), M.part(Dif, WHITE)]
    M.render(shell + [M.part(C, BLACK)], os.path.join(IMG, "Molded-Front.png"), size=(1000, 800), dir_=(-1, 1.2, -1.0))
    M.render(shell + [M.part(C, BLACK)] + cups, os.path.join(IMG, "Molded-Rear.png"), size=(1000, 800), dir_=(-1, 1.2, 0.9))
    # exploded
    up = 30.0
    ex = [M.part(H, BLACK, offset=(0, 0, up)), M.part(B, BLUE, offset=(0, 0, up + 12)), M.part(Dif, WHITE, offset=(0, 0, up - 6)),
          M.part(S, BLUE, offset=(14, 0, up * 0.5)), M.part(C, BLACK, offset=(0, 0, -up))] + comps((0, 0, -up * 0.45))
    M.render(ex, os.path.join(IMG, "Molded-Exploded.png"), size=(1000, 1100), dir_=(-1, 1.25, -0.75))
    M.render([M.part(H, BLACK), M.part(B, BLUE)], os.path.join(IMG, "Part-Housing-Inside.png"), size=(1000, 800), dir_=(-1, 1.2, 1.0))
    M.render([M.part(C, BLACK)], os.path.join(IMG, "Part-CapCups-Inside.png"), size=(1000, 800), dir_=(-1, 1.2, -1.0))
    M.render([M.part(L("Cap-Black"), BLACK)], os.path.join(IMG, "Part-Cap-Inside.png"), size=(1000, 800), dir_=(-1, 1.2, -1.0))
    # moldability maps, after
    paths = []
    for i, (n, pull) in enumerate((("Housing-Black", "z"), ("Cap-Cups-Black", "z"))):
        m = L(n)
        cls, t, res = D.analyse(m, D.AX[pull])
        for j, d in enumerate([(-1, 1.2, -1.1), (-1, 1.2, 0.9)]):
            p = "/tmp/dfma_%d_%d.png" % (i, j)
            M.render([M.part(m, face_colors=D.colours(cls))], p, size=(800, 640), dir_=d,
                     title="%s  undercut %.0f mm²" % (n, res["undercut"]) if j == 0 else None,
                     legend=[(D.COL[k], s) for k, s in (("undercut", "undercut"), ("nodraft", "no draft"), ("low", "0.5-1 deg"),
                                                        ("ok", ">= 1 deg"), ("flat", "flat to pull"))] if (i == 0 and j == 1) else None)
            paths.append(p)
    M.grid(paths, os.path.join(IMG, "DFM-After.png"))


if __name__ == "__main__":
    main()

