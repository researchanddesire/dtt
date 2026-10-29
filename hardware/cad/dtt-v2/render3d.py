"""Headless shaded renders of STL parts with moderngl (EGL, llvmpipe).

    python3 render3d.py scene.json

scene.json: {"out": "x.png", "size": [1400, 1100], "camera": {"dir": [-1, 1.3, -0.9], "up": [0, 0, 1],
             "ortho": true, "zoom": 1.0, "center": null}, "background": [1, 1, 1],
             "parts": [{"stl": "a.stl", "color": [r, g, b], "alpha": 1.0, "offset": [0, 0, 0]}, ...]}
Several scenes: a list of such objects.
"""
import json
import sys

import moderngl
import numpy as np
import trimesh
from PIL import Image

VERT = """
#version 330
uniform mat4 mvp;
uniform mat3 nmat;
in vec3 in_pos;
in vec3 in_norm;
out vec3 v_norm;
out vec3 v_pos;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_norm = normalize(nmat * in_norm);
    v_pos = in_pos;
}
"""
FRAG = """
#version 330
uniform vec4 color;
uniform vec3 view_dir;
in vec3 v_norm;
out vec4 f_color;
void main() {
    vec3 n = normalize(v_norm);
    if (!gl_FrontFacing) n = -n;
    vec3 l1 = normalize(vec3(-0.4, -0.5, 0.75));
    vec3 l2 = normalize(vec3(0.7, 0.3, 0.4));
    vec3 l3 = normalize(vec3(0.0, 0.8, -0.3));
    float d = 0.62 * max(dot(n, l1), 0.0) + 0.30 * max(dot(n, l2), 0.0) + 0.14 * max(dot(n, l3), 0.0);
    vec3 h = normalize(l1 + view_dir);
    float s = pow(max(dot(n, h), 0.0), 40.0) * 0.18;
    vec3 c = color.rgb * (0.30 + 0.72 * d) + vec3(s);
    f_color = vec4(c, color.a);
}
"""


def look(dir_, up):
    d = np.array(dir_, float)
    d /= np.linalg.norm(d)
    u = np.array(up, float)
    x = np.cross(u, -d)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(-d, x)
    # rows: camera x, y, z (z toward the viewer = -dir)
    return np.array([x, y, -d])


def render(scene, ctx, prog):
    w, h = scene.get("size", [1400, 1100])
    ss = 2
    W, H = w * ss, h * ss
    cam = scene.get("camera", {})
    R = look(cam.get("dir", [-1, 1.3, -0.9]), cam.get("up", [0, 0, 1]))
    meshes = []
    for p in scene["parts"]:
        m = trimesh.load(p["stl"], force="mesh")
        off = np.array(p.get("offset", [0, 0, 0]), float)
        v = np.asarray(m.vertices, np.float32) + off.astype(np.float32)
        f = np.asarray(m.faces, np.int32)
        # flat normals per face (sharp edges read better on mechanical parts)
        tri = v[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln == 0] = 1
        n = (n / ln).astype(np.float32)
        verts = tri.reshape(-1, 3)
        norms = np.repeat(n, 3, axis=0)
        meshes.append((verts, norms, p.get("color", [0.5, 0.5, 0.5]), p.get("alpha", 1.0)))
    allv = np.vstack([m[0] for m in meshes])
    c = np.array(cam.get("center") or (allv.min(0) + allv.max(0)) / 2, float)
    pc = (allv - c) @ R.T
    ext = pc.max(0) - pc.min(0)
    aspect = W / H
    zoom = cam.get("zoom", 1.0)
    half_h = max(ext[1] / 2, ext[0] / 2 / aspect) * 1.08 / zoom
    half_w = half_h * aspect
    zmin, zmax = pc[:, 2].min() - 10, pc[:, 2].max() + 10
    # model -> camera -> clip (orthographic)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = -R @ c
    O = np.array([[1 / half_w, 0, 0, 0], [0, 1 / half_h, 0, 0], [0, 0, -2 / (zmax - zmin), -(zmax + zmin) / (zmax - zmin)], [0, 0, 0, 1]])
    mvp = (O @ M).astype(np.float32)
    fbo = ctx.simple_framebuffer((W, H), components=4)
    fbo.use()
    bg = scene.get("background", [1, 1, 1])
    fbo.clear(bg[0], bg[1], bg[2], 1.0)
    ctx.enable(moderngl.DEPTH_TEST)
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
    prog["mvp"].write(mvp.T.tobytes())
    prog["nmat"].write(np.ascontiguousarray(R.T, dtype=np.float32).tobytes())
    prog["view_dir"].value = tuple((-np.array(cam.get("dir", [-1, 1.3, -0.9]), float) / np.linalg.norm(cam.get("dir", [-1, 1.3, -0.9]))).tolist())
    # opaque first, then transparent
    for verts, norms, col, alpha in sorted(meshes, key=lambda m: m[3] < 1.0):
        vbo = ctx.buffer(np.hstack([verts, norms]).astype(np.float32).tobytes())
        vao = ctx.simple_vertex_array(prog, vbo, "in_pos", "in_norm")
        prog["color"].value = (col[0], col[1], col[2], alpha)
        if alpha < 1.0:
            ctx.depth_mask = False
        vao.render(moderngl.TRIANGLES)
        ctx.depth_mask = True
        vao.release()
        vbo.release()
    data = fbo.read(components=4)
    img = Image.frombytes("RGBA", (W, H), data).transpose(Image.FLIP_TOP_BOTTOM)
    img = img.resize((w, h), Image.LANCZOS).convert("RGB")
    img.save(scene["out"])
    fbo.release()
    print("wrote", scene["out"])


def main():
    scenes = json.load(open(sys.argv[1]))
    if isinstance(scenes, dict):
        scenes = [scenes]
    ctx = moderngl.create_standalone_context(backend="egl")
    prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
    for s in scenes:
        render(s, ctx, prog)


if __name__ == "__main__":
    main()
