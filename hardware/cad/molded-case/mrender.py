"""Headless shaded renders (moderngl, EGL) with a colour per triangle.

Adapted from hardware/cad/dtt-v2/render3d.py (PR #14).
"""
import moderngl
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

VERT = """
#version 330
uniform mat4 mvp;
uniform mat3 nmat;
in vec3 in_pos;
in vec3 in_norm;
in vec3 in_col;
out vec3 v_norm;
out vec3 v_col;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_norm = normalize(nmat * in_norm);
    v_col = in_col;
}
"""
FRAG = """
#version 330
uniform vec3 view_dir;
uniform float alpha;
in vec3 v_norm;
in vec3 v_col;
out vec4 f_color;
void main() {
    vec3 n = normalize(v_norm);
    if (!gl_FrontFacing) n = -n;
    vec3 l1 = normalize(vec3(-0.4, 0.5, 0.75));
    vec3 l2 = normalize(vec3(0.7, -0.3, 0.4));
    vec3 l3 = normalize(vec3(0.0, -0.8, -0.3));
    float d = 0.62 * max(dot(n, l1), 0.0) + 0.30 * max(dot(n, l2), 0.0) + 0.14 * max(dot(n, l3), 0.0);
    vec3 h = normalize(l1 + view_dir);
    float s = pow(max(dot(n, h), 0.0), 40.0) * 0.18;
    f_color = vec4(v_col * (0.30 + 0.72 * d) + vec3(s), alpha);
}
"""
_ctx = None
_prog = None


def ctx():
    global _ctx, _prog
    if _ctx is None:
        _ctx = moderngl.create_standalone_context(backend="egl")
        _prog = _ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
    return _ctx, _prog


def look(dir_, up):
    d = np.array(dir_, float)
    d /= np.linalg.norm(d)
    x = np.cross(np.array(up, float), -d)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    return np.array([x, np.cross(-d, x), -d])


def part(mesh, color=(0.2, 0.2, 0.22), offset=(0, 0, 0), alpha=1.0, face_colors=None):
    if isinstance(mesh, str):
        mesh = trimesh.load(mesh, force="mesh")
    v = np.asarray(mesh.vertices, np.float32) + np.asarray(offset, np.float32)
    f = np.asarray(mesh.faces, np.int32)
    tri = v[f]
    n = np.asarray(mesh.face_normals, np.float32)
    fc = np.tile(np.asarray(color, np.float32), (len(f), 1)) if face_colors is None else np.asarray(face_colors, np.float32)
    return dict(v=tri.reshape(-1, 3), n=np.repeat(n, 3, 0), c=np.repeat(fc, 3, 0), alpha=alpha)


def render(parts, out, size=(1200, 900), dir_=(-1, 1.3, -0.9), up=(0, 0, 1), zoom=1.0, center=None,
           bg=(1, 1, 1), title=None, legend=None):
    c_, prog = ctx()
    w, h = size
    ss = 2
    W, H = w * ss, h * ss
    R = look(dir_, up)
    allv = np.vstack([p["v"] for p in parts])
    c = np.array(center if center is not None else (allv.min(0) + allv.max(0)) / 2, float)
    pc = (allv - c) @ R.T
    ext = pc.max(0) - pc.min(0)
    aspect = W / H
    half_h = max(ext[1] / 2, ext[0] / 2 / aspect) * 1.1 / zoom
    half_w = half_h * aspect
    zmin, zmax = pc[:, 2].min() - 10, pc[:, 2].max() + 10
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = -R @ c
    O = np.array([[1 / half_w, 0, 0, 0], [0, 1 / half_h, 0, 0], [0, 0, -2 / (zmax - zmin), -(zmax + zmin) / (zmax - zmin)], [0, 0, 0, 1]])
    mvp = (O @ M).astype(np.float32)
    fbo = c_.simple_framebuffer((W, H), components=4)
    fbo.use()
    fbo.clear(*bg, 1.0)
    c_.enable(moderngl.DEPTH_TEST)
    c_.enable(moderngl.BLEND)
    c_.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
    prog["mvp"].write(mvp.T.tobytes())
    prog["nmat"].write(np.ascontiguousarray(R.T, dtype=np.float32).tobytes())
    vd = -np.array(dir_, float) / np.linalg.norm(dir_)
    prog["view_dir"].value = tuple(vd.tolist())
    for p in sorted(parts, key=lambda p: p["alpha"] < 1.0):
        vbo = c_.buffer(np.hstack([p["v"], p["n"], p["c"]]).astype(np.float32).tobytes())
        vao = c_.simple_vertex_array(prog, vbo, "in_pos", "in_norm", "in_col")
        prog["alpha"].value = p["alpha"]
        c_.depth_mask = p["alpha"] >= 1.0
        vao.render(moderngl.TRIANGLES)
        c_.depth_mask = True
        vao.release()
        vbo.release()
    img = Image.frombytes("RGBA", (W, H), fbo.read(components=4)).transpose(Image.FLIP_TOP_BOTTOM)
    fbo.release()
    img = img.resize((w, h), Image.LANCZOS).convert("RGB")
    if title or legend:
        dr = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 22)
            small = ImageFont.truetype("DejaVuSans.ttf", 17)
        except OSError:
            font = small = ImageFont.load_default()
        if title:
            dr.text((18, 14), title, fill=(20, 20, 20), font=font)
        if legend:
            y = h - 26 * len(legend) - 10
            for col, txt in legend:
                dr.rectangle([18, y + 3, 34, y + 19], fill=tuple(int(255 * k) for k in col))
                dr.text((42, y), txt, fill=(30, 30, 30), font=small)
                y += 26
    img.save(out)
    return out


def grid(paths, out, cols=2):
    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    g = Image.new("RGB", (w * cols, h * rows), "white")
    for i, im in enumerate(ims):
        g.paste(im, ((i % cols) * w, (i // cols) * h))
    g.save(out)
    return out
