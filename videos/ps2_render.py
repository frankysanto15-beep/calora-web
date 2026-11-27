"""Calora: pantalla de título estilo PS2. Render 3D por software (numpy) + música sintetizada.
Uso: python3 ps2_render.py [--still N salida.png] | (sin args: renderiza calora_ps2.mp4)
"""
import sys, math, wave, subprocess, os
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, N = 270, 480, 30, 420          # interno; se escala x4 (vecino más cercano) a 1080x1920
FOV = math.radians(52)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def hexc(h): return np.array([int(h[i:i+2], 16) / 255 for i in (1, 3, 5)])
CREAM, GREEN, GREEN2, GREEN3, GREEN5 = hexc("#f6f1e6"), hexc("#1d3a33"), hexc("#2c5247"), hexc("#4f7568"), hexc("#c4d3c8")
ORANGE, PEACH, PINK, SAND, WHITE = hexc("#df6432"), hexc("#f4d9c6"), hexc("#efc0aa"), hexc("#e3d3b5"), np.ones(3)
FOG = hexc("#f2d6bf")

# ---------------- mallas ----------------
class Mesh:
    def __init__(s, V, T, color, uv=None, lit=True, cull=None):
        s.V, s.T = np.asarray(V, float), np.asarray(T, int)
        s.C = np.tile(color, (len(s.V), 1)) if np.ndim(color) == 1 else np.asarray(color, float)
        s.uv, s.lit, s.cull = uv, lit, cull
        fn = np.cross(s.V[s.T[:, 1]] - s.V[s.T[:, 0]], s.V[s.T[:, 2]] - s.V[s.T[:, 0]])
        s.N = np.zeros_like(s.V)
        for k in range(3): np.add.at(s.N, s.T[:, k], fn)
        s.N /= np.linalg.norm(s.N, axis=1, keepdims=True) + 1e-9

def outward(V, T, center):
    V, T = np.asarray(V, float), np.asarray(T, int).copy()
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    flip = np.einsum("ij,ij->i", fn, V[T].mean(1) - center) < 0
    T[flip] = T[flip][:, [0, 2, 1]]
    return T

def lathe(profile, seg):
    """profile: [(r, y)] de abajo hacia arriba; r=0 en los extremos = polo."""
    V, rings = [], []
    for r, y in profile:
        if r == 0: rings.append([len(V)]); V.append((0, y, 0)); continue
        rings.append(list(range(len(V), len(V) + seg)))
        V += [(r * math.cos(2 * math.pi * k / seg), y, r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
    T = []
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1: T += [(a[0], b[k], b[(k + 1) % seg]) for k in range(seg)]
        elif len(b) == 1: T += [(a[k], a[(k + 1) % seg], b[0]) for k in range(seg)]
        else:
            for k in range(seg):
                k2 = (k + 1) % seg
                T += [(a[k], a[k2], b[k]), (a[k2], b[k2], b[k])]
    V = np.array(V, float)
    return V, outward(V, T, np.array([0, V[:, 1].mean(), 0]))

def flat(V, T):
    V = np.asarray(V, float)[np.asarray(T).ravel()]
    return V, np.arange(len(V)).reshape(-1, 3)

def box(sx, sy, sz):
    V = np.array([(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)], float) / 2
    T = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return flat(V, outward(V, T, np.zeros(3)))

def sphere(r, seg=7, rings=5):
    return lathe([(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings)) for i in range(rings + 1)], seg)

def octa(r):
    V = np.array([(r, 0, 0), (-r, 0, 0), (0, r * 1.6, 0), (0, -r * 1.6, 0), (0, 0, r), (0, 0, -r)], float)
    T = [(0, 2, 4), (4, 2, 1), (1, 2, 5), (5, 2, 0), (0, 4, 3), (4, 1, 3), (1, 5, 3), (5, 0, 3)]
    return flat(V, outward(V, T, np.zeros(3)))

def hull(V, T, k):  # contorno de casco invertido: se dibujan solo sus caras traseras
    m = Mesh(V, T, GREEN)
    return Mesh(m.V + m.N * k, T, GREEN, lit=False, cull="front")

# ---- termo (cápsula r=1, cilindro de y=-0.65 a 0.65) ----
R, HH = 1.0, 0.65
cap = [(0, -HH - R)] + [(R * math.sin(math.pi / 2 * i / 3), -HH - R * math.cos(math.pi / 2 * i / 3)) for i in (1, 2, 3)]
cap += [(R, 0.0)] + [(R * math.cos(math.pi / 2 * i / 3), HH + R * math.sin(math.pi / 2 * i / 3)) for i in (0, 1, 2)] + [(0, HH + R)]
BODY_V, BODY_T = lathe(cap, 12)

def decal(poly2d, color, eps):
    """polígono convexo (x,y) proyectado sobre el frente del cilindro (abanico)."""
    P = np.array(poly2d, float)
    c = P.mean(0)
    pts = np.vstack([c, P])
    V = np.c_[pts[:, 0], pts[:, 1], np.sqrt(np.maximum(R * R - pts[:, 0] ** 2, 0)) + eps]
    n = len(P)
    T = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    return Mesh(V, outward(V, T, np.array([c[0], c[1], -5])), color)

def circ(cx, cy, rx, ry=None, n=10, a0=0, a1=2 * math.pi):
    ry = rx if ry is None else ry
    return [(cx + rx * math.cos(a0 + (a1 - a0) * k / n), cy + ry * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + (0 if a1 - a0 >= 2 * math.pi else 1))]

def brow(cx, cy, w, t, bend):
    top = [(cx + x, cy + bend * (1 - (x / w * 2) ** 2) + t / 2) for x in np.linspace(-w / 2, w / 2, 5)]
    return top + [(x, y - t) for x, y in reversed(top)]

def face_parts():
    out = []
    for s in (-1, 1):
        out.append(decal(circ(0.3 * s, 0.22, 0.12, 0.13), GREEN, 0.012))
        out.append(decal(circ(0.3 * s + 0.045, 0.27, 0.04, n=6), WHITE, 0.03))
        out.append(decal(circ(0.5 * s, -0.02, 0.12, 0.1), PINK, 0.012))
        out += [decal(brow(0.3 * s, 0.5, 0.3, 0.05, 0.05), GREEN, 0.012)]
    mouth = [(x, -0.06 + 0.03 * (x / 0.24) ** 2) for x in (0.24, 0.12, 0, -0.12, -0.24)] + circ(0, -0.07, 0.24, 0.22, n=8, a0=math.pi, a1=2 * math.pi)[1:-1]
    out.append(decal(mouth, GREEN, 0.012))
    out.append(decal(circ(0, -0.36, 0.07, 0.025, n=6), ORANGE, 0.012))
    out.append(decal([(-0.26, -0.48), (0.26, -0.48), (0.28, -0.56), (0.26, -0.66), (-0.26, -0.66), (-0.28, -0.56)], GREEN, 0.012))
    out.append(decal(circ(-0.1, -0.57, 0.055, n=6), WHITE, 0.03))
    out.append(decal(circ(0.11, -0.57, 0.04, n=6), ORANGE, 0.03))
    return out

def place(V, T, M):  # aplica matriz 4x4 a vértices locales
    return (np.c_[V, np.ones(len(V))] @ M.T)[:, :3], T

def tube(p0, p1, r, seg=5):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0; L = np.linalg.norm(d); y = d / L
    x = np.cross(y, [0, 0, 1.0]); x /= np.linalg.norm(x); z = np.cross(x, y)
    V, T = lathe([(0, 0), (r, 0), (r, L), (0, L)], seg)
    return V @ np.array([x, y, z]) + p0, T

def T4(t): M = np.eye(4); M[:3, 3] = t; return M
def S4(s): return np.diag([*s, 1.0])
def Ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
def Rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])
def Rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

FACE = face_parts()
LEG_V, LEG_T = box(0.17, 0.75, 0.17)
HAND_V, HAND_T = sphere(0.17, 7, 4)
DROP_V, DROP_T = lathe([(0, -1), (0.55, -0.88), (0.88, -0.5), (0.95, 0), (0.78, 0.5), (0.48, 0.95), (0.22, 1.35), (0, 1.75)], 8)
SPARK_V, SPARK_T = octa(0.09)
PED_V, PED_T = lathe([(0, -2.75), (2.1, -2.75), (2.1, -2.42), (1.95, -2.4), (0, -2.4)], 14)

def floor_mesh():
    n, ext = 14, 70.0
    xs = np.linspace(-ext, ext, n + 1)
    V = np.array([(x, -2.75, z) for z in xs for x in xs])
    T = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            T += [(a, a + n + 2, a + 1), (a, a + n + 1, a + n + 2)]
    V = np.array(V)
    return Mesh(V, T, np.ones(3), uv=V[:, [0, 2]] / 2.2)

def hills_mesh():
    rng = np.random.default_rng(7)
    V, T, C = [], [], []
    for k in range(28):
        a0, a1 = 2 * math.pi * k / 28, 2 * math.pi * (k + 1.3) / 28
        rr, h = 52 + rng.uniform(-4, 4), rng.uniform(4, 11)
        am = (a0 + a1) / 2
        b = len(V)
        V += [(rr * math.cos(a0), -2.8, rr * math.sin(a0)), (rr * math.cos(a1), -2.8, rr * math.sin(a1)), ((rr + 2) * math.cos(am), -2.8 + h, (rr + 2) * math.sin(am))]
        T.append((b, b + 1, b + 2))
        C += [GREEN3, GREEN3, GREEN5]
    V = np.array(V, float)
    return Mesh(V, outward(V, T, np.zeros(3)), np.array(C))

FLOOR, HILLS = floor_mesh(), hills_mesh()

# ---------------- tiempo ----------------
BEAT = 18  # 100 bpm a 30 fps
def sstep(a, b, f):
    t = min(max((f - a) / (b - a), 0), 1); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t

F_CRANE, F_ORBIT_END, F_TITLE, F_PRESS = 72, 288, 288, 360

def camera(f):
    intro_eye, intro_tgt = np.array([0, 6.5, 10.0]), np.array([0, 8.6, 0])
    a = lerp(-2.3, 0.0, sstep(F_CRANE + 20, F_ORBIT_END, f))
    rad = lerp(7.0, 10.6, sstep(200, F_TITLE + 20, f))
    hgt = lerp(1.6, 0.4, sstep(150, F_TITLE + 20, f))
    orb_eye = np.array([rad * math.sin(a), hgt, rad * math.cos(a)])
    orb_tgt = np.array([0, lerp(-0.4, 1.3, sstep(240, F_TITLE + 20, f)), 0])
    t = sstep(F_CRANE, F_CRANE + 70, f)
    eye, tgt = lerp(intro_eye, orb_eye, t), lerp(intro_tgt, orb_tgt, t)
    eye = eye + np.array([0.15 * math.sin(f / 23), 0.1 * math.sin(f / 31), 0])  # deriva lenta de cámara de menú
    return eye, tgt

def termo(f):
    """partes del termo en coordenadas de mundo para el cuadro f."""
    jt = (f - F_PRESS - 4) / 22
    jump = 1.5 * 4 * jt * (1 - jt) if 0 <= jt <= 1 else 0
    beat = abs(math.sin(math.pi * f / BEAT))
    sq = 1 - 0.035 * beat
    if F_PRESS - 4 <= f < F_PRESS + 4: sq = 0.88                      # anticipación antes del salto
    if 0 <= jt <= 1: sq = 1 + 0.08 * math.sin(math.pi * jt)
    lift = 0.06 * beat + jump
    pivot = np.array([0, -2.4, 0])
    G = T4([0, lift, 0]) @ T4(pivot) @ S4([1 / math.sqrt(sq), sq, 1 / math.sqrt(sq)]) @ T4(-pivot) @ Rz(0.03 * math.sin(math.pi * f / (2 * BEAT)))
    parts = []
    def add(V, T, color, outline=0.0, M=np.eye(4)):
        V2, T2 = place(V, T, G @ M)
        if outline: parts.append(hull(V2, T2, outline))
        parts.append(Mesh(V2, T2, color))
    add(BODY_V, BODY_T, CREAM, 0.07)
    for m in FACE:
        V2, _ = place(m.V, m.T, G); parts.append(Mesh(V2, m.T, m.C[0]))
    for s in (-1, 1): add(LEG_V, LEG_T, ORANGE, 0.035, T4([0.36 * s, -2.02, 0]))
    wave = 0.55 * math.sin(2 * math.pi * f / BEAT) if f > 150 else 0.0
    up = math.radians(55) + wave + (0.5 if 0 <= jt <= 1 else 0)
    sh_r, sh_l = np.array([0.93, -0.05, 0]), np.array([-0.93, -0.2, 0])
    hand_r = sh_r + 0.75 * np.array([math.cos(up), math.sin(up), 0.15])
    down = math.radians(-120) + (0.9 if 0 <= jt <= 1 else 0.08 * math.sin(math.pi * f / BEAT))
    hand_l = sh_l + 0.65 * np.array([math.cos(down), math.sin(down), 0.2])
    for sh, hd in ((sh_r, hand_r), (sh_l, hand_l)):
        add(*tube(sh, hd, 0.075), GREEN)
        add(HAND_V, HAND_T, WHITE, 0.05, T4(hd))
    shadow = circ(0, 0, 1.0 / (1 + 0.4 * jump), 0.55 / (1 + 0.4 * jump), n=12)
    Vs = np.array([(x, -2.395, y) for x, y in [(0, 0)] + shadow])
    parts.append(Mesh(Vs, outward(Vs, [(0, 1 + k, 1 + (k + 1) % 12) for k in range(12)], np.array([0, -9, 0])), GREEN2 * 0.55, lit=False))
    return parts

def world(f):
    parts = [FLOOR, HILLS, Mesh(PED_V, PED_T, GREEN2)]
    parts += termo(f)
    # gota-logo del intro, en el cielo
    pop = sstep(0, 24, f) * (1 + 0.15 * math.sin(math.pi * min(f / 24, 1)))
    pop *= 1 - sstep(F_CRANE + 10, F_CRANE + 40, f)            # se va antes de que la cámara llegue al termo
    M = T4([0, 8.6 + 0.2 * math.sin(f / 12), 0]) @ Ry(f * 0.09) @ S4([pop * 1.1] * 3)
    V, T = place(DROP_V, DROP_T, M)
    if pop > 0.01: parts += [hull(V, T, 0.12 * pop), Mesh(V, T, ORANGE)]
    # gotas orbitando al termo
    for k in range(5):
        a = 2 * math.pi * k / 5 + f * 0.025
        y = 0.2 + 1.1 * math.sin(f / 20 + k * 1.7)
        g = sstep(60 + k * 8, 100 + k * 8, f)
        M = T4([3.1 * math.cos(a), y, 3.1 * math.sin(a)]) @ Ry(f * 0.12 + k) @ S4([0.32 * g] * 3)
        V, T = place(DROP_V, DROP_T, M)
        parts.append(Mesh(V, T, ORANGE if k % 2 == 0 else PEACH))
    # chispas que suben
    rng = np.random.default_rng(3)
    for k in range(16):
        x, z, ph, sp = rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(0, 1), rng.uniform(0.004, 0.009)
        y = -2.5 + ((ph + f * sp) % 1) * 7
        M = T4([x, y, z]) @ Ry(f * 0.2 + k) @ Rx(f * 0.13)
        V, T = place(SPARK_V, SPARK_T, M)
        parts.append(Mesh(V, T, WHITE if k % 3 else ORANGE, lit=False))
    return parts

# ---------------- rasterizador ----------------
LIGHT = np.array([-0.45, 0.8, 0.55]); LIGHT /= np.linalg.norm(LIGHT)
RIM = np.array([0.6, 0.3, -0.75]); RIM /= np.linalg.norm(RIM)
NEAR = 0.15

def clip_near(P, A):
    """Sutherland-Hodgman de un triángulo contra d >= NEAR. P: (3,) profundidades, A: (3,k) atributos."""
    out = []
    for i in range(3):
        j = (i + 1) % 3
        if P[i] >= NEAR: out.append(A[i])
        if (P[i] >= NEAR) != (P[j] >= NEAR):
            t = (NEAR - P[i]) / (P[j] - P[i]); out.append(A[i] + t * (A[j] - A[i]))
    return [(out[0], out[k], out[k + 1]) for k in range(1, len(out) - 1)]

YY, XX = np.mgrid[0:H, 0:W].astype(float) + 0.5

def sky(eye, tgt):
    fw = (tgt - eye) / np.linalg.norm(tgt - eye)
    r = np.cross(fw, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, fw)
    th = math.tan(FOV / 2)
    ndy = 1 - 2 * YY / H
    dy = fw[1] + u[1] * ndy * th
    dn = np.sqrt(1 + (ndy * th) ** 2)
    t = np.clip((dy / dn) * 1.5 + 0.02, 0, 1) ** 0.75
    top = hexc("#2f6a5e")
    return FOG * (1 - t[..., None]) + top * t[..., None]

def render3d(f):
    eye, tgt = camera(f)
    fw = (tgt - eye) / np.linalg.norm(tgt - eye)
    r = np.cross(fw, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, fw)
    th, asp = math.tan(FOV / 2), W / H
    img = sky(eye, tgt)
    zb = np.zeros((H, W))
    for m in world(f):
        if not len(m.T): continue
        rel = m.V - eye
        d, vx, vy = rel @ fw, rel @ r, rel @ u
        if m.lit:
            diff = np.clip(m.N @ LIGHT, 0, 1)[:, None]
            rim = np.clip(m.N @ RIM, 0, 1)[:, None]
            col = m.C * (0.52 + 0.6 * diff) + hexc("#9fd2c4") * 0.28 * rim * m.C
        else: col = m.C
        dist = np.linalg.norm(rel, axis=1)
        fog = np.clip((dist - 7) / 45, 0, 0.88)
        uv = m.uv if m.uv is not None else np.zeros((len(m.V), 2))
        A = np.c_[vx, vy, d, col, fog, uv]
        tri = m.T
        if m.cull:  # casco invertido: conserva solo las caras que miran lejos de la cámara
            fn = np.cross(m.V[tri[:, 1]] - m.V[tri[:, 0]], m.V[tri[:, 2]] - m.V[tri[:, 0]])
            tri = tri[np.einsum("ij,ij->i", fn, eye - m.V[tri].mean(1)) < 0]
        for t in tri:
            if d[t].max() < NEAR: continue
            pieces = [(A[t[0]], A[t[1]], A[t[2]])] if d[t].min() >= NEAR else clip_near(d[t], A[t])
            for p in pieces:
                raster(img, zb, np.array(p), th, asp, m.uv is not None)
    return img

def raster(img, zb, P, th, asp, textured):
    dd = P[:, 2]
    sx = np.floor(((P[:, 0] / dd) / (th * asp) + 1) / 2 * W) + 0.5   # ajuste a píxel entero = temblor de vértices
    sy = np.floor((1 - (P[:, 1] / dd) / th) / 2 * H) + 0.5
    x0, x1 = int(max(sx.min(), 0)), int(min(sx.max() + 1, W))
    y0, y1 = int(max(sy.min(), 0)), int(min(sy.max() + 1, H))
    if x0 >= x1 or y0 >= y1: return
    area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
    if abs(area) < 1e-9: return
    X, Y = XX[y0:y1, x0:x1], YY[y0:y1, x0:x1]
    w0 = ((sx[1] - X) * (sy[2] - Y) - (sx[2] - X) * (sy[1] - Y)) / area
    w1 = ((sx[2] - X) * (sy[0] - Y) - (sx[0] - X) * (sy[2] - Y)) / area
    w2 = 1 - w0 - w1
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not inside.any(): return
    iz = w0 / dd[0] + w1 / dd[1] + w2 / dd[2]
    zr = zb[y0:y1, x0:x1]
    m = inside & (iz > zr)
    if not m.any(): return
    W3 = np.stack([w0[m], w1[m], w2[m]], 1)
    col = W3 @ P[:, 3:6]
    if textured:  # UV afín (sin corrección de perspectiva), como en consola
        uv = W3 @ P[:, 7:9]
        chk = (np.floor(uv[:, 0]) + np.floor(uv[:, 1])) % 2
        col = col * np.where(chk[:, None] > 0, hexc("#f3e9d6"), hexc("#c9d8cc"))
    fog = (W3 @ P[:, 6])[:, None]
    zr[m] = iz[m]
    img[y0:y1, x0:x1][m] = col * (1 - fog) + FOG * fog

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
def dither15(img):  # 5 bits por canal con tramado ordenado 4x4
    b = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W, None]
    return np.clip(np.floor(np.clip(img, 0, 1) * 31 + b) / 31, 0, 1)

# ---------------- texto / interfaz ----------------
def font(sz): return ImageFont.truetype(FONT, sz)

def chrome_letter(ch, sz):
    fnt = font(sz)
    w = int(fnt.getlength(ch)) + 8
    mask = Image.new("L", (w, sz + 12)); dr = ImageDraw.Draw(mask); dr.fontmode = "1"
    dr.text((4, 2), ch, font=fnt, fill=255)
    hgt = sz + 12
    stops = [(0, "#ffffff"), (0.38, "#d9efe8"), (0.5, "#2c5247"), (0.56, "#df6432"), (1, "#ffe3c9")]
    grad = np.zeros((hgt, w, 3))
    for i in range(hgt):
        t = i / hgt
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= t <= b: grad[i] = lerp(hexc(ca), hexc(cb), (t - a) / (b - a))
    outline = mask.filter(ImageFilter.MaxFilter(5))
    rgba = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    rgba.paste(Image.new("RGBA", (w, hgt), (29, 58, 51, 255)), (0, 0), outline)
    rgba.paste(Image.fromarray((grad * 255).astype(np.uint8)).convert("RGBA"), (0, 0), mask)
    return rgba

TITLE = [chrome_letter(c, 50) for c in "CALORA"]

def pixel_text(im, txt, sz, cx, y, color=(255, 255, 255), outline=(29, 58, 51)):
    dr = ImageDraw.Draw(im); dr.fontmode = "1"
    fnt = font(sz); w = fnt.getlength(txt)
    x = int(cx - w / 2)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (2, 2)):
        dr.text((x + dx, y + dy), txt, font=fnt, fill=outline)
    dr.text((x, y), txt, font=fnt, fill=color)

def overlay(im, f):
    if 18 <= f < 80:  # "CALORA presenta" bajo la gota
        if f < 74 or f % 2: pixel_text(im, "CALORA", 22, W / 2, 300, (255, 248, 239))
        if 30 <= f < 74: pixel_text(im, "presenta", 13, W / 2, 330, (244, 217, 198))
    if f >= F_TITLE:
        total = sum(t.width - 8 for t in TITLE)
        x = (W - total) / 2 - 4
        for i, L in enumerate(TITLE):
            t0 = F_TITLE + 4 + i * 4
            if f >= t0:
                k = min((f - t0) / 10, 1)
                dy = -60 * (1 - k) ** 2 + (8 * math.sin(math.pi * k) if k < 1 else 0)
                if f >= F_PRESS + 4: dy -= 3 * abs(math.sin(math.pi * (f - i * 3) / BEAT))
                im.alpha_composite(L, (int(x), int(48 + dy)))
            x += L.width - 8
        if f >= F_TITLE + 34:
            pixel_text(im, "MANTENCIÓN DE TERMOS", 12, W / 2, 112, (255, 248, 239))
        if F_TITLE + 46 <= f < F_PRESS:
            if (f // 12) % 3 != 2: pixel_text(im, "PRESIONA START", 15, W / 2, 420)
        elif F_PRESS <= f < F_PRESS + 18:
            if (f // 3) % 2 == 0: pixel_text(im, "PRESIONA START", 15, W / 2, 420, (255, 214, 120))
        elif f >= F_PRESS + 18:
            pixel_text(im, "¡AGUA CALIENTE!" , 15, W / 2, 420, (255, 214, 120))
        if f >= F_TITLE + 46:
            pixel_text(im, "© 2026 CALORA", 8, W / 2, 458, (244, 217, 198))

def frame(f):
    img = dither15(render3d(f))
    if f < 10: img = img * (f / 10)                                   # entrada desde negro
    fl = max(0, 1 - abs(f - F_PRESS - 1) / 4) if f >= F_PRESS - 3 else 0
    img = img + (1 - img) * fl * 0.85                                 # destello al presionar start
    im = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    overlay(im, f)
    return np.asarray(im.convert("RGB"))

# ---------------- música ----------------
SR = 44100
def music(path):
    n = int(SR * N / FPS); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    beat_s = 60 / 100
    def mtof(m): return 440 * 2 ** ((m - 69) / 12)
    chords = [[53, 57, 60, 64], [53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59], [53, 57, 60, 64, 69]]  # Fmaj7 Fmaj7 Em7 Dm7 Cmaj7 Fmaj9
    def env(n0, n1, a, rel):
        e = np.zeros(n); i0, i1 = int(n0 * SR), min(int(n1 * SR), n)
        if i0 >= n: return e
        seg = np.arange(i1 - i0) / SR
        e[i0:i1] = np.minimum(seg / a, 1)
        ir = min(i1 + int(rel * SR), n)
        e[i1:ir] = e[i1 - 1] * np.exp(-np.arange(ir - i1) / SR / (rel / 4))
        return e
    def lp(x, a):  # filtro paso bajo de un polo
        y, acc = np.empty_like(x), 0.0
        for i, v in enumerate(x.tolist()): acc += a * (v - acc); y[i] = acc
        return y
    for bar, ch in enumerate(chords):
        s0 = bar * 4 * beat_s; s1 = s0 + 4 * beat_s + (2 if bar == 5 else 0)
        e = env(s0, s1, 0.6 if bar else 1.8, 1.2)
        pad = sum(sum(((t * mtof(m) * (1 + dt)) % 1 * 2 - 1) for dt in (-0.004, 0.004)) for m in ch)
        p = lp(pad * e * 0.05, 0.08)
        out[:, 0] += p; out[:, 1] += np.roll(p, 300)
        if bar == 0: continue
        notes = (ch + [m + 12 for m in ch])[:8]
        for k in range(16):  # arpegio en semicorcheas, campana FM
            st = s0 + k * beat_s / 4
            if st >= N / FPS: break
            i0 = int(st * SR); L = min(int(0.35 * SR), n - i0)
            tt = np.arange(L) / SR; fr = mtof(notes[(k * 3) % len(notes)] + 12)
            v = np.sin(2 * np.pi * fr * tt + 1.8 * np.exp(-tt * 18) * np.sin(2 * np.pi * fr * 2 * tt)) * np.exp(-tt * 9) * 0.11
            pan = 0.5 + 0.35 * math.sin(k)
            out[i0:i0 + L, 0] += v * (1 - pan); out[i0:i0 + L, 1] += v * pan
        for k in range(8):  # bajo en corcheas
            st = s0 + k * beat_s / 2; i0 = int(st * SR); L = min(int(beat_s / 2 * SR * 0.9), n - i0)
            if L <= 0: break
            tt = np.arange(L) / SR; fr = mtof(ch[0] - 12)
            v = (np.sin(2 * np.pi * fr * tt) + 0.25 * np.sign(np.sin(2 * np.pi * fr * tt))) * np.exp(-tt * 3) * 0.16
            out[i0:i0 + L] += v[:, None]
    rng = np.random.default_rng(1)
    for b in range(4, int(N / FPS / beat_s) + 1):  # batería desde el compás 2
        st = b * beat_s; i0 = int(st * SR)
        if i0 >= n: break
        L = min(int(0.3 * SR), n - i0); tt = np.arange(L) / SR
        if b % 2 == 0 or b % 4 == 3:
            out[i0:i0 + L] += (np.sin(2 * np.pi * (45 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9) * 0.45)[:, None]
        if b % 2 == 1:
            sn = rng.standard_normal(L) * np.exp(-tt * 22) * 0.18 + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 25) * 0.12
            out[i0:i0 + L] += sn[:, None]
        for h in (0.5,):
            j0 = int((st + h * beat_s) * SR); Lh = min(int(0.05 * SR), n - j0)
            if Lh > 0:
                hh = np.diff(rng.standard_normal(Lh + 1)) * np.exp(-np.arange(Lh) / SR * 70) * 0.07
                out[j0:j0 + Lh, 0] += hh * 0.7; out[j0:j0 + Lh, 1] += hh
    # campanilla al presionar start
    for k, m in enumerate([77, 81, 84, 89]):
        i0 = int((F_PRESS / FPS + k * 0.07) * SR); L = min(int(1.2 * SR), n - i0); tt = np.arange(L) / SR
        v = np.sin(2 * np.pi * mtof(m) * tt + 2.5 * np.exp(-tt * 6) * np.sin(2 * np.pi * mtof(m) * 3.5 * tt)) * np.exp(-tt * 3.5) * 0.14
        out[i0:i0 + L] += v[:, None]
    # brillo de entrada
    sw = np.sin(2 * np.pi * mtof(88) * t) * np.exp(-((t - 0.8) / 0.5) ** 2) * 0.05
    out += sw[:, None]
    d = int(0.3 * SR)  # eco
    for k in (1, 2, 3):
        out[d * k:] += out[:-d * k][:, ::-1] * (0.28 ** k)
    out = np.tanh(out * 1.4)
    out *= 0.89 / np.abs(out).max()
    fade = np.minimum(1, (n - np.arange(n)) / (0.4 * SR))[:, None]
    out *= fade
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())

# ---------------- salida ----------------
if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).resize((W * 3, H * 3), Image.NEAREST).save(sys.argv[3]); sys.exit()
    wav, mp4 = os.path.join(HERE, "calora_ps2.wav"), os.path.join(HERE, "calora_ps2.mp4")
    music(wav)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", wav, "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, fr in enumerate(pool.imap(frame, range(N), chunksize=4)):
            ff.stdin.write(fr.tobytes())
            if i % 60 == 0: print("cuadro", i, flush=True)
    ff.stdin.close(); ff.wait()
    os.remove(wav)
    print("listo:", mp4)
