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
    "rib": 1.0,  # rib thickness, about 60 % of the wall, so no sink on the top face
    # The top plate is a full wall thick (underside 12.57, as before); the
    # OLED glass, whose face is at 12.77, gets a shallow pocket.
    "glass_pocket": (8.1, 37.8, 33.9, 53.2, 0.2, 12.82),  # glass x0, y0, x1, y1, clearance round it, pocket ceiling z
    # PCB screw bosses: the original 0408LTFB (#4) thread-forming screws.
    "boss_od": 5.6,  # about 2 x the 2.84 mm thread
    "boss_hole": 2.5,  # pilot; check the screw maker's chart for PC/ABS (often 0.8 x d = 2.3)
    "boss_hole_top": 7.0,  # cored up to here, short of the plate, so no thick lump under the top face
    "boss_rib": True,  # tie each boss to the side wall with a rib
    # PCB locating ribs on the inside of the walls, plate to seam, 0.3 off the PCB edge.
    "pcb_ribs_y": (14.0, 45.0, 58.0),  # both long sides
    # OLED: four posts through its mounting holes, heat-staked, on standoffs
    # that hold the glass 0.05 off its pocket.
    "oled_holes": ((9.25, 33.64), (32.75, 33.64), (9.25, 57.44), (32.75, 57.44)),
    "oled_board_top": 10.77,
    "oled_board_back": 9.57,
    "stake": (1.8, 0.8),  # post diameter (OLED hole about 2.0), length past the board's back (0.97 to the cell under the button-end holes)
    "standoff_d": 3.2,
    "oled_key": (11.5, 34.7, 15.5, 35.7, 11.2),  # rib where the flex would be if the module went in turned round
    # Distance sensor: its own two screws into bosses, a window round its
    # optical case, and a key rib.
    "sensor_pcb_top": 3.67,
    "sensor_screws": ((9.3, 16.9), (32.7, 10.3)),
    "sensor_boss": (3.8, 1.6),  # OD, pilot (assumed M2 thread-forming; the original screws are unknown)
    "sensor_window": (11.4, 9.6, 30.6, 17.6, 0.15),  # optical case x0, y0, x1, y1, clearance
    "sensor_key": (9.5, 7.0, 16.0, 8.0, 0.6),  # x0, y0, x1, y1, bottom z
    # LED light bar: a window with a ledge for the white diffuser, which goes
    # in from inside, and a chimney round the LEDs.
    "diffuser_throat": (7.0, 20.5, 35.0, 27.5),
    "diffuser_seat": (6.0, 19.5, 36.0, 28.5, 13.57),
    "chimney": 4.0,  # bottom z of a rib-thick wall round the seat, clear of the sensor PCB and the harness
    # Battery: located by ribs, held on two strips of double-sided tape on
    # the lands over it (printed clips are undercuts).
    "battery": (8.2, 54.7, 28.2, 89.7, 1.6, 8.6),
    "tape": 0.15,
    "battery_lands_y": (61.0, 68.0, 75.0, 82.0, 88.0),
    "battery_side_ribs": ((-1, 64.0), (-1, 78.0), (-1, 86.0), (1, 78.0), (1, 86.0)),  # side, y
    "battery_rib_bottom": 4.5,
    "battery_gap": 0.25,
    # Button: the flexure as in PR #13 (U slot through the plate), the post
    # now 0.3 over S2's plunger, since a moulding holds that tolerance.
    "button_post_gap": 0.3,
    "s2_top": -0.2,
    # Blue second shot (two-shot moulding): the logo and the button pad, 0.8 deep.
    "shot2_depth": 0.8,
    # Connector openings run down to the parting line (U notches), so no
    # slides: the B half forms them from below. The cap fills them back up.
    "notch_clear": 0.05,
    # Cap.
    "cap_floor": 1.6,
    "cap_edge_draft": 1.0,
    "lip": (0.8, 1.0, 0.05, (8.0, 74.0)),  # lip joint on the long sides: housing keeps the outer 0.8 of its wall for the last 1.0 mm; the cap's lip fills the rest, with this clearance; y range
    "cap_boss_od": 7.0,  # round the countersink, up to the PCB
    "cup_wall": 1.6,  # keyhole housings in the cup cap
}
P = PARAMS


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
    f1 = ENC.offset_face(face, -d) if d > 1e-4 else face
    w1 = f1.OuterWire.copy()
    w1.translate(V(0, 0, z_tip - w1.BoundBox.ZMin))
    return Part.makeLoft([w0, w1], True, True)


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


def plate_under():
    return E["top_z"] - P["wall"]


def pcb_ribs(pcb, inner):
    """Ribs on the inside of each long wall, stopping 0.3 off the PCB's edge.
    They hang full height from the plate: a rib that stood up from the open
    edge would have its top face toward the plate, an undercut for the core."""
    zs = E["seam_z"]
    pocket = ext(ENC.pcb_pocket(pcb).OuterWire, zs - 1, E["top_z"] + 1)
    ribs = []
    t = P["rib"]
    for y in P["pcb_ribs_y"]:
        for xa, xb in ((-10, 21), (21, 52)):
            ribs.append(drib(xa, y - t / 2, xb, y + t / 2, plate_under() + 0.3, zs))
    return Part.makeCompound(ribs).cut(pocket)


def screw_bosses(inner_wall):
    zu, zp = plate_under(), E["pcb_top_z"]
    out, holes = [], []
    for x, y in E["screw_axes"]:
        out.append(dpost(x, y, P["boss_od"], zu + 0.3, zp))
        holes.append(dhole(x, y, P["boss_hole"], zp - 0.1, P["boss_hole_top"], 0.25))
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
    for x, y in P["oled_holes"]:
        parts.append(dpost(x, y, P["standoff_d"], zu + 0.3, zt))
        parts.append(dpost(x, y, d, zt + 0.01, zb - past, 0.25))
    kx0, ky0, kx1, ky1, kz = P["oled_key"]
    parts.append(drib(kx0, ky0, kx1, ky1, zu + 0.3, kz))
    return parts


def glass_pocket():
    x0, y0, x1, y1, c, zc = P["glass_pocket"]
    return box(x0 - c, y0 - c, plate_under() - 0.5, x1 + c, y1 + c, zc)


def sensor_mount():
    zu, zp = plate_under(), P["sensor_pcb_top"]
    od, pilot = P["sensor_boss"]
    parts, holes = [], []
    for x, y in P["sensor_screws"]:
        parts.append(dpost(x, y, od, zu + 0.3, zp))
        holes.append(dhole(x, y, pilot, zp - 0.1, zp + 6.0, 0.25))
    kx0, ky0, kx1, ky1, kz = P["sensor_key"]
    parts.append(drib(kx0, ky0, kx1, ky1, zu + 0.3, kz))
    x0, y0, x1, y1, c = P["sensor_window"]
    window = box(x0 - c, y0 - c, zu - 1, x1 + c, y1 + c, E["top_z"] + 1)
    return parts, holes, window


def light_bar():
    zu = plate_under()
    tx0, ty0, tx1, ty1 = P["diffuser_throat"]
    sx0, sy0, sx1, sy1, sz = P["diffuser_seat"]
    cz = P["chimney"]
    t = P["rib"]
    outer = dprism(rect(sx0 - t, sy0 - t, sx1 + t, sy1 + t), zu + 0.3, cz)
    inner = dprism(rect(sx0, sy0, sx1, sy1), zu + 1, cz - 1, -P["rib_draft"])  # opens toward the core
    chimney = outer.cut(inner)
    cuts = [box(tx0, ty0, zu - 1, tx1, ty1, E["top_z"] + 1), box(sx0, sy0, zu - 1, sx1, sy1, sz)]
    return chimney, cuts


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
    slot = ext(ENC.button_slot_face(zu - 1).OuterWire, zu - 1, E["top_z"] + 1)
    post = dpost(px, py, E["button_post"][0], zu + 0.3, P["s2_top"] + P["button_post_gap"])
    return slot, post


def shot2(logo):
    """Blue second shot: the logo's outline and the button pad, shot2_depth deep."""
    zt, d = E["top_z"], P["shot2_depth"]
    tops = [f for f in logo.Faces if f.normalAt(0, 0).z > 0.99 and abs(f.CenterOfMass.z - zt) < 1e-3]
    blue = [f.extrude(V(0, 0, -d)) for f in tops]
    px, py, pr = E["button_pad"]
    blue.append(zcyl(px, py, 2 * pr, zt - d, zt))
    return blue


def connector_notches():
    """Jack and USB-C openings run down to the parting line, so the moving
    half forms them from below; the plug recess round USB-C runs down too.
    The receptacle's room behind it is open below already."""
    zs = E["seam_z"]
    jx, jz = E["jack_axis"]
    jr = E["jack_d"] / 2
    ux, uz = E["usb_center"]
    uw, uh = E["usb_size"]
    rw, rh, rd, _ = E["usb_recess"]
    y0, y1 = E["outer"][1], E["outer"][3]
    ye = ENC.usb_pocket_end()
    x0, x1, z1 = E["usb_room"]
    cuts = [Part.makeCylinder(jr, 6.0, V(jx, y0 - 1, jz), V(0, 1, 0)),
            box(jx - jr, y0 - 1, zs - 1, jx + jr, y0 + 5, jz),
            box(x0, ye - 4.1, zs - 1, x1, ye, z1),
            ENC.stadium_y(ux, uz, uw, uh, E["usb_r"], ye - 0.1, y1 + 1),
            box(ux - uw / 2, ye - 0.1, zs - 1, ux + uw / 2, y1 + 1, uz),
            ENC.usb_recess(),
            box(ux - rw / 2, y1 - rd, zs - 1, ux + rw / 2, y1 + 1, uz)]
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
    adds = [a.common(inner) for a in adds]  # nothing pokes through the walls
    h = h.fuse(adds).removeSplitter()
    h = ENC.solid(h)
    (a0, a1) = E["sw_body"]
    cuts = [ext(ENC.pcb_pocket(pcb).OuterWire, zs - 1, E["pcb_top_z"]),
            box(a0[0], a0[1], a0[2] - 1, a1[0], a1[1], a1[2])]
    cuts += ENC.slider_cuts() + connector_notches() + boss_holes + sens_holes + [sens_win] + bar_cuts
    cuts += [slot, glass_pocket(), housing_lip_cut()]
    cx, cy, w, ht, r, c = E["viewport"]
    zt = E["top_z"]
    rr = lambda d, z: ENC.rounded_rect(cx - w / 2 - d, cy - ht / 2 - d, cx + w / 2 + d, cy + ht / 2 + d, r + d, z).OuterWire
    cuts += [ext(rr(0, 0), plate_under() - 1, zt - c + 0.01), Part.makeLoft([rr(0, zt - c), rr(c, zt)], True, True),
             ext(rr(c, 0), zt - 0.01, zt + 1)]
    h = ENC.solid(h.cut(cuts).removeSplitter())
    blue = Part.makeCompound(shot2(logo)).common(h)
    h = ENC.solid(h.cut(blue).removeSplitter())
    return h, blue.removeSplitter(), pcb


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
    return ext_faces(lip_ring(o, P["wall"] + 0.5, ya - c, yb + c), zs - 1, zs + h + c)


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
    return dprism(lip_ring(o + c, P["wall"] - c, ya, yb), zs - 0.01, zs + h)


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
    jt = box(jx - jr + c, y0 + 0.05, zs - 0.01, jx + jr - c, y0 + P["wall"] - 0.05, jz - jr - c).cut(
        Part.makeCylinder(jr + c, 6.0, V(jx, y0 - 1, jz), V(0, 1, 0)))
    ut = box(ux - uw / 2 + c, ye + c, zs - 0.01, ux + uw / 2 - c, y1 - rd, uz - uh / 2 - c)
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
    holes = []
    zr = zp - E["cover_relief"]
    for x, y in E["screw_axes"]:
        adds.append(dpost(x, y, P["cap_boss_od"], zb + fl - 0.01, zp))
        holes.append(zcyl(x, y, E["screw_clear_d"], zb - 1, zp + 1))
        r = E["csk_d"] / 2
        h = (r - E["screw_clear_d"] / 2) / math.tan(math.radians(E["csk_angle"] / 2))
        lead = 0.0 if cups else 0.5  # in the cup cap the countersink starts at the counterbore's floor
        holes.append(Part.makeCone(r + lead * math.tan(math.radians(E["csk_angle"] / 2)), E["screw_clear_d"] / 2,
                                   h + lead, V(x, y, zf - lead)))
        if cups:
            holes.append(zcyl(x, y, E["cup_counterbore_d"], zb - 1, zf))
    adds += cap_fillers()
    if cups:
        housings, kh = keyhole_housings(zb, zr)
        adds += housings
        holes += kh
    cap = cap.fuse(adds).removeSplitter()
    cap = cap.cut(holes + ENC.slider_cuts()[:1])
    # nothing above the PCB's back face except the rim and the fillers
    keep = box(-20, -20, zb - 1, 70, 120, zp)
    above = Part.makeCompound([cap_rim(pcb)] + cap_fillers())
    cap = cap.common(keep).fuse(above.cut(Part.makeCompound(holes))).removeSplitter()
    return ENC.solid(cap)


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
    pins = [zcyl(x, y, d + 2 * E["cup_roof"][2], z0 - 1, zr + 1) for x, y, d in E["cup_keepout"]]
    housings, holes = [], []
    zroof = min(zc + rt, zr)
    for k in E["cup_keys"]:
        c, u, e = ENC.cup_key(k)
        outer = ENC.stadium(k, re + w, zb + 0.01, zroof)
        housings.append(outer.cut(pins))
    holes += ENC.cup_keyholes(zb)
    # windows over the lands: the chamber, less what the through holes cover
    dp = E["cup_snap"][0]
    for k in E["cup_keys"]:
        c, u, e = ENC.cup_key(k)
        chamber = ENC.stadium(k, re, zc - 0.01, zroof + 1)
        through = [zcyl(e.x, e.y, 2 * re, zc - 1, zroof + 2), zcyl(c.x, c.y, dp, zc - 1, zroof + 2),
                   ENC.band(e, c, E["cup_slot_w"] / 2, zc - 1, zroof + 2)]
        holes.append(chamber.cut(through))
    return housings, holes


# --- Switch cover, diffuser ------------------------------------------------


def build_slider():
    """PR #13's switch cover; it already pulls straight along X. Draft still to add."""
    return ENC.build_slider()


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
    housing, blue, pcb = build_housing(board, logo, comps)
    cap = build_cap(pcb)
    cup_cap = build_cap(pcb, cups=True)
    slider = build_slider()
    diffuser = doc.getObject("Diffuser").Shape.copy()
    screws = [doc.getObject("PCBMountScrew%d" % i).Shape.copy() for i in range(1, 5)]
    cups = [doc.getObject("SuctionCup%d" % i).Shape.copy() for i in (1, 2)]
    return dict(housing=housing, blue=blue, cap=cap, cup_cap=cup_cap, slider=slider, diffuser=diffuser,
                screws=screws, cups=cups, comps=comps, doc=doc)


def checks(g):
    out = []
    for k in ("housing", "blue", "cap", "cup_cap", "slider"):
        s = g[k]
        out.append("CHECK %s valid %s, %d solids, %.1f cm3" % (k, s.isValid(), len(s.Solids), s.Volume / 1000))
    parts = {"housing": g["housing"], "blue": g["blue"], "cap": g["cap"], "cup_cap": g["cup_cap"], "slider": g["slider"]}
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


def export(g):
    os.makedirs(PARTS, exist_ok=True)
    import Mesh
    files = {"Housing-Black": g["housing"], "Housing-Shot2-Blue": g["blue"], "Cap-Black": g["cap"],
             "Cap-Cups-Black": g["cup_cap"], "Switch-Cover-Blue": g["slider"], "Diffuser-White": g["diffuser"]}
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
    asm = [g["housing"], g["blue"], g["cup_cap"], g["slider"], g["diffuser"]] + g["screws"] + g["cups"]
    asm += [g["comps"][n][1] for n in keep if n in g["comps"]]
    Part.makeCompound(asm).exportStep(os.path.join(HERE, "DTT-Molded.step"))


if __name__ == "__main__" or any(a.endswith("build_molded_case.py") for a in sys.argv):  # freecadcmd runs it under its module name
    g = build_all()
    export(g)
    with open(os.path.join(HERE, "build", "checks.txt"), "w") as f:
        f.write("\n".join(checks(g)) + "\n")
    os._exit(0)
