"""Render the DTT v2 assembly images from the build/ meshes (run build_dtt_v2_assembly.py first).

    python3 render_dtt_v2.py            # writes images/*.png

Device coordinates: X across the board, Y up the board, Z toward the user (0 at the PCB front face).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
IMAGES = os.path.join(HERE, 'images')
COL = json.load(open(os.path.join(BUILD, 'colours.json')))

CASE = ['front', 'rear', 'rear_icon', 'slider']
INSIDE = ['pcb', 'models', 'proxies', 'glass', 'active', 'fpc', 'battery', 'screws']
CRADLE = ['cradle_black', 'cradle_blue', 'cups']
UP_Y = [0, 1, 0]


def part(name, prefix='', offset=(0, 0, 0), alpha=1.0, color=None):
    path = os.path.join(BUILD, prefix + name + '.stl')
    if not os.path.exists(path):
        return None
    return {'stl': path, 'color': color or COL[name], 'alpha': alpha, 'offset': list(offset)}


def scene(out, names, cam, size=(1200, 950), prefix='', offsets=None, alphas=None, colors=None):
    offsets, alphas, colors = offsets or {}, alphas or {}, colors or {}
    parts = [part(n, prefix, offsets.get(n, (0, 0, 0)), alphas.get(n, 1.0), colors.get(n)) for n in names]
    return {'out': os.path.join(IMAGES, out), 'size': list(size), 'camera': cam, 'background': [1, 1, 1],
            'parts': [p for p in parts if p]}


def main():
    os.makedirs(IMAGES, exist_ok=True)
    front34 = {'dir': [-0.55, -0.5, -1.0], 'up': UP_Y}
    rear34 = {'dir': [-0.6, -0.5, 1.0], 'up': UP_Y}          # camera on the USB-C side, behind
    rear34_l = {'dir': [0.6, -0.5, 1.0], 'up': UP_Y}         # camera on the PH6 side, behind
    scenes = [
        scene('DTT-v2-Hero.png', CASE + ['glass', 'active'] + CRADLE, front34, (1400, 1100)),
        scene('DTT-v2-Front.png', CASE + ['glass', 'active'], front34),
        scene('DTT-v2-Rear.png', CASE + ['screws'], rear34),
        scene('DTT-v2-Side-PH6.png', CASE + ['screws'], rear34_l),
        scene('DTT-v2-In-Cradle-Side.png', CASE + ['glass', 'active'] + CRADLE,
              {'dir': [-1.0, -0.35, -0.45], 'up': UP_Y}),
        scene('DTT-v2-In-Cradle-Rear.png', CASE + CRADLE, {'dir': [0.5, -0.4, 1.0], 'up': UP_Y}),
        scene('DTT-v2-Exploded.png', CASE + INSIDE, {'dir': [-1.0, -0.45, -0.75], 'up': UP_Y}, (1400, 1200),
              offsets={'front': (0, 0, 26), 'glass': (0, 0, 13), 'active': (0, 0, 13), 'fpc': (0, 0, 13),
                       'battery': (0, 0, -10), 'rear': (0, 0, -26), 'screws': (0, 0, -40), 'slider': (14, 0, -13)}),
        scene('DTT-v2-Switch-Side.png', CASE + ['glass', 'active'],
              {'dir': [-1.0, -0.3, -0.4], 'up': UP_Y, 'center': [21, 16, -4], 'zoom': 3.2}, (1000, 800)),
        scene('DTT-v2-Section-Long.png', CASE + INSIDE, {'dir': [-1.0, -0.3, -0.35], 'up': UP_Y}, (1400, 1000),
              prefix='secx_'),
        scene('DTT-v2-Section-Switch.png', CASE + INSIDE,
              {'dir': [0.25, 1.0, -0.55], 'up': [0, 0, 1], 'center': [0, 16, -5], 'zoom': 1.6}, (1400, 900),
              prefix='secy_'),
        scene('Detail-Boot-Pin.png', CASE + ['screws'],
              {'dir': [0.3, -0.35, 1.0], 'up': UP_Y, 'center': [-14, 42.5, -13.5], 'zoom': 4.0}, (900, 800)),
        scene('Section-Boot-Pin.png', CASE + INSIDE,
              {'dir': [0.05, 1.0, 0.02], 'up': [0, 0, 1], 'center': [-14, 42.5, -7.5], 'zoom': 2.8}, (1100, 900),
              prefix='secp_'),
        scene('DTT-v2-Cradle.png', CRADLE, front34),
        scene('DTT-v2-Cradle-Rear.png', CRADLE, {'dir': [0.45, -0.45, 1.0], 'up': UP_Y}),
        scene('Part-Front-Shell-Inside.png', ['front'], {'dir': [0.35, 0.45, 1.0], 'up': UP_Y}, (1000, 800)),
        scene('Part-Rear-Cover-Inside.png', ['rear'], {'dir': [-0.35, -0.45, -1.0], 'up': UP_Y}, (1000, 800)),
        scene('Part-Switch-Cover.png', ['slider'], {'dir': [-1.0, -0.6, -0.8], 'up': UP_Y, 'zoom': 1.0}, (800, 700)),
        scene('Stack-Board-Screen-Battery.png', INSIDE, {'dir': [-0.7, -0.5, -1.0], 'up': UP_Y}),
        scene('Stack-Board-Rear.png', ['pcb', 'models', 'proxies', 'battery'], {'dir': [-0.6, -0.5, 1.0], 'up': UP_Y}),
    ]
    sc = os.path.join(BUILD, 'scenes.json')
    json.dump(scenes, open(sc, 'w'), indent=1)
    subprocess.check_call([sys.executable, os.path.join(HERE, 'render3d.py'), sc])


if __name__ == '__main__':
    main()
