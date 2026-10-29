"""Render the jock mount previews in images/ from the meshes build_jock_mount.py leaves in build/.

    python3 hardware/cad/jock-mount/render_jock_mount.py

Needs moderngl (EGL), trimesh and Pillow; render3d.py is a copy of hardware/cad/dtt-v2/render3d.py.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, 'build')
IMG = os.path.join(HERE, 'images')
BLACK, CASE, BLUE = [0.2, 0.2, 0.215], [0.33, 0.33, 0.35], [0.09, 0.42, 0.93]
PAD, BAND, WHITE = [0.36, 0.37, 0.4], [0.62, 0.63, 0.67], [0.85, 0.85, 0.83]
BG = [0.96, 0.96, 0.97]
CASE_PARTS = {'Part__Feature001': CASE, 'RearCover': CASE, 'SwitchCover': BLUE, 'Diffuser': WHITE,
              'LogoInlay': BLUE, 'ButtonInlay': BLUE}


def part(name, colour):
    return {'stl': os.path.join(B, name + '.stl'), 'color': colour}


mount = [part('mount-black', BLACK), part('mount-blue', BLUE)]
case = [part(n, c) for n, c in CASE_PARTS.items()]
pad, band = [part('pad', PAD)], [part('band', BAND)]
front, rear = [-0.55, -0.35, -1], [0.55, -0.35, 1]
views = {
    'Jock-Mount-Hero': (front, mount + case + pad + band, 1.0),
    'Jock-Mount-Part': (front, mount, 1.0),
    'Jock-Mount-Rear': (rear, mount + pad, 1.0),
    'Jock-Mount-End': ([0, -1, 0.0001], mount + case + pad + band, 1.0),  # looking down from the waist
}
scenes = [{'out': os.path.join(IMG, n + '.png'), 'size': [1200, 1200], 'background': BG,
           'camera': {'dir': d, 'up': [0, 0, 1] if d[1] == -1 else [0, 1, 0], 'zoom': z}, 'parts': p}
          for n, (d, p, z) in views.items()]
os.makedirs(IMG, exist_ok=True)
path = os.path.join(B, 'scenes.json')
json.dump(scenes, open(path, 'w'))
subprocess.run([sys.executable, os.path.join(HERE, 'render3d.py'), path], check=True)
