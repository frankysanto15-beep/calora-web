"""Calora en pixel art: corto vertical de 14 s, 180x320 nativo escalado x6 a 1080x1920.
Técnicas: rampas con desplazamiento de tono, paleta por escena (LUT), iluminación por niveles de rampa,
contorno selectivo (sel-out), sombras como paso de rampa, parallax con ajuste a píxel, bloom re-cuantizado,
rayos de luz y vapor con tramado, disolución por tramado entre planos, sprites a 12 fps sobre cámara a 24.
Uso: python3 pixel_render.py [--still N salida.png]
"""
import sys, os, math, wave, colorsys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, N = 180, 320, 24, 336
HERE = os.path.dirname(os.path.abspath(__file__))
SANS, SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
Y, X = np.mgrid[0:H, 0:W].astype(float)

def hexc(h): return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
def bayer(n):
    m = np.array([[0, 2], [3, 1]])
    while len(m) < n: m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return m / m.size
B4 = np.tile(bayer(4), (H // 4, W // 4))
B8 = np.tile(bayer(8), (H // 8 + 1, W // 8 + 1))[:H, :W]

# ---------- paleta: rampas de 5 tonos con desplazamiento de tono ----------
def turn(h, target, deg):
    d = ((target - h + 180) % 360) - 180
    return (h + math.copysign(min(abs(d), deg), d)) % 360

def ramp(hexbase, tint, amt, vmul):
    c = np.clip((hexc(hexbase) * (1 - amt) + hexc(tint) * amt) * vmul, 0, 1)
    h, s, v = colorsys.rgb_to_hsv(*c); h *= 360
    out = []
    for vf, sf, hue in ((0.45, 1.15, turn(h, 245, 24)), (0.7, 1.08, turn(h, 245, 12)), (1, 1, h), (1.17, 0.85, turn(h, 55, 8)), (1.32, 0.68, turn(h, 55, 16))):
        out.append(colorsys.hsv_to_rgb(hue / 360, min(s * sf, 1), min(v * vf, 1)))
    return np.array(out)

BASES = dict(body="#f0ebdf", green="#2c5247", orange="#df6432", pink="#efbba6", wall="#8fb5ad", floor="#b08d6e", copper="#c07a45",
             frame="#e6dfd0", sky="#2b3a6e", hills="#43406a", town="#2d2b4a", house="#a0948a", roof="#7a3c3c", grass="#2f4d3e",
             light="#ffe6a0", rain="#a9c4e8", glass="#3b5c90")
def palette(tint, amt, vmul):
    return {k: ramp(v, tint, amt, vmul) for k, v in BASES.items()}
NIGHT, COLD, WARM = palette("#3c4f9a", 0.38, 0.82), palette("#4a64a8", 0.26, 0.9), palette("#ffb06a", 0.22, 1.04)
def flatpal(P): return np.concatenate(list(P.values()))

def tone(P, mat, idx):  # idx: array de índices 0..4 -> colores
    return P[mat][np.clip(idx, 0, 4).astype(int)]

def lvl(level, dither=0.7):  # nivel continuo -> índice de rampa, tramado solo en las fronteras entre tonos
    return np.clip(np.floor(level * 5 + (B4 - 0.5) * dither), 0, 4)

# ---------- utilidades de máscara ----------
def shift(m, dy, dx):
    o = np.zeros_like(m)
    o[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = m[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
    return o
def dilate(m, k=1):
    o = m.copy()
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx * dx + dy * dy <= k * k + 0.5: o |= shift(m, dy, dx)
    return o
def ell(cx, cy, rx, ry): return ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 <= 1
def seg(x0, y0, x1, y1, t):
    dx, dy = x1 - x0, y1 - y0
    u = np.clip(((X - x0) * dx + (Y - y0) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
    return (X - x0 - u * dx) ** 2 + (Y - y0 - u * dy) ** 2 <= t * t
def rect(x0, y0, x1, y1): return (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)

def paint(img, m, col, outline=None, lit=None, k=1):
    """pinta una parte; outline=(tono_claro, tono_oscuro) hace sel-out: el contorno se aclara del lado iluminado."""
    if outline is not None:
        ring = dilate(m, k) & ~m
        img[ring] = np.where(lit[ring][:, None], outline[0], outline[1]) if lit is not None else outline[1]
    img[m] = col[m] if np.ndim(col) == 3 else col

# ---------- el termo ----------
def termo(img, P, cx, cy, r, light, mood, t12, wave=False, glint=None, rim=None, tear=None, ol=1):
    hh = 0.65 * r
    L = np.array(light, float); L /= np.linalg.norm(L)
    lit = (X - cx) * L[0] + (Y - cy) * L[1] > 0
    G = P["green"]
    # piernas
    for s in (-1, 1):
        lx = cx + s * 0.36 * r; w = max(2, round(0.17 * r))
        m = rect(round(lx - w / 2), cy + hh + 0.8 * r, round(lx - w / 2) + w, cy + hh + 1.35 * r)
        paint(img, m, tone(P, "orange", np.where(X - lx < 0 if L[0] < 0 else X - lx >= 0, 3, 1)), (G[1], G[0]), lit, ol)
    # cuerpo: normal de cápsula -> nivel -> rampa
    dyc = np.clip(Y - cy, -hh, hh)
    nx, ny = (X - cx) / r, (Y - cy - dyc) / r
    d2 = nx ** 2 + ny ** 2; body = d2 <= 1
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    ndl = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    level = 0.18 + 0.82 * ndl
    if rim is not None:  # luz de contra: borde iluminado del lado de la ventana
        R = np.array(rim, float); R /= np.linalg.norm(R)
        level = level + 0.9 * np.clip(nx * R[0] + ny * R[1], 0, 1) ** 3 * (nz < 0.55)
    idx = lvl(level)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    idx = np.where((nx * Hh[0] + ny * Hh[1] + nz * Hh[2]) > 0.985, 4, idx)
    if glint is not None: idx = np.where(np.abs(nx + 0.35 * ny - glint) < 0.07, 4, idx)
    paint(img, body, tone(P, "body", idx), (G[2], G[0]), lit, ol)
    # cara
    ey, e = cy - 0.2 * r, max(1.3, 0.12 * r)
    blink = mood == "happy" and t12 % 30 in (0, 1)
    for s in (-1, 1):
        ex = cx + s * 0.3 * r
        if blink: img[seg(ex - e, ey, ex + e, ey, max(0.6, 0.03 * r))] = G[0]
        else:
            m = ell(ex, ey, e, e * 1.08)
            if mood == "sad": m &= Y >= ey - 0.45 * e  # párpado caído
            img[m] = G[0]
            img[ell(ex + 0.35 * e, ey - 0.35 * e, max(0.6, 0.32 * e), max(0.6, 0.32 * e))] = P["body"][4]
        by = cy - 0.47 * r
        if mood == "sad":  # cejas tristes: extremo interior más alto
            img[seg(ex - s * 0.15 * r, by - 0.07 * r, ex + s * 0.15 * r, by + 0.05 * r, max(0.6, 0.035 * r))] = G[0]
        else:
            img[seg(ex - 0.14 * r, by + 0.02 * r, ex, by - 0.04 * r, max(0.6, 0.035 * r)) | seg(ex, by - 0.04 * r, ex + 0.14 * r, by + 0.02 * r, max(0.6, 0.035 * r))] = G[0]
        img[ell(cx + s * 0.5 * r, cy + 0.02 * r, max(1, 0.11 * r), max(1, 0.08 * r)) & body] = P["pink"][2]
    my = cy + 0.06 * r
    if mood == "happy":
        img[ell(cx, my, 0.22 * r, 0.2 * r) & (Y >= my)] = G[0]
        img[ell(cx, my + 0.15 * r, 0.09 * r, 0.05 * r) & (Y >= my)] = P["orange"][2]
    else:
        ring = ell(cx, my + 0.18 * r, 0.16 * r, 0.13 * r) & ~ell(cx, my + 0.18 * r, 0.16 * r - max(1, 0.05 * r), 0.13 * r - max(1, 0.05 * r))
        img[ring & (Y <= my + 0.18 * r)] = G[0]
    py = cy + 0.55 * r
    img[rect(cx - 0.26 * r, py - 0.1 * r, cx + 0.26 * r, py + 0.1 * r)] = G[0]
    img[ell(cx - 0.11 * r, py, max(0.8, 0.055 * r), max(0.8, 0.055 * r))] = P["body"][4]
    img[ell(cx + 0.11 * r, py, max(0.8, 0.04 * r), max(0.8, 0.04 * r))] = P["orange"][3]
    if tear is not None:
        tx, ty = cx - 0.3 * r - 0.06 * r, ey + e + tear * 0.5 * r
        img[ell(tx, ty, max(1, 0.035 * r), max(1.5, 0.06 * r))] = P["rain"][4]
    # brazos y manos
    for s in (-1, 1):
        sx, sy = cx + s * 0.97 * r, cy + 0.02 * r
        if wave and s == 1:
            a = [-1.1, -0.75, -1.1, -1.45][(t12 // 2) % 4]
            hx, hy = sx + 0.55 * r * math.cos(a), sy + 0.75 * r * math.sin(a)
        elif mood == "sad": hx, hy = sx + s * 0.18 * r, sy + 0.62 * r
        else: hx, hy = sx + s * 0.3 * r, sy + 0.5 * r
        paint(img, seg(sx, sy, hx, hy, max(0.8, 0.06 * r)), G[1])
        paint(img, ell(hx, hy, max(1.5, 0.15 * r), max(1.5, 0.15 * r)), tone(P, "body", np.where(lit, 4, 2)), (G[2], G[0]), lit, ol)
    return body

# ---------- escenas ----------
def bloom(img, emis, rad=6, k=0.7):
    b = emis.copy()
    for _ in range(3):  # desenfoque de caja separable x3 ~ gaussiano
        c = np.cumsum(np.pad(b, ((0, 0), (rad + 1, rad), (0, 0)), mode="edge"), 1); b = (c[:, 2 * rad + 1:] - c[:, :-2 * rad - 1]) / (2 * rad + 1)
        c = np.cumsum(np.pad(b, ((rad + 1, rad), (0, 0), (0, 0)), mode="edge"), 0); b = (c[2 * rad + 1:] - c[:-2 * rad - 1]) / (2 * rad + 1)
    return img + b * k

def quantize(img, pal, amp=0.07):  # el "shader" de paleta: todo vuelve a la paleta de la escena, con tramado ordenado
    v = np.clip(img, 0, 1) + (B4[..., None] - 0.5) * amp
    d = ((v[..., None, :] - pal[None, None]) ** 2).sum(-1)
    return pal[d.argmin(-1)]

RNG = np.random.default_rng(5)
STARS = [(RNG.uniform(0, 260), RNG.uniform(0, 170), RNG.integers(0, 6)) for _ in range(60)]
RAIN = [(RNG.uniform(0, 260), RNG.uniform(0, 320), RNG.uniform(7, 10)) for _ in range(70)]
TOWN = [(RNG.integers(-20, 330), RNG.integers(14, 40), RNG.integers(10, 24)) for _ in range(30)]

def s1_exterior(f):
    P = NIGHT; t12 = f // 2
    cam = round(40 * (f / 72) ** 0.8)                                   # paneo; cada capa se ajusta a píxel entero
    off = {k: round(cam * v) for k, v in dict(sky=0.05, hills=0.2, town=0.45, house=0.75, fence=1.3).items()}
    moonx, moony = 46 - off["sky"], 52
    glow = np.exp(-((X - moonx) ** 2 + (Y - moony) ** 2) / 900)
    img = tone(P, "sky", lvl((Y < 260) * (0.15 + 0.45 * (Y / 260) ** 1.6 + 0.5 * glow), 1.0))
    for sx, sy, ph in STARS:
        x, y = int(sx - off["sky"]), int(sy)
        if 0 <= x < W and (t12 + ph) % 7: img[y, x] = P["light"][4] if ph % 3 else P["rain"][4]
    emis = np.zeros((H, W, 3))
    moon = ell(moonx, moony, 10, 10)
    img[moon] = tone(P, "frame", lvl(1.0 - 0.6 * ((X - moonx + 4) ** 2 + (Y - moony + 4) ** 2 > 90)))[moon]
    img[ell(moonx + 3, moony + 2, 2, 2) | ell(moonx - 3, moony + 5, 1.5, 1.5)] = P["frame"][2]
    emis[moon] = hexc("#c9d6ff") * 0.6
    hill = 214 + 10 * np.sin((X + off["hills"]) / 23) + 6 * np.sin((X + off["hills"]) / 9.1)
    img[Y > hill] = P["hills"][1]; img[(Y > hill) & (Y <= hill + 1)] = P["hills"][3]     # borde iluminado por la luna
    for tx, tw, th in TOWN:
        x0 = tx - off["town"]
        m = rect(x0, 236 - th, x0 + tw, 262); img[m] = P["town"][1]; img[m & (X == x0)] = P["town"][3]
        if (tx * 7) % 5 == 0: img[rect(x0 + 3, 240 - th, x0 + 5, 243 - th)] = P["light"][2]
    hx = 70 - off["house"]
    img[rect(hx, 196, hx + 64, 262)] = tone(P, "house", lvl(0.55 + 0.25 * (X < hx + 6)))[rect(hx, 196, hx + 64, 262)]
    img[rect(hx + 64, 202, hx + 80, 262) & (Y > 196 + (X - hx - 64) * 0.4)] = P["house"][0]  # cara lateral en sombra
    roof = (Y < 198) & (Y > 166 + np.abs(X - hx - 32) * 0.95) & (X > hx - 6) & (X < hx + 70)
    img[roof] = tone(P, "roof", np.where(X < hx + 32, 3, 1))[roof]
    img[rect(hx + 46, 166, hx + 54, 184) & ~roof] = P["roof"][1]
    win = rect(hx + 12, 210, hx + 32, 232)
    img[dilate(win, 1)] = P["frame"][1]
    img[win] = P["glass"][4]; emis[win] = hexc("#bcd2ff") * 0.9
    img[ell(hx + 22, 226, 4, 6) & win] = P["glass"][2]                               # el termo, en silueta tras la ventana
    img[rect(hx + 21, 210, hx + 23, 232) | rect(hx + 12, 220, hx + 32, 222)] = P["frame"][1]
    img[rect(hx + 40, 226, hx + 52, 262)] = P["roof"][0]
    ground = Y >= 262
    img[ground] = tone(P, "grass", lvl(0.35 - 0.25 * (Y - 262) / 58))[ground]
    img[ground & rect(hx + 12, 262, hx + 32, 276) & (Y < 262 + (X - hx - 12) * 0 + 14)] = P["grass"][2]  # luz de la ventana en el pasto
    for k in range(-1, 12):
        px = k * 22 - off["fence"] % 22
        img[rect(px, 268, px + 4, 320)] = P["town"][0]; img[rect(px, 268, px + 1, 320)] = P["town"][2]
    img[rect(0, 280, W, 283) | rect(0, 300, W, 303)] = P["town"][0]
    for rx, ry, sp in RAIN:
        x0, y0 = (rx - f * sp * 0.25) % 200 - 10, (ry + f * sp) % 340 - 10
        img[seg(x0, y0, x0 - 1, y0 + 4, 0.5)] = P["rain"][3]
    img = bloom(img, emis, 7, 0.55)
    img *= 1 - 0.35 * np.clip(((X - 90) / 120) ** 2 + ((Y - 160) / 200) ** 2, 0, 1)[..., None]  # viñeta
    return quantize(img, flatpal(P)), P

def room(P, lamp, inten, warm, f, tile=14, ox=0, scale=1.0):
    t12 = f // 2
    lx, ly = lamp
    fy = round(232 * scale - (scale - 1) * 160)
    d2 = ((X - lx) ** 2 + (Y - ly) ** 2) / (95 * scale) ** 2
    wl = 0.12 + inten * 0.85 / (1 + 2.2 * d2)
    idx = lvl(wl, 1.0)
    gx, gy = (X + ox) % tile, Y % tile
    idx = np.where((gx == 0) | (gy == 0), idx - 1, np.where((gx == 1) | (gy == 1), idx + 1, idx))  # junta y bisel de azulejo
    img = tone(P, "wall", idx)
    fl = Y >= fy
    ck = (((X + ox) // (20 * scale)) + ((Y - fy) // (10 * scale))) % 2
    img[fl] = tone(P, "floor", lvl(0.2 + inten * 0.6 / (1 + d2)) - ck)[fl]
    img[(Y >= fy - 3) & (Y < fy)] = P["frame"][1]
    return img, fy

def bathroom(P, f, mood, warm):
    t12 = f // 2
    flick = [1, 1, 1, 0.2, 1, 1, 0.5, 1, 1, 1, 1, 0.1, 0.9, 1][t12 % 14] if not warm else 1   # parpadeo de la ampolleta
    lamp = (98, 46)
    img, fy = room(P, lamp, 0.95 * flick if warm else 0.62 * flick, warm, f)
    emis = np.zeros((H, W, 3))
    # ventana
    win = rect(16, 70, 58, 128)
    img[dilate(win, 2)] = P["frame"][2]; img[dilate(win, 2) & ~dilate(win, 1)] = P["frame"][0]
    img[win] = tone(P, "glass", lvl(0.95 - 0.3 * (Y - 70) / 58))[win] if not warm else P["light"][4]
    if not warm:
        for rx, ry, sp in RAIN[:14]:
            x0, y0 = 16 + rx % 42, 70 + (ry + f * sp * 0.3) % 58
            img[seg(x0, y0, x0, y0 + 3, 0.5) & win] = P["rain"][4]
    else: emis[win] = hexc("#fff0c0") * 1.0
    img[rect(36, 70, 38, 128) | rect(16, 98, 58, 100)] = P["frame"][1]
    # ducha de cobre
    img[rect(150, 40, 154, 150)] = tone(P, "copper", np.where(X < 152, 3, 1))[rect(150, 40, 154, 150)]
    img[rect(136, 40, 154, 44)] = P["copper"][2]
    img[rect(130, 44, 142, 49)] = P["copper"][1]; img[rect(130, 44, 142, 45)] = P["copper"][4]
    if not warm:  # gota cayendo, a 12 fps
        dy = (t12 * 9) % 140
        img[ell(136, 52 + dy, 1, 1.6)] = P["rain"][4]
    # ampolleta colgante
    lx, ly = lamp
    img[rect(lx, 0, lx + 1, ly - 6)] = P["green"][0]
    img[rect(lx - 3, ly - 7, lx + 4, ly - 3)] = P["copper"][1]
    bulb = ell(lx + 0.5, ly, 4.5, 4.5)
    img[bulb] = P["light"][4] if flick > 0.6 else P["light"][1]
    emis[bulb] = (hexc("#ffe3a0") if warm else hexc("#d8e6ff")) * flick * 1.4
    # termo: sombra proyectada en la pared (un paso de rampa), sombra de contacto en el suelo
    cx, r = 92, 26; cy = fy - 2 * r - 2                                   # pies sobre el piso
    sh = ell(cx + 9, cy + 8, r + 1, r + 0.65 * r + 2) & (Y < fy - 3)
    img[sh] = np.clip(img[sh] * 0.72, 0, 1)
    cs = ell(cx, fy + 3, r * 1.05, 4)
    img[cs] = img[cs] * 0.6
    hop = [0, -1, -3, -1][t12 % 4] if warm else (1 if t12 % 3 == 0 else 0)        # rebote feliz / temblor de frío
    body_light = (lx - cx, ly - cy, 60)
    termo(img, P, cx + (hop if not warm else 0), cy + (hop if warm else 0), r, body_light, mood, t12, wave=warm,
          glint=(-1.2 + ((f - 268) / 14)) if warm and 268 <= f < 300 else None, rim=(-1, -0.3) if warm else None)
    if warm:  # rayos de luz por la ventana y polvo flotante
        u = (X - 16) * 0.6 - (Y - 70) * 0.8
        band = np.clip(1 - np.abs(((u + 6) % 22) - 11) / 6, 0, 1) * ((X - 16) * 0.8 + (Y - 70) * 0.6 > 0)
        fall = np.exp(-(((X - 16) * 0.8 + (Y - 70) * 0.6) / 150) ** 2)
        img = img + (band * fall * 0.28)[..., None] * hexc("#ffd89a")
        for k in range(14):
            px = (20 + k * 37 + t12 * (1 + k % 3)) % 120 + 30; py = (80 + k * 53 - t12 * 2) % 150 + 70
            if band[int(py), int(px)] > 0.2: img[int(py), int(px)] = P["light"][4]
        for k in range(8):  # vapor de la ducha, transparente por tramado
            age = ((f * 0.8 + k * 17) % 60) / 60
            vx, vy = 132 + 8 * math.sin(k + f / 15), 120 - age * 90
            img = img + (np.exp(-((X - vx) ** 2 + (Y - vy) ** 2) / (40 + 220 * age)) * 0.33 * (1 - age))[..., None]
    img = bloom(img, emis, 6, 0.6)
    if not warm: img *= 1 - 0.4 * np.clip(((X - 90) / 110) ** 2 + ((Y - 160) / 190) ** 2, 0, 1)[..., None]
    return quantize(img, flatpal(P)), P

def s3_closeup(f):
    P = COLD; t12 = f // 2
    img, _ = room(P, (40, -30), 0.75, False, f, tile=28, ox=12, scale=2.0)
    r = 48 + (f - 168) // 6                                              # acercamiento lento en escalones de 1 px
    termo(img, P, 90, 176, r, (-50, -200, 90), "sad", t12, tear=min(max((f - 180) / 30, 0), 1.4), ol=2)
    img *= 1 - 0.45 * np.clip(((X - 90) / 105) ** 2 + ((Y - 170) / 180) ** 2, 0, 1)[..., None]
    return quantize(img, flatpal(P)), P

# ---------- texto ----------
def text(im, s, font, cx, y, fill, out, shadow=True):
    d = ImageDraw.Draw(im); d.fontmode = "1"
    x = round(cx - font.getlength(s) / 2)
    if shadow: d.text((x + 1, y + 2), s, font=font, fill=out)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)): d.text((x + dx, y + dy), s, font=font, fill=out)
    d.text((x, y), s, font=font, fill=fill)
def rgb(c): return tuple(int(v * 255 + 0.5) for v in c)
F10, F11, F30 = ImageFont.truetype(SANS, 10), ImageFont.truetype(SANS, 11), ImageFont.truetype(SERIF, 30)

def frame(f):
    if f < 72: img, P = s1_exterior(f)
    elif f < 168: img, P = bathroom(COLD, f, "sad", False)
    elif f < 216: img, P = s3_closeup(f)
    elif f < 228:  # disolución por tramado 8x8, en pasos de 12 fps
        a, _ = s3_closeup(f); b, P = bathroom(WARM, f, "happy", True)
        p = ((f - 216) // 2 + 1) / 6
        img = np.where((B8 < p)[..., None], b, a)
    else: img, P = bathroom(WARM, f, "happy", True)
    if f < 8: img = img * np.floor(f / 2 + 1) / 4                     # entrada desde negro en 4 escalones
    im = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    G, Bd, O = rgb(P["green"][0]), rgb(P["body"][4]), rgb(P["orange"][2])
    if 10 <= f < 72:
        s = "Una noche cualquiera..."
        text(im, s[:max(0, (f - 10) // 2)], F10, W / 2, 24, Bd, G)
    if 176 <= f < 216:
        text(im, "¿Agua fría otra vez?", F11, W / 2, 272, Bd, G)
    if f >= 262:
        k = min((f - 262) // 2, 5)
        y = [-30, 0, 14, 26, 22, 24][k]                                   # caída con rebote, posiciones enteras
        text(im, "calora", F30, W / 2 + 8, y, rgb(P["body"][4]), G)
        d = ImageDraw.Draw(im)
        dx = W / 2 - 52
        d.polygon([(dx, y + 12), (dx - 6, y + 24), (dx - 4, y + 30), (dx + 4, y + 30), (dx + 6, y + 24)], fill=O, outline=G)
    if f >= 282: text(im, "Mantención de termos", F11, W / 2, 62, Bd, G)
    if f >= 300 and (f // 6) % 4: text(im, "¡Agua caliente otra vez!", F10, W / 2, 290, rgb(P["light"][4]), G)
    out = np.asarray(im)
    if f in (0, 100, 200, 300):  # autocomprobación: todo píxel pertenece a la paleta de la escena (o al negro de la entrada)
        pal = {tuple(rgb(c)) for c in flatpal(P)} | {tuple(rgb(c)) for Q in (COLD, WARM) for c in flatpal(Q)}
        bad = {tuple(c) for c in out.reshape(-1, 3)} - pal
        assert f < 8 or not bad, f"colores fuera de paleta en {f}: {len(bad)}"
    return out

# ---------- sonido ----------
SR = 44100
def music(path):
    n = int(SR * N / FPS); t = np.arange(n) / SR; out = np.zeros(n)
    def mtof(m): return 440 * 2 ** ((m - 69) / 12)
    def pluck(st, m, dur=1.2, amp=0.12, bright=1.0):
        i0 = int(st * SR); L = min(int(dur * SR), n - i0)
        if L <= 0: return
        tt = np.arange(L) / SR; fr = mtof(m)
        out[i0:i0 + L] += (np.sin(2 * np.pi * fr * tt) + 0.3 * bright * np.sin(4 * np.pi * fr * tt) * np.exp(-tt * 8)) * np.exp(-tt * 4) * amp
    rng = np.random.default_rng(2)
    noise = rng.standard_normal(n)
    rain = np.empty(n); acc = 0.0
    for i, v in enumerate(noise.tolist()): acc += 0.18 * (v - acc); rain[i] = acc  # lluvia: ruido filtrado
    env = np.interp(t, [0, 0.4, 3, 3.05, 9, 9.5], [0, 1, 1, 0.45, 0.45, 0])         # adentro suena más apagada
    out += rain * env * 0.16
    for st in np.arange(3, 9, 0.5) + 0.04: pluck(st, 96, 0.08, 0.04)             # goteo
    sad = [69, 72, 76, 74, 72, 71, 69, 64, 65, 69, 72, 71]
    for k, m in enumerate(sad): pluck(3.2 + k * 0.5, m, 1.4, 0.1)
    for st, ch in ((3.2, [45, 52, 57]), (6.2, [41, 48, 53])):
        for m in ch:
            i0 = int(st * SR); L = int(3 * SR); tt = np.arange(L) / SR
            out[i0:i0 + L] += np.sin(2 * np.pi * mtof(m) * tt) * np.minimum(tt / 0.8, 1) * np.exp(-tt * 0.5) * 0.05
    i0, L = int(8.6 * SR), int(0.9 * SR); tt = np.arange(L) / SR               # subida hacia el plano cálido
    out[i0:i0 + L] += noise[:L] * (tt / 0.9) ** 2 * 0.12 + np.sin(2 * np.pi * (300 + 900 * tt ** 2) * tt) * (tt / 0.9) ** 2 * 0.05
    bpm = 0.5
    for st, ch in ((9.5, [48, 55, 59, 64]), (11.5, [53, 57, 60, 64]), (12.5, [48, 55, 60, 64])):
        for m in ch:
            i0 = int(st * SR); L = min(int(3 * SR), n - i0); tt = np.arange(L) / SR
            out[i0:i0 + L] += np.sin(2 * np.pi * mtof(m) * tt) * np.minimum(tt / 0.2, 1) * np.exp(-tt * 0.7) * 0.05
    arp = [72, 76, 79, 83, 79, 76]
    for k in range(18): pluck(9.5 + k * bpm / 2, arp[k % 6] + (5 if 11.5 <= 9.5 + k * bpm / 2 < 12.5 else 0), 0.5, 0.06, 1.5)
    for k in range(9):
        i0 = int((9.5 + k * bpm) * SR); L = int(0.25 * SR); tt = np.arange(L) / SR
        out[i0:i0 + L] += np.sin(2 * np.pi * (50 + 80 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 10) * 0.3
    for k, m in enumerate([84, 88, 91, 96]): pluck(10.95 + k * 0.08, m, 1.6, 0.08, 2)
    d = int(0.23 * SR); out[d:] += out[:-d] * 0.3
    out = np.tanh(out * 1.3); out *= 0.89 / np.abs(out).max()
    out *= np.minimum(1, (n - np.arange(n)) / (0.3 * SR))
    st = np.stack([out, np.roll(out, 220)], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())

if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).resize((W * 3, H * 3), Image.NEAREST).save(sys.argv[3]); sys.exit()
    from multiprocessing import Pool
    wav, mp4 = os.path.join(HERE, "calora_pixel.wav"), os.path.join(HERE, "calora_pixel.mp4")
    music(wav)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for fr in pool.imap(frame, range(N), chunksize=4): ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("listo:", mp4)
