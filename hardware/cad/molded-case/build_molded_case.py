"""Injection-moulded version of the enclosed DTT case (first pass).

Same outside, PCB, parts and screw axes as ../enclosed-case (PR #13), rebuilt
as moulded parts instead of a printed body: one uniform wall, draft on
everything that faces sideways, nothing that needs a slide, and features
that pull straight out of a two-plate tool. Where a printed snap could not be
moulded, it is swapped for a moulded equivalent (see README).

    /opt/fc11/bin/freecadcmd build_molded_case.py      (writes parts/)

Coordinates as in ../enclosed-case: X = pcb_x - 127.583333,
Y = 151.9861 - pcb_y, PCB top at Z = -3.5, PCB back at Z = -5.1. The tool
opens along Z for the housing and the caps, along X for the switch cover.
"""

import math
import os
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "enclosed-case"))
import build_enclosed_case as ENC  # noqa: E402

ASSY = os.path.join(HERE, "..", "enclosed-case", "DTT-Enclosed.FCStd")
PARTS = os.path.join(HERE, "parts")
V = App.Vector
E = ENC.P
box, zcyl, rect, disc, ext = ENC.box, ENC.zcyl, ENC.rect, ENC.disc, ENC.ext

PARAMS = {
    # Material: PC/ABS, about 0.5-0.7 % shrink. Everything below is the
    # moulded (shrunk) size.
    "wall": 1.6,  # nominal wall: sides, ends, top plate, cap floor
    "draft": 1.0,  # degrees on the outside (1.5+ under a texture finish)
    "draft_in": 1.0,  # inside walls, so the wall stays uniform
    "rib_draft": 0.5,  # each face of ribs, bosses and posts
    "cut_draft": 1.0,  # through openings and pockets in the plate, notches, keyholes
    "fit_draft": 0.5,  # sliding and locating fits (switch channel, PCB pocket)
    "shutoff": 3.0,  # where the two halves meet on a side face (connector notches, cup-cap windows)
    "root_r": 0.4,  # fillet where ribs, bosses and posts meet the plate or the cap floor (0.25 x wall)
    # Steel safe: fits start loose / light, so the moulder tunes them by
    # taking steel out of the tool (adding steel back means welding).
    "steel_safe": {"slider_clear": 0.25, "cup_snap": (8.6, 8.2, 1.5)},
    "pcb_pocket_grow": 0.1,  # steel safe: PCB pocket and rib ends 0.1 further off the board than PR #13
    "rib": 1.0,  # rib thickness, about 60 % of the wall, so no sink on the top face
    # The top plate is a full wall thick (underside 12.57, as before); the
    # OLED glass, whose face is at 12.77, gets a shallow pocket.
    # The CAD glass is 25.8 x 15.4, but a real 0.96" module's glass is about
    # 26.7 x 19.3, so leave room for that: the pocket and the clear zone
    # between the standoffs.
    "glass_pocket": (7.6, 35.2, 34.4, 56.3, 0.0, 12.82),  # x0, y0, x1, y1, clearance round it, pocket ceiling z
    # PCB screw bosses: the original 0408LTFB (#4) thread-forming screws.
    "boss_od": 5.6,  # about 2 x the 2.84 mm thread
    "boss_hole": 2.6,  # pilot, steel safe; check the screw maker's chart for PC/ABS (often 0.8 x d = 2.3)
    "boss_hole_top": 7.0,  # pilot up to here (past the screw's tip)
    "boss_relief": 1.6,  # then a thinner core up to 0.6 under the plate, so the boss is a 2 mm tube, not a solid lump
    "boss_rib": True,  # tie each boss to the side wall with a rib
    # PCB locating ribs on the inside of the walls, plate to seam, 0.3 off the PCB edge.
    "pcb_ribs_y": (14.0, 45.0, 58.0),  # both long sides
    # OLED: four posts through its mounting holes, heat-staked, on standoffs
    # that hold the glass 0.05 off its pocket.
    "oled_holes": ((9.25, 33.64), (32.75, 33.64), (9.25, 57.44), (32.75, 57.44)),
    "oled_board_top": 10.77,
    "oled_board_back": 9.57,
    "stake": (1.7, 0.8),  # post diameter (OLED hole about 2.0), length past the board's back (0.97 to the cell under the button-end holes)
    "standoff_d": 3.2,  # span of the two crossed fins round each stake, clipped clear of the glass_pocket zone
    "oled_key": (11.5, 34.0, 15.5, 35.0, 11.2),  # rib where the flex would be if the module went in turned round
    # Distance sensor: its own two screws into bosses, a window round its
    # optical case, and a key rib.
    "sensor_pcb_top": 3.67,
    "sensor_screws": ((9.3, 16.9), (32.7, 10.3)),
    "sensor_boss": (3.8, 1.7),  # OD, pilot (assumed M2 thread-forming; the original screws are unknown)
    "sensor_window": (11.4, 9.6, 30.6, 17.6, 0.15),  # optical case x0, y0, x1, y1, clearance
    "sensor_key": (9.5, 7.0, 16.0, 8.0, 0.6),  # x0, y0, x1, y1, bottom z
    # LED light bar: an open window under the overlay's white print, and a
    # in from inside, and a chimney round the LEDs.
    "diffuser_throat": (7.0, 20.5, 35.0, 27.5),
    "chimney": 4.0,  # bottom z of a rib-thick wall round the seat, clear of the sensor PCB and the harness
    # Battery: located by ribs, held on two strips of double-sided tape on
    # the lands over it (printed clips are undercuts).
    "battery": (8.2, 54.7, 28.2, 89.7, 1.6, 8.6),
    "tape": 0.15,
    "battery_lands_y": (61.0, 68.0, 75.0, 82.0, 88.0),
    "battery_side_ribs": ((-1, 64.0), (-1, 78.0), (-1, 86.0), (1, 78.0), (1, 86.0)),  # side, y
    "battery_rib_bottom": 4.5,
    "battery_gap": 0.35,
    # Button: the flexure as in PR #13 (U slot through the plate), the post
    # now 0.3 over S2's plunger, since a moulding holds that tolerance.
    "button_post_gap": 0.3,
    "button_post_core": 2.2,  # the post is cored from its tip, so it isn't a 4 mm solid rod
    "s2_top": -0.2,
    # Top overlay: one printed polycarbonate film over the whole flat top, in
    # a shallow recess so its edge can't catch. Back-printed black, with the
    # product blue (logo, button pad), a white diffuser window over the LEDs
    # and a clear window over the screen. A die-cut hole over the sensor's
    # lenses (a film across them carries IR from emitter to detector). The
    # film runs solid over the button (nothing to line up, and it seals the
    # slot): bonded to the pad and bar, no adhesive in a band over the U slot
    # so the film can bend there as the pad moves.
    "overlay": (0.25, 0.3, 0.8, 0.2),  # film with adhesive, recess depth, recess inset from the flat top's edge, film to recess wall
    "overlay_hinge": 1.0,  # no-adhesive band past each side of the button's U slot
    "overlay_clear_grow": 0.5,  # clear window past the viewport, so the print edge hides the cut
    # Second layer just over the LEDs: an opal light-diffusing PC film laminated
    # under the overlay's white window (two hits of white ink), sitting down in
    # the window through the plate, so the three LEDs read as one even bar.
    "diffuser_layer": (0.25, 0.2),  # thickness, clearance to the window walls
    # Connector openings run down to the parting line (U notches), so no
    # slides: the B half forms them from below. The cap fills them back up.
    "notch_clear": 0.05,
    # Switch cover: a closed pocket round S1's lever, this much clear above and below.
    "slider_lever_clear": 0.25,
    # Cap.
    "cap_floor": 1.6,
    "cap_edge_draft": 1.0,
    "lip": (0.8, 1.0, 0.1, (8.0, 74.0)),  # lip joint on the long sides: housing keeps the outer 0.8 of its wall for the last 1.0 mm; the cap's lip fills the rest, with this clearance; y range
    "cap_boss_od": 7.0,  # round the countersink, up to the PCB
    "cup_wall": 1.6,  # keyhole housings in the cup cap
}
P = PARAMS
E.update(P["steel_safe"])  # PR #13's sizes the moulded parts share


def T(a):
    return math.tan(math.radians(a))


# --- Drafted outside and inside -------------------------------------------

_round_inset = ENC.round_inset


def drafted_round_inset(z, t=0.0):
    """The PR #13 inset at height z, plus the draft: every section moves in by
    tan(draft) for each mm above the seam, ends included."""
    return _round_inset(z, t) + T(P["draft"]) * max(z - E["seam_z"], 0.0)


def envelope(z0, t=0.0):
    """Outside of the housing from z0 up, or the surface t inside it (the
    inside of a uniform shell): a ruled loft for the drafted sides up to the
    top round, then PR #13's loft round the top."""
    ENC.round_inset = drafted_round_inset
    try:
        curved, straight = ENC.section_levels(t)
        wire = lambda z: ENC.outline_at(z, 0.0, ENC.round_inset(z, t)).OuterWire
        za = curved[0]
        s = Part.makeLoft([wire(z0), wire(za)], True, True)
        s = s.fuse(Part.makeLoft([wire(z) for z in curved], True, False))
        if straight:
            s = s.fuse(Part.makeLoft([wire(z) for z in straight], True, True))
        return ENC.solid(s.removeSplitter())
    finally:
        ENC.round_inset = _round_inset


def dprism(face, z_root, z_tip, ang=None):
    """A face extruded from z_root to z_tip, tapering by ang degrees a side
    toward the tip (a drafted rib, post or boss)."""
    ang = P["rib_draft"] if ang is None else ang
    if len(face.Faces) > 1:
        ss = [dprism(f, z_root, z_tip, ang) for f in face.Faces]
        return ss[0].fuse(ss[1:]) if len(ss) > 1 else ss[0]
    face = face.Faces[0]
    d = abs(z_tip - z_root) * T(ang)
    w0 = face.OuterWire.copy()
    w0.translate(V(0, 0, z_root - w0.BoundBox.ZMin))
    f1 = ENC.offset_face(face, -d) if abs(d) > 1e-4 else face
    w1 = f1.OuterWire.copy()
    w1.translate(V(0, 0, z_tip - w1.BoundBox.ZMin))
    return Part.makeLoft([w0, w1], True, True)


def taper(shape, nom, ang, axis=(0, 0, 1)):
    """Redraw a prism (constant section along axis) with draft: its section
    is as drawn at nom along the axis, and grows by tan(ang) for each mm
    further along the axis (ang < 0: shrinks). A cut that is wider at the
    bottom takes ang < 0; a feature hanging down that is thinner at its tip
    takes ang > 0 with nom at its root."""
    a = V(*axis)
    bb = shape.BoundBox
    pts = [V(x, y, z) for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax) for z in (bb.ZMin, bb.ZMax)]
    lo, hi = min(p.dot(a) for p in pts), max(p.dot(a) for p in pts)
    mid = (lo + hi) / 2
    faces = Part.makeFace(shape.slice(a, mid), "Part::FaceMakerBullseye").Faces
    out = []
    k = T(ang)
    for f in faces:
        if f.Wires and len(f.Wires) > 1:
            print("taper: section with a hole, left straight")
            out.append(f.extrude(a * (hi - lo)).translated(a * (lo - mid)))
            continue
        ws = []
        for at in (lo, hi):
            d = (at - nom) * k
            g = ENC.offset_face(f, d) if abs(d) > 1e-5 else f
            w = g.OuterWire.copy()
            w.translate(a * (at - mid))
            ws.append(w)
        out.append(Part.makeLoft(ws, True, True))
    return out[0].fuse(out[1:]).removeSplitter() if len(out) > 1 else out[0]


def drop_slivers(shape, tol=0.01):
    """Booleans on tangent drafted faces can leave zero-volume scraps."""
    big = [x for x in shape.Solids if x.Volume > tol]
    return big[0] if len(big) == 1 else Part.makeCompound(big)


def root_edges(shape, z, down=True):
    """Concave edges in the plane z where something stands off it: ribs,
    bosses and posts hanging below it (down) or standing on it."""
    out = []
    sgn = -1.0 if down else 1.0
    for e in shape.Edges:
        b = e.BoundBox
        if abs(b.ZMin - z) > 1e-4 or abs(b.ZMax - z) > 1e-4:
            continue
        fs = shape.ancestorsOfType(e, Part.Face)
        m = e.valueAt(e.FirstParameter + 0.5 * (e.LastParameter - e.FirstParameter))
        n = None
        for f in fs:
            try:
                u, v = f.Surface.parameter(m)
                nn = f.normalAt(u, v)
            except Exception:
                continue
            if abs(nn.z) < 0.9:
                n = nn
                break
        if n is None:
            continue
        q = m - V(n.x, n.y, 0) * 0.05 + V(0, 0, sgn * 0.05)
        if shape.isInside(q, 1e-6, True):
            out.append(e)
    return out


def root_fillet(feat, z, r, down=True):
    """Give a rib, boss or post a fillet of radius r where it meets the plane
    z (the plate's underside, or the cap's floor): fuse it with a slab on the
    far side of z, fillet the concave edges in z, and return the result. The
    slab is clipped off later (adds are trimmed to the inside of the shell)."""
    try:
        b = feat.BoundBox
        g = r + 0.6
        z0, z1 = (z, z + 0.5) if down else (z - 0.5, z)
        slab = box(b.XMin - g, b.YMin - g, z0, b.XMax + g, b.YMax + g, z1)
        s = feat.fuse(slab).removeSplitter()
        es = root_edges(s, z, down)
        if not es:
            return feat
        f = s.makeFillet(r, es)
        return f if f.isValid() else feat
    except Exception:
        return feat


def tz(shape, nom, ang):
    return [taper(s, nom, ang) for s in shape] if isinstance(shape, list) else taper(shape, nom, ang)


def drib(x0, y0, x1, y1, z_root, z_tip, ang=None):
    return dprism(rect(x0, y0, x1, y1), z_root, z_tip, ang)


def dpost(x, y, d, z_root, z_tip, ang=None):
    ang = P["rib_draft"] if ang is None else ang
    r0 = d / 2
    r1 = r0 - abs(z_tip - z_root) * T(ang)
    h = abs(z_tip - z_root)
    if z_tip < z_root:
        return Part.makeCone(r1, r0, h, V(x, y, z_tip))
    return Part.makeCone(r0, r1, h, V(x, y, z_root))


def dhole(x, y, d, z_open, z_end, ang=None):
    """A cored hole, d at its open end, narrowing toward z_end."""
    return dpost(x, y, d, z_open, z_end, ang)


# --- Housing ---------------------------------------------------------------


def pcb_pocket_face(pcb):
    return ENC.offset_face(ENC.pcb_pocket(pcb), P["pcb_pocket_grow"])


def plate_under():
    return E["top_z"] - P["wall"]


def pcb_ribs(pcb, inner):
    """Ribs on the inside of each long wall, stopping 0.3 off the PCB's edge.
    They hang full height from the plate: a rib that stood up from the open
    edge would have its top face toward the plate, an undercut for the core."""
    zs = E["seam_z"]
    pocket = taper(ext(pcb_pocket_face(pcb).OuterWire, zs - 1, E["top_z"] + 1), E["pcb_top_z"], -P["fit_draft"])
    ribs = []
    t = P["rib"]
    for y in P["pcb_ribs_y"]:
        for xa, xb in ((-10, 21), (21, 52)):
            ribs.append(drib(xa, y - t / 2, xb, y + t / 2, plate_under() + 0.3, zs))
    return Part.makeCompound(ribs).cut(pocket)


def boss_core(x, y, pilot, z_open, z_pilot, relief, zu):
    """A boss's core from its open tip: the pilot for the screw up to
    z_pilot, then a thinner relief core up to 0.6 under the plate, so the
    boss is a tube all the way up and leaves no thick lump (and no sink mark)
    under the top face. A hanging boss can't get thinner toward its root
    without an undercut, so the coring has to come from the tip."""
    out = [dhole(x, y, pilot, z_open, z_pilot, 0.25)]
    if relief:
        out.append(dhole(x, y, relief, z_pilot - 0.01, zu - 0.6, 0.25))
    return out


def screw_bosses(inner_wall):
    zu, zp = plate_under(), E["pcb_top_z"]
    out, holes = [], []
    for x, y in E["screw_axes"]:
        out.append(dpost(x, y, P["boss_od"], zu + 0.3, zp))
        holes += boss_core(x, y, P["boss_hole"], zp - 0.1, P["boss_hole_top"], P["boss_relief"], zu)
        if P["boss_rib"]:  # out to the side wall; clipped to the inside later
            xa, xb = (x - 12, x) if x < 21 else (x, x + 12)
            t = P["rib"] / 2
            out.append(drib(xa, y - t, xb, y + t, zu + 0.3, zp + 1.0).cut(zcyl(x, y, P["boss_od"] - 0.4, -10, 20)))
    return out, holes


def oled_mount():
    zu = plate_under()
    zt, zb = P["oled_board_top"], P["oled_board_back"]
    d, past = P["stake"]
    parts = []
    x0, y0, x1, y1 = P["glass_pocket"][:4]
    clip = taper(box(x0, y0, zt - 1, x1, y1, zu + 1), zu, -P["rib_draft"])
    r, t = P["standoff_d"] / 2, P["rib"] / 2
    for x, y in P["oled_holes"]:
        fins = [drib(x - r, y - t, x + r, y + t, zu + 0.3, zt), drib(x - t, y - r, x + t, y + r, zu + 0.3, zt)]
        parts += [f.cut(clip) for f in fins]
        parts.append(dpost(x, y, d, zu + 0.3, zb - past, 0.25))  # the stake runs up to the plate
    kx0, ky0, kx1, ky1, kz = P["oled_key"]
    parts.append(drib(kx0, ky0, kx1, ky1, zu + 0.3, kz))
    return parts


def glass_pocket():
    x0, y0, x1, y1, c, zc = P["glass_pocket"]
    return taper(box(x0 - c, y0 - c, plate_under() - 0.5, x1 + c, y1 + c, zc), zc, -P["cut_draft"])


def sensor_mount():
    zu, zp = plate_under(), P["sensor_pcb_top"]
    od, pilot = P["sensor_boss"]
    parts, holes = [], []
    for x, y in P["sensor_screws"]:
        parts.append(dpost(x, y, od, zu + 0.3, zp))
        holes += boss_core(x, y, pilot, zp - 0.1, zu - 0.6, 0, zu)  # the pilot runs on up: no lump under the plate
    kx0, ky0, kx1, ky1, kz = P["sensor_key"]
    parts.append(drib(kx0, ky0, kx1, ky1, zu + 0.3, kz))
    x0, y0, x1, y1, c = P["sensor_window"]
    window = taper(box(x0 - c, y0 - c, zu - 1, x1 + c, y1 + c, E["top_z"] + 1), E["top_z"], -P["cut_draft"])
    return parts, holes, window


def light_bar():
    zu = plate_under()
    tx0, ty0, tx1, ty1 = P["diffuser_throat"]
    cz = P["chimney"]
    t = P["rib"]
    outer = dprism(rect(tx0 - t, ty0 - t, tx1 + t, ty1 + t), zu + 0.3, cz)
    # the window as drawn at the top face, opening toward the core all the way down
    window = taper(box(tx0, ty0, cz - 1, tx1, ty1, E["top_z"] + 1), E["top_z"], -P["rib_draft"])
    return outer.cut(window), [window]


def battery_ribs():
    x0, y0, x1, y1, z0, z1 = P["battery"]
    zu = plate_under()
    g, t = P["battery_gap"], P["rib"]
    zl = z1 + P["tape"]
    parts = [drib(x0 + 1, y - t / 2, x1 - 1, y + t / 2, zu + 0.3, zl) for y in P["battery_lands_y"]]
    for side, y in P["battery_side_ribs"]:
        xi = x0 - g if side < 0 else x1 + g
        xo = xi + side * t
        parts.append(drib(min(xi, xo), y - 3, max(xi, xo), y + 3, zu + 0.3, P["battery_rib_bottom"]))
    # end stop at the USB-C end
    parts.append(drib(x0 + 2, y1 + g, x1 - 2, y1 + g + t, zu + 0.3, P["battery_rib_bottom"]))
    return parts


def button():
    """PR #13's U slot and pad over S2, with a drafted post. The tray under it
    is gone: S2 stops the pad."""
    px, py, pr = E["button_pad"]
    zu = plate_under()
    # the U's outside opens out downward and the bar and pad narrow downward,
    # each drafted on its own (offsetting the thin U itself makes bad faces)
    xr, bw = E["button_bar"]
    w, h = E["button_slot_w"], bw / 2
    z0, z1, zt, cd = zu - 1, E["top_z"] + 1, E["top_z"], P["cut_draft"]
    outer = ENC.merge_faces(rect(xr, py - h - w, px, py + h + w).fuse(disc(px, py, pr + w)))
    for yc in (py - h - w / 2, py + h + w / 2):
        outer = ENC.merge_faces(outer.fuse(disc(xr, yc, w / 2)))
    tongue = ENC.merge_faces(rect(xr - 1, py - h, px, py + h).fuse(disc(px, py, pr)))
    slot = taper(ext(outer.OuterWire, z0, z1), zt, -cd).cut(taper(ext(tongue.OuterWire, z0 - 0.5, z1 + 0.5), zt, cd))
    tip = P["s2_top"] + P["button_post_gap"]
    post = dpost(px, py, E["button_post"][0], zu + 0.3, tip)
    post = post.cut(dhole(px, py, P["button_post_core"], tip - 0.1, zu - 0.6, P["rib_draft"]))
    return slot, post


def flat_top():
    """The flat top face, inside the top round."""
    zt = E["top_z"]
    return ENC.outline_at(zt, 0.0, drafted_round_inset(zt))


def button_hinge():
    """The no-adhesive band over the button's U slot, overlay_hinge past each
    side of it. The film stays bonded to the middle of the bar and the pad."""
    px, py, pr = E["button_pad"]
    xr, bw = E["button_bar"]
    w, h, g = E["button_slot_w"], bw / 2, P["overlay_hinge"]
    outer = ENC.merge_faces(rect(xr - g, py - h - w - g, px, py + h + w + g).fuse(disc(px, py, pr + w + g)))
    inner = ENC.merge_faces(rect(xr - g - 1, py - h + g, px, py + h - g).fuse(disc(px, py, pr - g)))
    return outer.cut(inner)


def overlay_faces(logo):
    """The overlay's 2D layers at z 0: die-cut outline and holes, and the
    clear, white and blue print areas (black is everything else)."""
    t, depth, inset, gap = P["overlay"]
    recess = ENC.offset_face(flat_top(), -inset)
    outline = ENC.offset_face(recess, -gap)
    zt = E["top_z"]
    x0, y0, x1, y1, c = P["sensor_window"]
    holes = [rect(x0 - c, y0 - c, x1 + c, y1 + c)]
    hinge = button_hinge()
    cx, cy, w, ht, r, _ = E["viewport"]
    g = P["overlay_clear_grow"]
    clear = ENC.rounded_rect(cx - w / 2 - g, cy - ht / 2 - g, cx + w / 2 + g, cy + ht / 2 + g, r + g)
    tx0, ty0, tx1, ty1 = P["diffuser_throat"]
    white = rect(tx0, ty0, tx1, ty1)
    blue = []
    for f in logo.Faces:
        if f.normalAt(0, 0).z > 0.99 and abs(f.CenterOfMass.z - zt) < 1e-3:
            f = f.copy()
            f.translate(V(0, 0, -zt))
            blue.append(f)
    px, py, pr = E["button_pad"]
    blue.append(disc(px, py, pr))
    for f in [outline, recess] + holes + [clear, white, hinge]:
        f.translate(V(0, 0, -f.BoundBox.ZMin))
    dt, dc = P["diffuser_layer"]
    diffuser = rect(tx0 + dc, ty0 + dc, tx1 - dc, ty1 - dc)
    return dict(recess=recess, outline=outline, holes=holes, clear=clear, white=white, blue=blue, diffuser=diffuser,
                hinge=hinge)


def build_overlay(L):
    """The film as solids, one per print colour, for the assembly and renders."""
    t, depth, _, _ = P["overlay"]
    z0 = E["top_z"] - depth
    sol = lambda f: f.extrude(V(0, 0, t)).translated(V(0, 0, z0))
    cut = Part.makeCompound([sol(h) for h in L["holes"]])
    film = sol(L["outline"]).cut(cut)
    clear = film.common(sol(L["clear"]))
    white = film.common(sol(L["white"]))
    blue = film.common(Part.makeCompound([sol(f) for f in L["blue"]]))
    black = film.cut([sol(L["clear"]), sol(L["white"])] + [sol(f) for f in L["blue"]])
    dt = P["diffuser_layer"][0]
    diffuser = L["diffuser"].extrude(V(0, 0, dt)).translated(V(0, 0, z0 - dt))
    return dict(black=black.removeSplitter(), blue=blue.removeSplitter(), white=white.removeSplitter(),
                clear=clear.removeSplitter(), diffuser=diffuser)


def connector_notches():
    """Jack and USB-C openings run down to the parting line, so the moving
    half forms them from below; the plug recess round USB-C runs down too.
    The receptacle's room behind it is open below already."""
    zs = E["seam_z"]
    jx, jz = E["jack_axis"]
    jr = E["jack_d"] / 2
    ux, uz = E["usb_center"]
    uw, uh = E["usb_size"]
    rw, rh, rd, rr = E["usb_recess"]
    y0, y1 = E["outer"][1], E["outer"][3]
    ye = ENC.usb_pocket_end()
    x0, x1, z1 = E["usb_room"]
    so = -P["shutoff"]  # the sides of each U are where the core meets the cavity: shut-off angle
    # Each U's straight sides run up to where its rounded top starts, as drawn
    # there, and open out toward the parting line.
    zu_top = uz + uh / 2 - E["usb_r"]
    zr_top = uz + rh / 2 - rr
    cuts = [Part.makeCylinder(jr, 6.0, V(jx, y0 - 1, jz), V(0, 1, 0)),
            taper(box(jx - jr, y0 - 1, zs - 1, jx + jr, y0 + 5, jz), jz, so),
            taper(box(x0, ye - 4.1, zs - 1, x1, ye, z1), z1, -P["cut_draft"]),
            ENC.stadium_y(ux, uz, uw, uh, E["usb_r"], ye - 0.1, y1 + 1),
            taper(box(ux - uw / 2, ye - 0.1, zs - 1, ux + uw / 2, y1 + 1, zu_top), zu_top, so),
            ENC.usb_recess(),
            taper(box(ux - rw / 2, y1 - rd, zs - 1, ux + rw / 2, y1 + 1, zr_top), zr_top, so)]
    return cuts


def build_housing(board, logo, comps):
    zs = E["seam_z"]
    pcb = ENC.outline(board)
    outer = envelope(zs)
    inner = envelope(zs - 1, P["wall"])
    h = ENC.solid(outer.cut(inner).removeSplitter())
    bosses, boss_holes = screw_bosses(inner)
    sens, sens_holes, sens_win = sensor_mount()
    chimney, bar_cuts = light_bar()
    slot, post = button()
    adds = bosses + oled_mount() + sens + [chimney, post] + battery_ribs() + [pcb_ribs(pcb, inner)]
    zu, rr = plate_under(), P["root_r"]
    filleted = [root_fillet(a, zu, rr) for a in adds]
    print("root fillets: %d of %d housing features" % (sum(f is not a for f, a in zip(filleted, adds)), len(adds)))
    adds = [a.common(inner) for a in filleted]  # nothing pokes through the walls (or into the plate)
    h = h.fuse(adds).removeSplitter()
    h = ENC.solid(h)
    (a0, a1) = E["sw_body"]
    fd, cd = P["fit_draft"], P["cut_draft"]
    cuts = [taper(ext(pcb_pocket_face(pcb).OuterWire, zs - 1, E["pcb_top_z"]), E["pcb_top_z"], -fd),
            taper(box(a0[0], a0[1], a0[2] - 1, a1[0], a1[1], a1[2]), a1[2], -cd)]
    cuts += [taper(c, c.BoundBox.ZMax, -fd) for c in ENC.slider_cuts()]
    cuts += connector_notches() + boss_holes + sens_holes + [sens_win] + bar_cuts
    cuts += [slot, glass_pocket(), housing_lip_cut()]
    cx, cy, w, ht, r, _ = E["viewport"]
    zt = E["top_z"]
    cuts.append(taper(ext(ENC.rounded_rect(cx - w / 2, cy - ht / 2, cx + w / 2, cy + ht / 2, r).OuterWire,
                          plate_under() - 1, zt + 1), zt, -cd))  # no chamfer: the film spans the edge
    L = overlay_faces(logo)
    _, depth, _, _ = P["overlay"]
    cuts.append(taper(ext(L["recess"].OuterWire, zt - depth, zt + 1), zt - depth, cd))  # opens toward the cavity
    if os.environ.get("BISECT"):
        for i, c in enumerate(cuts):
            h2 = h.cut(c)
            if not h2.isValid():
                b = c.BoundBox
                print("BISECT bad cut %d: %.1f-%.1f %.1f-%.1f %.1f-%.1f" % (i, b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
            else:
                h = h2
    h = ENC.solid(drop_slivers(h.cut(cuts).removeSplitter()))
    return h, L, pcb


# --- Cap -------------------------------------------------------------------


def cap_outline_at(z, inset):
    return ENC.outline_at(z, 0.0, inset)


def cap_shell(zb):
    """The cap's outside: the case outline at the seam, drawing in toward the
    rear face by the draft, with PR #13's chamfer round the rear edge."""
    zs = E["seam_z"]
    k = T(P["cap_edge_draft"])
    c = E["bottom_chamfer"]
    w = lambda z, extra=0.0: cap_outline_at(z, k * (zs - z) + extra).OuterWire
    s = Part.makeLoft([w(zb), w(zb + c)], True, True) if False else None
    s = Part.makeLoft([w(zb, c), w(zb + c), w(zs)], True, True)
    return ENC.solid(s.removeSplitter())


def lip_ring(a, b, ya, yb):
    f = ENC.plan_outline()
    return ENC.offset_face(f, -a).cut(ENC.offset_face(f, -b)).common(rect(-20, ya, 70, yb))


def housing_lip_cut():
    """The step in the bottom of the housing's long walls the cap's lip goes into."""
    zs = E["seam_z"]
    o, h, c, (ya, yb) = P["lip"]
    return taper(ext_faces(lip_ring(o, P["wall"] + 0.5, ya - c, yb + c), zs - 1, zs + h + c), zs + h + c, -P["cut_draft"])


def ext_faces(face, z0, z1):
    out = []
    for f in face.Faces:
        out.append(ext(f.OuterWire, z0, z1))
    return out[0].fuse(out[1:]) if len(out) > 1 else out[0]


def cap_rim(pcb):
    """The cap's lip: the inner part of the wall carried on up into the step
    in the housing's walls, so the two locate before the screws go in."""
    zs = E["seam_z"]
    o, h, c, (ya, yb) = P["lip"]
    return taper(ext_faces(lip_ring(o + c, P["wall"] - c, ya, yb), zs - 0.01, zs + h), zs, -P["rib_draft"])


def cap_fillers():
    """Tabs that rise into the bottoms of the jack and USB-C notches."""
    zs = E["seam_z"]
    c = P["notch_clear"]
    jx, jz = E["jack_axis"]
    jr = E["jack_d"] / 2
    ux, uz = E["usb_center"]
    uw, uh = E["usb_size"]
    rd = E["usb_recess"][2]
    y0, y1 = E["outer"][1], E["outer"][3]
    ye = ENC.usb_pocket_end()
    # standing up from the cap, so they narrow toward their tops, at the
    # notches' shut-off angle; the gap to the notch stays c at the seam
    so = -P["shutoff"]
    jt = taper(box(jx - jr + c, y0 + 0.05, zs - 0.3, jx + jr - c, y0 + P["wall"] - 0.15, jz - jr - c), zs, so).cut(
        Part.makeCylinder(jr + c, 6.0, V(jx, y0 - 1, jz), V(0, 1, 0)))
    ut = taper(box(ux - uw / 2 + c, ye + c, zs - 0.3, ux + uw / 2 - c, y1 - rd, uz - uh / 2 - c), zs, so)
    return [jt, ut]


def build_cap(pcb, cups=False):
    zs, zp = E["seam_z"], E["pcb_bottom_z"]
    extra = E["cup_cover_extra"] if cups else 0.0
    zf = zp - E["cover_thickness"]  # rear face of the plain cap; screw heads sit here
    zb = zf - extra
    shell = cap_shell(zb)
    fl = P["cap_floor"]
    # Hollow it to a tray: floor, and a wall round the edge up to the seam.
    hollow = dprism(ENC.offset_face(ENC.plan_outline(), -P["wall"] + P["lip"][2]), zs + 1, zb + fl, P["draft_in"])
    cap = shell.cut(hollow)
    adds = [cap_rim(pcb)]
    floor_feats = []
    holes = []
    zr = zp - E["cover_relief"]
    for x, y in E["screw_axes"]:
        floor_feats.append(dpost(x, y, P["cap_boss_od"], zb + fl - 0.01, zp))
        holes.append(taper(zcyl(x, y, E["screw_clear_d"], zb - 1, zp + 1), zp + 1, -P["fit_draft"]))
        r = E["csk_d"] / 2
        h = (r - E["screw_clear_d"] / 2) / math.tan(math.radians(E["csk_angle"] / 2))
        lead = 0.0 if cups else 0.5  # in the cup cap the countersink starts at the counterbore's floor
        holes.append(Part.makeCone(r + lead * math.tan(math.radians(E["csk_angle"] / 2)), E["screw_clear_d"] / 2,
                                   h + lead, V(x, y, zf - lead)))
        if cups:
            holes.append(taper(zcyl(x, y, E["cup_counterbore_d"], zb - 1, zf), zf, -P["cut_draft"]))
    adds += cap_fillers()
    if cups:
        housings, kh = keyhole_housings(zb, zr)
        floor_feats += housings
        holes += kh
    floor_feats = [root_fillet(f, zb + fl, P["root_r"], down=False).common(shell) for f in floor_feats]
    adds += floor_feats
    cap = cap.fuse(adds).removeSplitter()
    groove = ENC.slider_cuts()[0]
    cap = cap.cut(holes + [taper(groove, groove.BoundBox.ZMin, P["fit_draft"])])  # opens toward the cap's core
    # nothing above the PCB's back face except the rim and the fillers
    keep = box(-20, -20, zb - 1, 70, 120, zp)
    above = Part.makeCompound([cap_rim(pcb)] + cap_fillers())
    cap = cap.common(keep).fuse(above.cut(Part.makeCompound(holes))).removeSplitter()
    return ENC.solid(drop_slivers(cap))


def keyhole_housings(zb, zr):
    """The keyholes of PR #13's cup cover, in housings that stand on the
    floor, moulded without side actions: the slot, the entry and the click
    pocket go straight through from the rear (formed by the fixed half), and
    the lands the cup heads bear on are formed from above, through windows in
    the roof. What is left of the roof covers the entry, the slot and the
    pocket, so looking in through a keyhole you still see the roof, not the PCB."""
    w = P["cup_wall"]
    re = E["cup_entry_d"] / 2
    zl = zb + E["cup_land"]
    _, ht, hc = E["cup_head"]
    zc = zl + ht + hc  # chamber ceiling, roof underside
    rt = E["cup_roof"][0]
    z0 = zb
    pins = [taper(zcyl(x, y, d + 2 * E["cup_roof"][2], z0 - 1, zr + 1), zb, P["cut_draft"]) for x, y, d in E["cup_keepout"]]
    housings, holes = [], []
    zroof = min(zc + rt, zr)
    cd, so = P["cut_draft"], P["shutoff"]
    for k in E["cup_keys"]:
        c, u, e = ENC.cup_key(k)
        outer = taper(ENC.stadium(k, re + w, zb + 0.01, zroof), zb, -P["rib_draft"])  # stands on the floor
        housings.append(outer.cut(pins))
    # PR #13's keyhole cuts, in the order cup_keyholes() makes them: the
    # entry, click pocket and slot go through from the rear (fixed half), so
    # they open toward the rear face; the head's chamber over the land is
    # formed from above, so it opens upward.
    kh = ENC.cup_keyholes(zb)
    for i in range(0, len(kh), 5):
        entry, pocket, slot, room, band = kh[i:i + 5]
        holes += [taper(entry, zc, -cd), taper(pocket, zl + 1, -cd), taper(slot, zl + 1, -cd),
                  taper(room, zl, cd), taper(band, zl, cd)]
    # windows over the lands: the chamber (carried on up at the same draft),
    # less what the roof still covers over the through holes; where the roof
    # meets a window is a shut-off
    dp = E["cup_snap"][0]
    for k in E["cup_keys"]:
        c, u, e = ENC.cup_key(k)
        chamber = taper(ENC.stadium(k, re, zc - 0.01, zroof + 1), zl, cd)
        # no window past the entry's centre, so the roof over the entry stays
        # joined to the end wall however the window's draft opens it out
        chamber = chamber.common(ENC.band(e, e + u * 60, 30, zc - 1, zroof + 2))
        through = [zcyl(e.x, e.y, 2 * re, zc - 1, zroof + 2), zcyl(c.x, c.y, dp, zc - 1, zroof + 2),
                   ENC.band(e, c, E["cup_slot_w"] / 2, zc - 1, zroof + 2)]
        holes.append(chamber.cut([taper(t, zc, -so) for t in through]))
    return housings, holes


# --- Switch cover, diffuser ------------------------------------------------


def build_slider():
    """PR #13's switch cover, redrawn to pull along X: the parting line is
    the flange's inner face, so every side face narrows toward +X (the grip),
    the finger ridges open toward +X and the lever's pocket opens toward -X.
    The pocket is closed below: the cover goes on S1's lever before the PCB
    drops in."""
    g = ENC.slider_geom()
    ya = E["act_y"]
    xo = E["outer"][2] + E["grip_proud"]
    X = (1, 0, 0)
    d = -P["fit_draft"]
    flange = taper(box(g["xi"], ya - g["fl"] / 2, g["fz0"], g["xf"], ya + g["fl"] / 2, g["fz1"]), g["xi"], d, X)
    grip = taper(box(g["xf"] - 0.01, ya - g["gl"] / 2, g["wz0"], xo, ya + g["gl"] / 2, g["wz1"]), g["xi"], d, X)
    try:
        outer = [e for e in grip.Edges if e.BoundBox.XMin > xo - 1e-3]
        grip = grip.makeFillet(0.6, outer)
    except Exception as ex:
        print("grip fillet skipped:", ex)
    s = flange.fuse(grip)
    for dy in (-1.5, 0.0, 1.5):  # finger ridges
        s = s.cut(taper(box(xo - 0.35, ya + dy - 0.3, g["wz0"] - 1, xo + 1, ya + dy + 0.3, g["wz1"] + 1), xo - 0.35,
                        P["cut_draft"], X))
    z0, z1 = E["act_z"]
    w, c = E["act_w"] + 0.4, P["slider_lever_clear"]
    xb = E["act_tip_x"] + 0.4
    s = s.cut(taper(box(g["xi"] - 1, ya - w / 2, z0 - c, xb, ya + w / 2, z1 + c), xb, -P["cut_draft"], X))
    return s.removeSplitter()


# --- Build -----------------------------------------------------------------


def components(doc):
    names = ["BoardRev4", "OLEDPCB", "OLEDHeader", "OLEDHeaderPins", "OLEDFlex", "OLEDRearICs", "Part__Feature005",
             "SensorPCB", "SensorOpticalCase", "SensorLenses", "SensorConnector", "BatteryPouch", "BatteryTape",
             "Part__Feature002", "Part__Feature003", "Part__Feature006", "PCB_J5", "PCB_J2", "PCB_J6", "PCB_S2",
             "PCB_M1", "PCB_U5", "PCB_U6", "PCB_U7", "SensorScrew1", "SensorScrew2",
             "BatteryLead1", "BatteryLead2"] + ["HarnessWire%d" % i for i in range(1, 8)]
    names += [o.Name for o in doc.Objects if o.Name.startswith("PCB_") and o.Name not in names]
    out = {}
    for n in names:
        o = doc.getObject(n)
        if o is not None and hasattr(o, "Shape") and not o.Shape.isNull():
            out[n] = (o.Label, o.Shape.copy())
    return out


def build_all():
    doc = App.openDocument(ASSY)
    board = doc.getObject("BoardRev4").Shape
    logo = doc.getObject("LogoInlay").Shape
    comps = components(doc)
    housing, layers, pcb = build_housing(board, logo, comps)
    overlay = build_overlay(layers)
    cap = build_cap(pcb)
    cup_cap = build_cap(pcb, cups=True)
    slider = build_slider()
    screws = [doc.getObject("PCBMountScrew%d" % i).Shape.copy() for i in range(1, 5)]
    cups = [doc.getObject("SuctionCup%d" % i).Shape.copy() for i in (1, 2)]
    return dict(housing=housing, layers=layers, overlay=overlay, cap=cap, cup_cap=cup_cap, slider=slider,
                screws=screws, cups=cups, comps=comps, doc=doc)


def checks(g):
    out = []
    for k in ("housing", "cap", "cup_cap", "slider"):
        s = g[k]
        out.append("CHECK %s valid %s, %d solids, %.1f cm3" % (k, s.isValid(), len(s.Solids), s.Volume / 1000))
    film = Part.makeCompound(list(g["overlay"].values()))
    out.append("CHECK overlay to housing %.3f mm3 overlap, film top %.2f under the top face" % (
        film.common(g["housing"]).Volume, E["top_z"] - film.BoundBox.ZMax))
    parts = {"housing": g["housing"], "overlay": film, "cap": g["cap"], "cup_cap": g["cup_cap"], "slider": g["slider"]}
    for name, (label, s) in g["comps"].items():
        for pn, p in parts.items():
            try:
                v = p.common(s).Volume
            except Exception:
                v = -1
            if abs(v) > 0.01:
                out.append("CHECK overlap %s / %s: %.2f mm3" % (pn, label, v))
    for i, s in enumerate(g["screws"]):
        out.append("CHECK screw %d in housing %.2f mm3, in cup cap %.2f mm3" % (
            i + 1, g["housing"].common(s).Volume, g["cup_cap"].common(s).Volume))
    for i, c in enumerate(g["cups"]):
        out.append("CHECK cup %d in cup cap %.2f mm3" % (i + 1, g["cup_cap"].common(c).Volume))
    return out


def overlay_json(L, path):
    """Polylines of the overlay's layers, for overlay_dxf.py."""
    import json

    def loops(faces):
        out = []
        for f in faces:
            for w in f.Wires:
                pts = w.discretize(Deflection=0.01)
                out.append([(round(p.x, 4), round(p.y, 4)) for p in pts])
        return out

    data = {"CUT_OUTLINE": loops([L["outline"]]), "CUT_HOLES": loops(L["holes"]), "PRINT_CLEAR": loops([L["clear"]]),
            "PRINT_WHITE": loops([L["white"]]), "PRINT_BLUE": loops(L["blue"]), "RECESS": loops([L["recess"]]),
            "NO_ADHESIVE": loops([L["clear"], L["white"], L["hinge"]]),
            "DIFFUSER_LAYER": loops([L["diffuser"]])}
    json.dump(data, open(path, "w"))


def export(g):
    os.makedirs(PARTS, exist_ok=True)
    import Mesh
    files = {"Housing-Black": g["housing"], "Cap-Black": g["cap"], "Cap-Cups-Black": g["cup_cap"],
             "Switch-Cover-Blue": g["slider"]}
    files.update({"Overlay-" + k.capitalize(): s for k, s in g["overlay"].items()})
    for n, s in files.items():
        s.exportStep(os.path.join(PARTS, n + ".step"))
        m = Mesh.Mesh(s.tessellate(0.02))
        m.write(os.path.join(PARTS, n + ".stl"))
    # references for renders and checks
    ref = os.path.join(HERE, "build")
    os.makedirs(ref, exist_ok=True)
    for name, (label, s) in g["comps"].items():
        Mesh.Mesh(s.tessellate(0.05)).write(os.path.join(ref, name + ".stl"))
    for i, s in enumerate(g["screws"]):
        Mesh.Mesh(s.tessellate(0.05)).write(os.path.join(ref, "Screw%d.stl" % (i + 1)))
    for i, s in enumerate(g["cups"]):
        Mesh.Mesh(s.tessellate(0.1)).write(os.path.join(ref, "Cup%d.stl" % (i + 1)))
    keep = ("BoardRev4", "OLEDPCB", "Part__Feature005", "SensorPCB", "SensorOpticalCase", "BatteryPouch", "Part__Feature002",
            "PCB_J5", "Part__Feature006", "PCB_S2", "PCB_M1")
    overlay_json(g["layers"], os.path.join(PARTS, "Overlay-Layers.json"))
    asm = [g["housing"], g["cup_cap"], g["slider"]] + list(g["overlay"].values()) + g["screws"] + g["cups"]
    asm += [g["comps"][n][1] for n in keep if n in g["comps"]]
    Part.makeCompound(asm).exportStep(os.path.join(HERE, "DTT-Molded.step"))


if __name__ == "__main__" or any(a.endswith("build_molded_case.py") for a in sys.argv):  # freecadcmd runs it under its module name
    g = build_all()
    export(g)
    with open(os.path.join(HERE, "build", "checks.txt"), "w") as f:
        f.write("\n".join(checks(g)) + "\n")
    os._exit(0)
