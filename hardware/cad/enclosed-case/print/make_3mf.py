"""Build a Bambu Studio project (3MF) of the PR #13 printed parts.

Run from the repo root:  python3 hardware/cad/enclosed-case/print/make_3mf.py
Needs trimesh and numpy. Writes DTT-Enclosed-Print.3mf next to this file.
With "stepped" after it, writes DTT-Enclosed-Stepped-Print.3mf from
../stepped/parts: plate 1 only, as the stepped case doesn't fit the sleeve.

Filaments follow Lucy's AMS: 1 blue, 2 white (diffuser), 3 black.
Plates (256 x 256 bed): 1 the case with both rear caps (flat and suction-cup;
delete the one you don't want), 2 the sleeve backplate and wall bracket. Two
plates keep Bambu's plate grid a single row. Each part is turned to its print face.
"""
import os
import sys
import uuid
import zipfile

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
STEPPED = "stepped" in sys.argv[1:]
CASE = os.path.join(HERE, "..", "stepped" if STEPPED else "", "parts")
SNAP = os.path.join(HERE, "..", "..", "..", "production-exports", "cad", "snap-backplate")
OUT = os.path.join(HERE, "DTT-Enclosed-Stepped-Print.3mf" if STEPPED else "DTT-Enclosed-Print.3mf")

BLUE, WHITE, BLACK = 1, 2, 3
BED, PLATE_GAP = 256.0, 307.2  # plate N sits (N-1) * 307.2 mm right of plate 1

FLIP = trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0])        # top face down
SIDE = trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0])   # -X face down
NONE = np.eye(4)

# (object name, [(part name, file, filament)], rotation, plate, bed x, bed y, extra settings)
OBJECTS = [
    ("Housing", [("Housing-Black", f"{CASE}/Housing-Black.stl", BLACK),
                 ("Housing-Inlays-Blue", f"{CASE}/Housing-Inlays-Blue.stl", BLUE),
                 ("Housing-Diffuser-White", f"{CASE}/Housing-Diffuser-White.stl", WHITE)],
     FLIP, 1, 38, 120, {}),
    ("Rear-Cover", [("Rear-Cover-Black", f"{CASE}/Rear-Cover-Black.stl", BLACK)],
     NONE, 1, 98, 120, {}),
    ("Switch-Cover", [("Switch-Cover-Blue", f"{CASE}/Switch-Cover-Blue.stl", BLUE)],
     SIDE, 1, 225, 120, {}),
    ("Rear-Cover-Cups", [("Rear-Cover-Cups-Black", f"{CASE}/Rear-Cover-Cups-Black.stl", BLACK)],
     NONE, 1, 162, 120, {"wall_loops": "4"}),
    ("Snap-Backplate", [("Snap-Backplate-Black", f"{SNAP}/DTT-Snap-Backplate-Black.stl", BLACK),
                        ("Snap-Backplate-Blue", f"{SNAP}/DTT-Snap-Backplate-Blue.stl", BLUE)],
     NONE, 2, 85, 120, {"wall_loops": "4"}),
    ("Wall-Bracket", [("Wall-Bracket-Black", f"{SNAP}/DTT-Snap-Backplate-Wall-Bracket.stl", BLACK)],
     NONE, 2, 170, 120, {"wall_loops": "4"}),
]
if STEPPED:
    OBJECTS = [o for o in OBJECTS if o[3] == 1]

NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
      'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
      'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"')
APP = "BambuStudio-02.08.02.61"


def uid():
    return str(uuid.uuid4())


def mesh_xml(oid, m):
    v = "\n".join(f'     <vertex x="{a:.5f}" y="{b:.5f}" z="{c:.5f}"/>' for a, b, c in m.vertices)
    t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
    return (f'  <object id="{oid}" p:UUID="{uid()}" type="model">\n   <mesh>\n    <vertices>\n{v}\n'
            f'    </vertices>\n    <triangles>\n{t}\n    </triangles>\n   </mesh>\n  </object>')


def build():
    placed = []  # (name, plate, [(part name, mesh, filament)], settings, translation)
    for name, parts, rot, plate, x, y, extra in OBJECTS:
        meshes = []
        for pname, path, fil in parts:
            m = trimesh.load(path)
            m.apply_transform(rot)
            meshes.append((pname, m, fil))
        lo = np.min([m.bounds[0] for _, m, _ in meshes], axis=0)
        hi = np.max([m.bounds[1] for _, m, _ in meshes], axis=0)
        centre = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
        for _, m, _ in meshes:
            m.apply_translation(-centre)  # object origin: footprint centre, on the bed
        size = hi - lo
        assert size[0] / 2 < min(x, BED - x) and size[1] / 2 < min(y, BED - y), name
        placed.append((name, plate, meshes, extra, (x + (plate - 1) * PLATE_GAP, y)))
    return placed


def write(placed):
    files = {}
    obj_xml, comp_ids, next_id = [], {}, 1
    for name, _, meshes, _, _ in placed:
        ids = []
        for pname, m, _ in meshes:
            obj_xml.append(mesh_xml(next_id, m))
            ids.append(next_id)
            next_id += 1
        comp_ids[name] = ids
    files["3D/Objects/object_1.model"] = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {NS} '
        f'requiredextensions="p">\n <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
        + "\n".join(obj_xml) + "\n </resources>\n <build/>\n</model>\n")

    res, items, cfg_objs, plates = [], [], [], {}
    for name, plate, meshes, extra, (tx, ty) in placed:
        oid = next_id
        next_id += 1
        comps = "\n".join(
            f'    <component p:path="/3D/Objects/object_1.model" objectid="{cid}" p:UUID="{uid()}" '
            f'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' for cid in comp_ids[name])
        res.append(f'  <object id="{oid}" p:UUID="{uid()}" type="model">\n   <components>\n{comps}\n'
                   f'   </components>\n  </object>')
        items.append(f'  <item objectid="{oid}" p:UUID="{uid()}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.3f} {ty:.3f} 0" printable="1"/>')
        parts = []
        for (pname, m, fil), cid in zip(meshes, comp_ids[name]):
            parts.append(
                f'    <part id="{cid}" subtype="normal_part">\n'
                f'      <metadata key="name" value="{pname}"/>\n'
                f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                f'      <metadata key="source_file" value="{pname}.stl"/>\n'
                f'      <metadata key="extruder" value="{fil}"/>\n'
                f'      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                f'facets_reversed="0" backwards_edges="0"/>\n    </part>')
        settings = "".join(f'    <metadata key="{k}" value="{v}"/>\n' for k, v in extra.items())
        cfg_objs.append(f'  <object id="{oid}">\n    <metadata key="name" value="{name}"/>\n'
                        f'    <metadata key="extruder" value="{meshes[0][2]}"/>\n{settings}'
                        + "\n".join(parts) + "\n  </object>")
        plates.setdefault(plate, []).append(oid)

    files["3D/3dmodel.model"] = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {NS} '
        f'requiredextensions="p">\n <metadata name="Application">{APP}</metadata>\n'
        f' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f' <metadata name="Title">DTT enclosed case print (PR #13)</metadata>\n <resources>\n'
        + "\n".join(res) + f'\n </resources>\n <build p:UUID="{uid()}">\n' + "\n".join(items)
        + "\n </build>\n</model>\n")

    plate_xml = []
    for n in sorted(plates):
        inst = "\n".join(
            f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n'
            f'      <metadata key="instance_id" value="0"/>\n'
            f'      <metadata key="identify_id" value="{100 + oid}"/>\n    </model_instance>'
            for oid in plates[n])
        plate_xml.append(f'  <plate>\n    <metadata key="plater_id" value="{n}"/>\n'
                         f'    <metadata key="plater_name" value="{["Case (both caps)", "Sleeve and bracket"][n - 1]}"/>\n'
                         f'    <metadata key="locked" value="false"/>\n{inst}\n  </plate>')
    files["Metadata/model_settings.config"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "\n".join(cfg_objs) + "\n"
        + "\n".join(plate_xml) + "\n</config>\n")

    files["3D/_rels/3dmodel.model.rels"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    files["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        ' <Default Extension="png" ContentType="image/png"/>\n'
        ' <Default Extension="config" ContentType="text/xml"/>\n</Types>\n')

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for k in ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model",
                  "3D/_rels/3dmodel.model.rels", "3D/Objects/object_1.model",
                  "Metadata/model_settings.config"]:
            z.writestr(k, files[k])
    return OUT


if __name__ == "__main__":
    placed = build()
    print(write(placed))
    for name, plate, meshes, _, t in placed:
        lo = np.min([m.bounds[0] for _, m, _ in meshes], axis=0)
        hi = np.max([m.bounds[1] for _, m, _ in meshes], axis=0)
        print(f"plate {plate} {name:16s} {np.round(hi - lo, 1)} at {t}")
