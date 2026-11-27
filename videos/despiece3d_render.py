"""Despiece 3D del termostato de varilla: rayos X sobre lo que tapa la pieza explicada, cámara dinámica.
Render por software (numpy), luz por píxel, 540x960 -> 1080x1920. Misma grilla de tiempo y música que despiece_render.py
(144 bpm = 10 cuadros por tiempo), así cada corte y cada clic cae en el ritmo.
Uso: python3 despiece3d_render.py [--still N salida.png]
"""
import sys, os, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ps2_render import lathe, box, outward, T4, Rx, Ry, Rz, S4, hexc
import despiece_render as dr
from pixel_render import bloom

W, H, FPS, N = 540, 960, 24, 26 * 40                                   # 26 compases; el final empalma con el inicio
BEAT, BAR = 10, 40
HERE = os.path.dirname(os.path.abspath(__file__))
YY, XX = np.mgrid[0:H, 0:W].astype(float) + 0.5
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
F18, F22, F28 = (ImageFont.truetype(FB, s) for s in (18, 22, 28))

def ease(a, b, f):
    t = min(max((f - a) / (b - a), 0), 1); return t * t * (3 - 2 * t)
def back(a, b, f):
    t = min(max((f - a) / (b - a), 0), 1); c = 1.7; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
def lerp(a, b, t): return a + (b - a) * t

# ---------- materiales ----------
MAT = dict(plastic=(hexc("#e2dfd8"), 0.25, 30), dark=(hexc("#2e3238"), 0.35, 40), brass=(hexc("#d6a63c"), 0.9, 60),
           copper=(hexc("#cc7440"), 0.9, 55), steel=(hexc("#b9c1c8"), 0.85, 80), red=(hexc("#d23a30"), 0.35, 40),
           tank=(hexc("#eeeeee"), 0.3, 30), water=(hexc("#4c8ccf"), 0.2, 30), hot=(hexc("#e8692c"), 0.2, 30), white=(hexc("#f4f4f2"), 0.3, 30))

class Part:
    def __init__(s, V, T, mat, name, part, N=None, emis=None):
        s.V, s.T = np.asarray(V, float), np.asarray(T, int)
        s.mat, s.name, s.part, s.emis = mat, name, part, emis
        if N is None:
            fn = np.cross(s.V[s.T[:, 1]] - s.V[s.T[:, 0]], s.V[s.T[:, 2]] - s.V[s.T[:, 0]])
            N = np.zeros_like(s.V)
            for k in range(3): np.add.at(N, s.T[:, k], fn)
        s.N = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-9)

def roundbox(hx, hy, hz, r):
    V, T = lathe([(math.sin(math.pi * i / 10), -math.cos(math.pi * i / 10)) for i in range(11)], 16)
    d = V / np.linalg.norm(V, axis=1, keepdims=True)
    core = np.clip(d * 1e3, -np.array([hx - r, hy - r, hz - r]), np.array([hx - r, hy - r, hz - r]))
    return core + d * r, T, d

def cyl_z(r, z0, z1, seg=24, knurl=0.0, cap_r=None):
    """cilindro con eje z (para perilla, botón, disco)."""
    V, T = lathe([(0, z0), (r, z0), (r, z1), (cap_r or r * 0.92, z1 + 0.6), (0, z1 + 0.6)], seg)
    if knurl:
        ang = np.arctan2(V[:, 2], V[:, 0]); side = (V[:, 1] > z0 + 0.1) & (V[:, 1] < z1 + 0.1)
        k = 1 + knurl * (np.cos(ang * 12) > 0) * side
        V[:, 0] *= k; V[:, 2] *= k
    V = V @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])                   # eje y -> eje z
    return V, outward(V, T, np.array([0, 0, (z0 + z1) / 2]))

def place(V, M): return (np.c_[V, np.ones(len(V))] @ M.T)[:, :3]

# ---------- el termostato (mm; cabezal de y=0 a 42, varilla hacia abajo) ----------
def build():
    P = []
    V, T, Nn = roundbox(25, 21, 15, 4); P.append(Part(V + [0, 21, 0], T, "plastic", "cover", 2, Nn))
    for k in range(9):  # escala alrededor de la perilla
        a = -2.3 + 4.6 * k / 8
        V, T = box(1.2, 3.5, 0.6)
        P.append(Part(place(V, T4([15.8 * math.sin(a), 22 + 15.8 * math.cos(a), 15.2]) @ Rz(-a)), T, "red" if k >= 6 else "dark", "cover", 2))
    for sx in (-19, 19):
        V, T = cyl_z(1.6, 14.6, 15.2, 8); P.append(Part(V + [sx, 4, 0], T, "dark", "cover", 2))
    V, T = cyl_z(11.5, 15, 23, 48, knurl=0.05); P.append(Part(V, T, "dark", "knob", 1))
    V, T = box(1.6, 8.5, 0.8); P.append(Part(V + [0, 4.5, 23.9], T, "white", "knob", 1))
    for tx in (-14, 0, 14):
        V, T = box(6.4, 10, 0.9); P.append(Part(V + [tx, 47, 0], T, "brass", "terminals", 3))
    V, T = box(22, 11, 10); P.append(Part(V + [0, 16, 0], T, "dark", "switch", 4))
    V, T = box(5, 3, 5); P.append(Part(V + [0, 10, 0], T, "white", "switch", 4))
    V, T = box(19, 0.8, 6); P.append(Part(V + [9.5, 0, 0], T, "steel", "lever", 4))     # pivote en el origen
    for tx in (-7, 0, 7):
        V, T = box(1.5, 4, 0.8); P.append(Part(V + [tx, 23.5, 0], T, "brass", "switch", 4))
    V, T = lathe([(0, 0), (6, 0), (5.2, 0.9), (3, 1.5), (0, 1.7)], 20)
    P.append(Part(V @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]]), outward(V @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]]), T, np.array([0, 0, -3])), "steel", "disc", 6))
    V, T = cyl_z(3, 0, 5, 16); P.append(Part(V, T, "red", "button", 6))
    V, T = lathe([(0, -8), (6, -8), (6, 0), (0, 0)], 20); P.append(Part(V, T, "brass", "collar", 5))
    V, T = lathe([(0, -228)] + [(3.2 * math.sin(math.pi / 2 * i / 4), -224.8 + 3.2 * (1 - math.cos(math.pi / 2 * i / 4)) - 3.2) for i in range(1, 5)] + [(3.2, -8), (0, -8)], 16)
    P.append(Part(V, T, "copper", "tube", 5))
    V, T = lathe([(0, -226), (1.3, -226), (1.3, 6), (0, 6)], 10); P.append(Part(V, T, "steel", "invar", 5))
    return P
DEVICE = build()

def build_tank():
    P = []
    prof = [(0, 0), (190, 0), (205, 30), (205, 570), (190, 600), (0, 600)]
    V, T = lathe(prof, 28); P.append(Part(V, T, "tank", "tank", 0))
    V, T = lathe([(0, 8), (196, 8), (196, 340), (0, 340)], 24); P.append(Part(V, T, "water", "water", 0))
    V, T = lathe([(0, 340), (196, 340), (196, 590), (0, 590)], 24); P.append(Part(V, T, "hot", "water", 0))
    for x in (-45, -15):  # resistencia en U
        V, T = lathe([(0, 0), (5, 0), (5, 300), (0, 300)], 10); P.append(Part(V + [x, 0, 0], T, "copper", "heater", 0, emis=hexc("#ff7a2a") * 0.7))
    V, T = box(40, 10, 10); P.append(Part(V + [-30, 300, 0], T, "copper", "heater", 0, emis=hexc("#ff7a2a") * 0.7))
    V, T = lathe([(0, 0), (6, 0), (6, 240), (0, 240)], 12); P.append(Part(V + [45, 0, 0], T, "steel", "vaina", 0))
    V, T = lathe([(0, -10), (80, -10), (80, 0), (0, 0)], 24); P.append(Part(V, T, "steel", "flange", 0))
    return P
TANK = build_tank()

EXPL = {1: (0, 0, 70), 2: (0, 0, -40), 3: (0, 38, 0), 4: (-34, -4, 34), 5: (0, -46, 0), 6: (36, 6, 38)}

def device_meshes(st, base=np.eye(4)):
    """st: explode (dict parte->0..1), knob, lever, ext, flip, button, heat."""
    out = []
    for p in DEVICE:
        e = st["explode"].get(p.part, 0)
        M = base @ T4(np.array(EXPL[p.part]) * e)
        if p.name == "knob": M = M @ T4([0, 22, 0]) @ Rz(st["knob"])
        if p.name == "lever": M = M @ T4([-9.5, 7.6, 0]) @ Rz(st["lever"])
        if p.name == "disc": M = M @ T4([16, 33, 2]) @ S4([1, 1, -1 if st["flip"] else 1]) @ T4([0, 0, 0])
        if p.name == "button": M = M @ T4([17, 36, 15 + st["button"]])
        if p.name == "tube": M = M @ T4([0, -8, 0]) @ S4([1, (220 + st["ext"]) / 220, 1]) @ T4([0, 8, 0])
        if p.name == "invar": M = M @ T4([0, -st["ext"], 0])
        emis = hexc("#ff6a1a") * 0.9 * st["heat"] if p.name == "tube" else None
        out.append((p, M, emis))
    return out

# ---------- rasterizador con luz por píxel y pasada transparente ----------
LK = np.array([-0.5, 0.75, 0.6]); LK /= np.linalg.norm(LK)
LF = np.array([0.8, 0.1, 0.4]); LF /= np.linalg.norm(LF)
LR = np.array([0.2, 0.4, -0.9]); LR /= np.linalg.norm(LR)
GHOST = hexc("#8fd3ff")

def shade(Nw, Pw, base, spec, shin, eye, emis, glow, dim):
    n = Nw / (np.linalg.norm(Nw, axis=1, keepdims=True) + 1e-9)
    v = eye - Pw; v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-9
    amb = 0.16 + 0.1 * n[:, 1:2]
    dif = np.clip(n @ LK, 0, 1)[:, None] * 1.0 + np.clip(n @ LF, 0, 1)[:, None] * 0.35 * hexc("#bcd2ff")
    h = LK + v; h /= np.linalg.norm(h, axis=1, keepdims=True)
    sp = np.clip((n * h).sum(1), 0, 1)[:, None] ** shin * spec * 1.4
    fres = (1 - np.clip((n * v).sum(1), 0, 1))[:, None]
    rim = np.clip(n @ LR, 0, 1)[:, None] * 0.5 * fres
    metal = spec > 0.8
    c = base * (amb + dif) * (0.7 if metal else 1) + sp * (base if metal else 1) + rim * hexc("#9ec9ff")
    if metal: c = c + base * 0.25 * np.clip(v[:, 1:2] + 0.3, 0, 1)   # reflejo de entorno simple
    c = c * dim
    if emis is not None: c = c + emis
    if glow: c = c + glow * hexc("#ffb347") * fres ** 1.5
    return c, fres

class Cam:
    def __init__(s, eye, tgt, fov):
        s.eye, s.fw = np.asarray(eye, float), np.asarray(tgt, float) - eye
        s.fw /= np.linalg.norm(s.fw)
        s.r = np.cross(s.fw, [0, 1, 0]); s.r /= np.linalg.norm(s.r); s.u = np.cross(s.r, s.fw)
        s.th = math.tan(math.radians(fov) / 2); s.asp = W / H
    def proj(s, V):
        rel = V - s.eye; d = rel @ s.fw
        return (rel @ s.r / d / (s.th * s.asp) + 1) / 2 * W, (1 - rel @ s.u / d / s.th) / 2 * H, d

def render(cam, items, bg):
    img = bg.copy(); zb = np.zeros((H, W)); trans = []
    for p, M, emis, mode, glow, dim in items:
        V = place(p.V, M); R = M[:3, :3]; Nw = p.N @ R.T
        sx, sy, d = cam.proj(V)
        base, spec, shin = MAT[p.mat]
        tri = p.T
        fn = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]])
        tri = tri[(np.einsum("ij,ij->i", fn, cam.eye - V[tri].mean(1)) > 0) & (d[tri].min(1) > 1)]  # caras traseras fuera
        for t in tri:
            A = (sx[t], sy[t], 1 / d[t], Nw[t], V[t])
            if mode == "solid": raster(img, zb, A, (base, spec, shin, cam.eye, emis, glow, dim), None)
            else: trans.append((d[t].mean(), A, (base, spec, shin, cam.eye, emis, glow, dim), mode))
    trans.sort(key=lambda x: -x[0])                                     # de atrás hacia adelante
    for _, A, sh, mode in trans: raster(img, zb, A, sh, mode)
    return img

def raster(img, zb, A, sh, mode):
    sx, sy, iz, Nw, Pw = A
    x0, x1 = int(max(sx.min(), 0)), int(min(sx.max() + 1, W)); y0, y1 = int(max(sy.min(), 0)), int(min(sy.max() + 1, H))
    if x0 >= x1 or y0 >= y1: return
    area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
    if abs(area) < 1e-9: return
    Xs, Ys = XX[y0:y1, x0:x1], YY[y0:y1, x0:x1]
    w0 = ((sx[1] - Xs) * (sy[2] - Ys) - (sx[2] - Xs) * (sy[1] - Ys)) / area
    w1 = ((sx[2] - Xs) * (sy[0] - Ys) - (sx[0] - Xs) * (sy[2] - Ys)) / area
    w2 = 1 - w0 - w1
    z = w0 * iz[0] + w1 * iz[1] + w2 * iz[2]
    zr = zb[y0:y1, x0:x1]
    m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (z > zr)
    if not m.any(): return
    # interpolación con corrección de perspectiva
    Wp = np.stack([w0[m] * iz[0], w1[m] * iz[1], w2[m] * iz[2]], 1); Wp /= Wp.sum(1, keepdims=True)
    c, fres = shade(Wp @ Nw, Wp @ Pw, *sh)
    region = img[y0:y1, x0:x1]
    if mode is None:
        region[m] = c; zr[m] = z[m]
    else:  # rayos X: color fantasma, más opaco en los bordes (fresnel)
        a = (0.08 + 0.55 * fres ** 1.5) * (1.6 if mode == "ghost+" else 1)
        g = GHOST * (0.35 + 0.9 * fres)
        region[m] = region[m] * (1 - a) + g * a

# ---------- guion ----------
PARTS = {1: "1 · PERILLA", 2: "2 · CARCASA", 3: "3 · BORNES", 4: "4 · MICRORRUPTOR", 5: "5 · VARILLA SENSORA", 6: "6 · DISCO DE SEGURIDAD"}
PCAPS = {1: ["Con ella eliges a qué temperatura", "se apaga la resistencia."],
         2: ["Plástico que cubre y aísla las", "piezas que llevan corriente."],
         3: ["Aquí se conectan los cables: entra", "la corriente y va a la resistencia."],
         4: ["Es el interruptor: con un clic", "deja pasar o corta la corriente."],
         5: ["Tubo de cobre con una varilla que", "casi no se dilata. Con el calor el", "tubo crece y mueve el interruptor."],
         6: ["Si el agua pasa de unos 90 °C, se", "da vuelta y corta todo. Queda", "bloqueado hasta rearmarlo."]}
GHOSTS = {1: set(), 2: set(), 3: set(), 4: {"cover", "knob"}, 5: {"cover", "knob", "tube"}, 6: {"cover", "knob"}}
ANCHOR = {1: (0, 30, 24), 2: (-25, 30, 10), 3: (14, 52, 0), 4: (0, 16, 5), 5: (0, -60, 3), 6: (16, 33, 3)}

def orbit(tgt, dist, yaw, pitch):
    tgt = np.asarray(tgt, float)
    return tgt + dist * np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)]), tgt

def work_T(f):
    if f < 1000: return 20 + 41 * ease(915, 998, f)
    if f < 1040: return 61 - 6 * ease(1000, 1038, f)
    if f < 1080: return 55 + 37 * ease(1040, 1080, f)
    return 92 - 4 * ease(1080, 1160, f)

LOOP_YAW = 0.006
def script(f):
    if f < 160 or f >= 1000: return script_loop(f)
    return script_main(f + 160)

def script_loop(f):
    st = dict(explode={}, knob=0.6, lever=0.0, ext=0.0, flip=False, button=0.0, heat=0.0)
    S = dict(st=st, ghost=set(), focus=None, caps=None, title=None, labels=[], hud=None, tank=True, fov=34, shake=0, insert=0.0)
    yaw = 0.5 + ((f - 1000) if f >= 1000 else (f + 40)) * LOOP_YAW          # el giro sigue igual a través del corte del loop
    if f >= 1000:
        S["insert"] = -230 * (1 - ease(1000, 1036, f))                    # vuelve a entrar en su vaina
        eye, tgt = orbit([0, 250, 0], 1300, yaw, 0.15)
    else:
        k = ease(80, 158, f)
        eye, tgt = orbit(lerp(np.array([0, 250, 0]), np.array([45, -25, 0]), k), lerp(1300, 170, k ** 0.7), yaw + 0.4 * k, lerp(0.15, -0.1, k))
        S["shake"] = 3 * ease(110, 160, f)
        if f < 70: S["title"] = ("EL TERMOSTATO DE VARILLA", "de un termo eléctrico")
        if 12 <= f < 110:
            S["labels"] = [("vaina", (45, 200, 0), 1), ("resistencia", (-45, 150, 0), -1), ("termostato", (45, -30, 0), 1)]
            S["bottom"] = ["Se instala desde abajo: la varilla", "entra en una vaina, junto a la", "resistencia, y así mide el agua."]
        if f >= 110: S["caps"] = ["Veamos qué tiene dentro..."]
    S["cam"] = Cam(eye if not S["shake"] else eye + np.random.default_rng(f).normal(0, S["shake"], 3) * np.linalg.norm(eye - tgt) / 300, tgt, S["fov"])
    return S

def script_main(f):
    st = dict(explode={}, knob=0.6, lever=0.0, ext=0.0, flip=False, button=0.0, heat=0.0)
    S = dict(st=st, ghost=set(), focus=None, caps=[], title=None, labels=[], hud=None, tank=False, fov=38, shake=0)
    if f < 160:
        if f < 80: eye, tgt = orbit([0, 21, 0], lerp(95, 150, ease(0, 80, f)), lerp(-1.0, 0.3, ease(0, 80, f)), 0.18)
        else: eye, tgt = orbit(lerp(np.array([0, 21, 0]), np.array([0, -95, 0]), ease(80, 140, f)), lerp(150, 520, ease(80, 140, f)), lerp(0.3, 0.9, ease(80, 160, f)), 0.12)
        S["title"] = ("EL TERMOSTATO DE VARILLA", "de un termo eléctrico") if f >= 6 else None
        if f >= 90: S["labels"] = [("cabezal", (25, 30, 0), 1), ("varilla (220 mm)", (3, -150, 0), 1)]
    elif f < 240:
        S["tank"] = True
        eye, tgt = orbit([0, 250, 0], lerp(1500, 1250, ease(160, 240, f)), lerp(0.5, 1.0, ease(160, 240, f)), 0.15); S["fov"] = 34
        S["caps"] = ["Se instala desde abajo: la varilla", "entra en una vaina, junto a la", "resistencia, y así mide el agua."]
        S["labels"] = [("vaina", (45, 200, 0), 1), ("resistencia", (-45, 150, 0), -1), ("termostato", (45, -30, 0), 1)]
    elif f < 320:
        k = ease(240, 320, f)
        eye, tgt = orbit([0, -30, 0], lerp(420, 210, k), lerp(1.2, 0.5, k), 0.15)
        S["shake"] = 2.5 * ease(280, 320, f)
        S["caps"] = ["Ahora, desarmémoslo", "pieza por pieza."]
    elif f < 360:
        e = back(320, 332, f) * (1 - ease(350, 359, f))
        st["explode"] = {k: e for k in EXPL}
        eye, tgt = orbit([0, 0, 0], 300, lerp(0.5, -0.7, ease(320, 352, f)), lerp(0.2, 0.35, ease(320, 352, f)))
        S["shake"] = 6 * max(0, 1 - (f - 320) / 10); S["fov"] = 38 + 8 * max(0, 1 - (f - 320) / 8)
        if f >= 324: S["labels"] = [(str(k), place(np.array([ANCHOR[k]]), T4(np.array(EXPL[k]) * e))[0], 0) for k in EXPL]
    elif f < 840:
        p = (f - 360) // 80 + 1; l = f - 360 - (p - 1) * 80
        S["focus"], S["ghost"] = p, GHOSTS[p]
        whip = (1 - ease(0, 8, l)) * 1.3
        cams = {1: ([0, 24, 18], 95, lerp(0.7, 0.25, l / 80), 0.12), 2: ([0, 21, 0], 170, lerp(-0.9, -0.4, l / 80), 0.3),
                3: ([0, 46, 0], 105, lerp(0.3, 0.8, l / 80), 0.65), 4: ([0, 14, 0], 100, lerp(-0.6, -0.2, l / 80), 0.2),
                5: ([0, lerp(-200, -5, ease(4, 76, l)), 0], 120, 0.9, 0.08), 6: ([14, 32, 6], 90, lerp(0.75, 0.4, l / 80), 0.32)}
        tg, dist, yaw, pitch = cams[p]
        eye, tgt = orbit(tg, dist, yaw + whip, pitch)
        if p == 1: st["knob"] = [-1.6, -0.6, 0.6, 1.6, 0.6, -0.6, -1.6, -0.6][(l // BEAT) % 8]
        if p == 4: st["lever"] = 0.0 if (l // 20) % 2 == 0 else -0.22
        if p == 5:
            st["ext"] = 6 * ease(10, 60, l); st["heat"] = ease(10, 60, l); st["lever"] = -0.22 * ease(50, 60, l)
        if p == 6: st["flip"] = l >= 40; st["button"] = 3 if l >= 40 else 0
        if p == 6 and 40 <= l < 46: S["shake"] = 3
        S["title"], S["caps"] = (PARTS[p], None), PCAPS[p]
        S["labels"] = [(PARTS[p].split("· ")[1].lower(), ANCHOR[p], 1)]
        if p == 5 and l > 20: S["labels"].append(("varilla interior (invar)", (1.3, -120, 0), -1))
    elif f < 900:
        order = [5, 4, 6, 2, 1, 3]
        for i, k in enumerate(order):  # cada pieza salta y vuelve a su lugar en su tiempo
            l = f - 840 - i * BEAT
            st["explode"][k] = math.sin(math.pi * min(max(l / BEAT, 0), 1)) * 0.6
        eye, tgt = orbit([0, -10, 0], 280, lerp(0.4, 0.4 + math.pi, ease(840, 900, f)), 0.25)
        S["caps"] = ["Todo junto otra vez..."]
    else:
        T = work_T(f)
        st["knob"] = lerp(0.6, -0.3, ease(900, 910, f))
        st["ext"] = 8 * max(T - 20, 0) / 72; st["heat"] = np.clip((T - 25) / 60, 0, 1)
        closed = f < 1000 or f >= 1040
        st["lever"] = 0.0 if closed else -0.22
        tripped = 1080 <= f < 1104
        st["flip"] = tripped; st["button"] = 3 if tripped else (-1.2 if 1100 <= f < 1108 else 0)
        S["ghost"] = {"cover", "knob", "tube"}
        if f < 1080: eye, tgt = orbit([-9, 4, 0], lerp(290, 250, ease(900, 1080, f)), 0.35 + 0.25 * math.sin(f / 60), 0.18)
        elif f < 1100: eye, tgt = orbit([16, 33, 2], 80, 0.5, 0.3)
        else: eye, tgt = orbit(lerp(np.array([4, 18, 0]), np.array([0, -95, 0]), ease(1104, 1150, f)), lerp(100, 520, ease(1104, 1150, f)), 0.5 + (f - 1100) / 90, 0.15)
        if f in range(1000, 1004) or f in range(1040, 1044): S["shake"] = 2
        if 1080 <= f < 1090: S["shake"] = 7 * (1 - (f - 1080) / 10)
        S["hud"] = dict(T=T, on=closed and not tripped and f < 1104 or (f >= 1104 and closed), flash=max(0, 1 - abs(f - 1080) / 6) if f >= 1080 else 0)
        S["caps"] = (["Fijas 60 °C. El agua se calienta,", "el tubo crece y... ¡clic!", "la resistencia se apaga."] if f < 1000 else
                     ["Al enfriarse unos grados, el tubo", "se acorta y vuelve a encender."] if f < 1040 else
                     ["¿Y si el interruptor se pega?", "La temperatura sigue subiendo..."] if f < 1080 else
                     ["¡El disco de seguridad salta", "y corta todo!"] if f < 1100 else
                     ["Solo vuelve a funcionar apretando", "el botón de rearme, después de", "revisar por qué falló."])
        if f < 1104: S["labels"] = [("microrruptor", (0, 16, 5), -1), ("disco de seguridad", (16, 33, 3), 1)]
    if f >= 320 and not (1080 <= f < 1100):  # el zoom late con el bombo
        S["fov"] *= 1 - 0.025 * math.exp(-((f % BEAT) / BEAT) * 6)
    if S["shake"]:
        rng = np.random.default_rng(f); eye = eye + rng.normal(0, S["shake"], 3) * np.linalg.norm(eye - tgt) / 300
    S["cam"] = Cam(eye, tgt, S["fov"])
    return S

BG = None
def background():
    v = 0.05 + 0.16 * np.exp(-((XX - W / 2) ** 2 + (YY - H * 0.48) ** 2) / 150000)
    return np.stack([v * 0.85, v * 0.95, v * 1.15], -1)

def frame(f):
    global BG
    if BG is None: BG = background()
    S = script(f); cam = S["cam"]; st = S["st"]
    items = []
    if S["tank"]:
        base = T4([45, -8 + S.get("insert", 0), 0]) @ Rz(math.pi)                               # termostato dado vuelta, varilla hacia arriba
        for p in TANK:
            mode = "ghost" if p.name in ("tank", "water") else "solid"
            items.append((p, np.eye(4), p.emis, mode, 0, 1.0))
        for p, M, emis in device_meshes(st, base): items.append((p, M, emis, "solid", 0, 1.0))
    else:
        pulse = 0.6 + 0.4 * math.exp(-((f % BEAT) / BEAT) * 5)
        for p, M, emis in device_meshes(st):
            ghost = p.name in S["ghost"]
            foc = S["focus"]
            glow = 0.55 * pulse if foc and p.part == foc and not ghost else 0
            dim = 0.45 if foc and p.part != foc and not ghost else 1.0
            items.append((p, M, emis, "ghost" if ghost else "solid", glow, dim))
    img = render(cam, items, BG)
    emis = np.clip(img - 0.85, 0, None) * 2
    img = bloom(img, emis, 8, 0.5)
    if S["hud"] and S["hud"]["flash"]: img = img + (1 - img) * 0.45 * S["hud"]["flash"]
    im = Image.fromarray((np.clip(img, 0, 1) ** (1 / 1.1) * 255).astype(np.uint8))
    overlay(im, S, f)
    return np.asarray(im)

def txt(d, s, font, cx, y, fill, anchor="ma"):
    d.text((cx + 2, y + 2), s, font=font, fill=(0, 0, 0), anchor=anchor)
    d.text((cx, y), s, font=font, fill=fill, anchor=anchor)

def overlay(im, S, f):
    d = ImageDraw.Draw(im); cam = S["cam"]
    y = 26
    if S["title"]:
        a, b = S["title"]
        txt(d, a, F28, W / 2, y, (255, 214, 120)); y += 38
        if b: txt(d, b, F22, W / 2, y, (220, 230, 240)); y += 34
    if S["caps"]:
        for k, s in enumerate(S["caps"]): txt(d, s, F22, W / 2, y + k * 30, (240, 242, 245))
    for k, s in enumerate(S.get("bottom") or []): txt(d, s, F22, W / 2, H - 130 + k * 30, (240, 242, 245))
    for s, P3, side in S["labels"]:
        x, yy, dd = cam.proj(np.array([P3], float))
        x, yy = float(x[0]), float(yy[0])
        if dd[0] <= 0 or not (0 < x < W and 0 < yy < H): continue
        if side == 0:  # número sobre la pieza
            d.ellipse((x - 14, yy - 14, x + 14, yy + 14), fill=(20, 24, 30), outline=(255, 200, 100), width=3)
            d.text((x, yy), s, font=F18, fill=(255, 220, 150), anchor="mm"); continue
        lx = min(max(x + side * 80, 70), W - 70); ly = yy - 40
        d.line((x, yy, lx, ly), fill=(255, 200, 100), width=2); d.ellipse((x - 4, yy - 4, x + 4, yy + 4), fill=(255, 200, 100))
        txt(d, s, F18, lx, ly - 22, (255, 224, 170))
    h = S["hud"]
    if h:  # termómetro y luz de la resistencia
        x0, y0, y1 = 52, 300, 760
        d.rounded_rectangle((x0 - 12, y0 - 10, x0 + 12, y1 + 10), 12, fill=(30, 34, 40), outline=(200, 210, 220), width=2)
        T = h["T"]; col = (230, 60, 50) if T > 75 else (240, 120, 50) if T > 40 else (80, 140, 210)
        d.rounded_rectangle((x0 - 5, y1 - (y1 - y0) * min(T, 100) / 100, x0 + 5, y1 + 5), 5, fill=col)
        d.ellipse((x0 - 20, y1 + 2, x0 + 20, y1 + 42), fill=col, outline=(200, 210, 220), width=2)
        for k in range(0, 101, 20):
            yy = y1 - (y1 - y0) * k / 100; d.line((x0 + 14, yy, x0 + 24, yy), fill=(160, 170, 180), width=2)
            d.text((x0 + 28, yy), str(k), font=F18, fill=(160, 170, 180), anchor="lm")
        txt(d, f"{int(T)} °C", F22, x0 + 6, y1 + 50, (255, 255, 255))
        on = h["on"]
        cx, cy = W - 90, 790
        if on: d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(40, 90, 50))
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(90, 230, 120) if on else (90, 30, 30), outline=(220, 220, 220), width=2)
        txt(d, "resistencia", F18, cx, cy + 26, (220, 225, 230))
        txt(d, "ENCENDIDA" if on else "APAGADA", F18, cx, cy + 48, (120, 240, 150) if on else (255, 110, 100))
        txt(d, "vista de rayos X", F18, W / 2, H - 40, (150, 190, 220))

# ---------- música: 144 bpm, buildup al inicio y remate final que cae en el cuadro 0 (loop) ----------
SR = 44100
def music(path):
    import wave
    n = int(SR * N / FPS); t = np.arange(n) / SR
    beat = BEAT / FPS; bar = 4 * beat
    def F(fr): return fr / FPS
    def mtof(m): return 440 * 2 ** ((m - 69) / 12)
    def lp(x, a):
        y, acc = np.empty_like(x), 0.0
        for i, v in enumerate(x.tolist()): acc += a * (v - acc); y[i] = acc
        return y
    def saw(fr, tt, det=(0,)): return sum(((tt * fr * (1 + d) + 0.31 * k) % 1) * 2 - 1 for k, d in enumerate(det)) / len(det)
    def add(buf, st, sig):
        i0 = int(round(st * SR)) % n; L = len(sig)
        idx = (np.arange(L) + i0) % n; np.add.at(buf, idx, sig)          # circular: las colas pasan al inicio del loop
    rng = np.random.default_rng(21)
    pads, bass, lead, drums, fx = (np.zeros(n) for _ in range(5))
    prog = [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]]      # Re menor, Si bemol, Fa, Do
    DROP, TRIP, REARM = F(160), F(920), F(940)
    groove = (t >= DROP) & (t < F(1000)) & ~((t >= TRIP) & (t < REARM))
    for b in range(26):
        ch = prog[b % 4]; s0 = b * bar; tt = np.arange(int(bar * SR)) / SR
        for m in ch + [ch[0] + 12]: add(pads, s0, saw(mtof(m), tt, (-0.011, -0.004, 0.005, 0.012)) * 0.08)
        if 4 <= b < 25 and not 23 <= b < 23.5:
            for k in range(8):
                st_ = s0 + (k + 0.5) * beat / 2
                if TRIP <= st_ < REARM: continue
                tb = np.arange(int(beat / 2 * 0.9 * SR)) / SR
                add(bass, st_, (saw(mtof(ch[0] - 12), tb, (-0.004, 0.004)) + 0.7 * np.sin(2 * np.pi * mtof(ch[0] - 24) * tb)) * np.exp(-tb * 4) * 0.3)
    pump = np.where(groove, 1 - 0.72 * np.exp(-((t / beat) % 1) * 9), 1.0)
    build = np.clip(t / DROP, 0, 1)
    pads = lp(pads, 0.05) * pump * np.where(t < DROP, 0.3 + 0.7 * build ** 2, np.where(t >= F(1000), 0.55, 1))
    bass = lp(bass, 0.12) * pump
    # buildup: un pluck por tiempo que sube, redoble que acelera, ruido que crece
    for k in range(16):
        tt = np.arange(int(0.3 * SR)) / SR; m = [62, 65, 69, 72][k % 4] + 12 + (k // 4) * 2
        add(lead, k * beat, np.sin(2 * np.pi * mtof(m) * tt) * np.exp(-tt * 12) * 0.12 * (0.5 + 0.5 * k / 16))
    for k in range(80):
        st_ = F(40) + F(120) * (1 - (1 - k / 80) ** 1.8)
        tt = np.arange(int(0.04 * SR)) / SR
        add(drums, st_, rng.standard_normal(len(tt)) * np.exp(-tt * 70) * 0.11 * (0.2 + 0.8 * k / 80))
    riser = np.diff(rng.standard_normal(n + 1)) * np.clip((t - F(80)) / F(80), 0, 1) ** 2 * (t < DROP) * 0.13
    riser += np.sin(2 * np.pi * np.cumsum(200 + 1400 * np.clip((t - F(80)) / F(80), 0, 1) ** 2) / SR) * np.clip((t - F(80)) / F(80), 0, 1) ** 2 * (t < DROP) * 0.04
    # melodía original sobre las piezas, más un "blip" que sube un grado por pieza
    phrase = [74, 77, 79, 81, 79, 77, 74, 72, 70, 72, 74, 77, 74, 72, 69, 72]
    for b in range(5, 17):
        for k in range(8):
            m = phrase[((b - 5) % 2) * 8 + k]; tl = np.arange(int(beat / 2 * 0.8 * SR)) / SR
            add(lead, b * bar + k * beat / 2, (np.sign(np.sin(2 * np.pi * mtof(m) * tl)) * 0.5 + saw(mtof(m), tl, (-0.003, 0.003)) * 0.5) * np.exp(-tl * 3) * 0.08)
    scale = [62, 65, 67, 69, 72, 74]
    for p in range(6):
        tt = np.arange(int(0.5 * SR)) / SR; fr = mtof(scale[p] + 12)
        add(fx, F(200 + p * 80), np.sin(2 * np.pi * fr * tt + 2 * np.exp(-tt * 10) * np.sin(4 * np.pi * fr * tt)) * np.exp(-tt * 5) * 0.16)
        tt = np.arange(int(0.3 * SR)) / SR
        add(fx, F(680 + p * BEAT), np.sin(2 * np.pi * fr * tt) * np.exp(-tt * 9) * 0.15 + rng.standard_normal(len(tt)) * np.exp(-tt * 90) * 0.12)
    lead = lp(lead, 0.4)
    # batería: en el buildup el bombo entra a negras en el compás 2; groove completo desde el drop
    for k in range(int(N / BEAT)):
        st_ = k * beat
        if (F(80) <= st_ < DROP) or groove[min(int(st_ * SR), n - 1)]:
            tt = np.arange(int(0.25 * SR)) / SR
            add(drums, st_, np.sin(2 * np.pi * (45 + 150 * np.exp(-tt * 35)) * tt) * np.exp(-tt * 9) * (1 if st_ >= DROP else 0.55))
        if groove[min(int(st_ * SR), n - 1)]:
            if k % 2 == 1:
                tt = np.arange(int(0.16 * SR)) / SR; add(drums, st_, np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt * 20) * 0.15)
            tt = np.arange(int(0.05 * SR)) / SR; add(drums, st_ + beat / 2, np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt * 60) * 0.07)
    for k in range(24):  # tensión antes del disparo del disco
        st_ = F(880) + F(40) * (1 - (1 - k / 24) ** 1.6)
        tt = np.arange(int(0.04 * SR)) / SR; add(drums, st_, rng.standard_normal(len(tt)) * np.exp(-tt * 70) * 0.1 * (0.3 + 0.7 * k / 24))
    for fr_, amp in ((160, 1.0), (920, 1.2)):  # impactos: explosión y disparo del disco
        tt = np.arange(int(1.2 * SR)) / SR
        add(fx, F(fr_), (np.sin(2 * np.pi * (40 + 100 * np.exp(-tt * 20)) * tt) * np.exp(-tt * 3) * 0.6 + rng.standard_normal(len(tt)) * np.exp(-tt * 6) * 0.25) * amp)
    for fr_ in (440, 460, 480, 500, 640, 840, 880):  # clics del microrruptor y del disco, en el tiempo
        tt = np.arange(int(0.05 * SR)) / SR; add(fx, F(fr_), (rng.standard_normal(len(tt)) * 0.6 + np.sin(2 * np.pi * 2600 * tt)) * np.exp(-tt * 110) * 0.35)
    tt = np.arange(int(2.5 * SR)) / SR
    for m in [62, 65, 69, 74, 77]: add(fx, REARM, np.sin(2 * np.pi * mtof(m) * tt) * np.exp(-tt * 1.4) * 0.06)
    tl = np.arange(int(F(40) * SR)) / SR                                  # remate: barrido al revés que cae en el cuadro 0
    add(fx, F(1000), np.diff(rng.standard_normal(len(tl) + 1)) * (tl / tl[-1]) ** 3 * 0.18)
    for k in range(4):
        tt = np.arange(int(0.12 * SR)) / SR; add(drums, F(1000) + (2 + k * 0.5) * beat, np.sin(2 * np.pi * (60 + 120 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14) * 0.35)
    mix = pads + bass + lead + drums + fx + riser
    d = int(beat * 0.75 * SR); mix = mix + 0.25 * np.roll(mix, d)        # eco circular
    out = np.tanh(mix * 1.4); out *= 0.89 / np.abs(out).max()
    st = np.stack([out + 0.1 * np.roll(lead, 400), out + 0.1 * np.roll(pads, 600)], 1); st *= 0.89 / np.abs(st).max()
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())

if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).save(sys.argv[3]); sys.exit()
    from multiprocessing import Pool
    wav, mp4 = os.path.join(HERE, "despiece3d.wav"), os.path.join(HERE, "termostato_despiece_3d.mp4")
    music(wav)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, fr in enumerate(pool.imap(frame, range(N), chunksize=2)):
            ff.stdin.write(fr.tobytes())
            if i % 100 == 0: print("cuadro", i, flush=True)
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("listo:", mp4)
