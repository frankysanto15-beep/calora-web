"""Despiece animado del termostato de varilla de un termo eléctrico (pixel art 270x480 -> 1080x1920).
Música a 144 bpm = 10 cuadros por tiempo a 24 fps: cada corte, pieza y clic cae en un tiempo.
Uso: python3 despiece_render.py [--still N salida.png]
"""
import sys, os, math, wave, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixel_render import ramp, hexc, bayer, bloom, text, rgb, SANS

W, H, FPS = 270, 480, 24
BEAT, BAR = 10, 40
N = 29 * BAR
HERE = os.path.dirname(os.path.abspath(__file__))
Y, X = np.mgrid[0:H, 0:W].astype(float)
B4 = np.tile(bayer(4), (H // 4, W // 4 + 1))[:H, :W]
B8 = np.tile(bayer(8), (H // 8, W // 8 + 1))[:H, :W]

BASES = dict(plastic="#dedbd3", dark="#3d424a", copper="#c8743c", brass="#d2a43e", steel="#b4bcc3", red="#d23c32", bg="#262a33",
             paper="#2b5da3", line="#dbe7f7", hot="#e8692c", water="#4c8ccf", ok="#46b05c", light="#ffe39a")
P = {k: ramp(v, "#ffffff", 0, 1) for k, v in BASES.items()}
PAL = np.concatenate(list(P.values()))

def lvl(level, d=0.7): return np.clip(np.floor(level * 5 + (B4 - 0.5) * d), 0, 4).astype(int)
def quantize(img, amp=0.06):
    v = np.clip(img, 0, 1) + (B4[..., None] - 0.5) * amp
    return PAL[((v[..., None, :] - PAL[None, None]) ** 2).sum(-1).argmin(-1)]
def shift(m, dy, dx):
    o = np.zeros_like(m)
    o[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = m[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
    return o
def ring(m): return (shift(m, 1, 0) | shift(m, -1, 0) | shift(m, 0, 1) | shift(m, 0, -1)) & ~m
def ease(a, b, f, back=False):
    t = min(max((f - a) / (b - a), 0), 1)
    if back: c = 1.7; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2   # sobrepasa y vuelve
    return t * t * (3 - 2 * t)

# ---------- el aparato, en milímetros: origen = centro superior del cabezal, y hacia abajo ----------
EXPLODE = {1: (-42, -8), 2: (-40, 50), 3: (0, -30), 4: (42, 40), 5: (0, 30), 6: (42, -4)}
ROD = 100  # varilla dibujada acortada (la real mide 220-450 mm), con marcas de corte

class Dev:
    def __init__(s, img, ox, oy, sc, e=0.0, flip=False, xray=False, mode="real"):
        s.img, s.ox, s.oy, s.sc, s.e, s.flip, s.xray, s.mode = img, ox, oy, sc, e, flip, xray, mode
        s.masks = {k: np.zeros((H, W), bool) for k in range(1, 7)}
        s.lines = np.zeros((H, W), bool)
    def off(s, part):
        dx, dy = EXPLODE[part]; return dx * s.e, dy * s.e
    def px(s, x, y, part):
        dx, dy = s.off(part); x, y = x + dx, y + dy
        return s.ox + x * s.sc, s.oy + (-y if s.flip else y) * s.sc
    def rect(s, x0, y0, x1, y1, part, r=0):
        a, b = s.px(x0, y0, part); c, d = s.px(x1, y1, part)
        xa, xb, ya, yb = min(a, c), max(a, c), min(b, d), max(b, d)
        m = (X >= round(xa)) & (X < round(xb)) & (Y >= round(ya)) & (Y < round(yb))
        if r:
            rr = r * s.sc
            cx = np.clip(X, xa + rr, xb - rr); cy = np.clip(Y, ya + rr, yb - rr)
            m &= (X - cx) ** 2 + (Y - cy) ** 2 <= rr * rr
        return m
    def ell(s, cx, cy, rx, ry, part):
        a, b = s.px(cx, cy, part)
        return ((X - a) / (rx * s.sc)) ** 2 + ((Y - b) / (ry * s.sc)) ** 2 <= 1
    def seg(s, x0, y0, x1, y1, t, part):
        a, b = s.px(x0, y0, part); c, d = s.px(x1, y1, part)
        dx, dy = c - a, d - b
        u = np.clip(((X - a) * dx + (Y - b) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
        return (X - a - u * dx) ** 2 + (Y - b - u * dy) ** 2 <= max(t * s.sc, 0.6) ** 2
    def lx(s, part, x0):  # coordenada local x en mm (para sombreado cilíndrico)
        dx, _ = s.off(part); return ((X - s.ox) / s.sc - dx - x0)
    def fill(s, m, col, part, outline=True, see=False):
        if s.mode == "sketch":
            s.lines |= ring(m); s.masks[part] |= m; return
        if see: m = m & (B4 < 0.5)                                     # transparencia por tramado ("rayos X")
        s.img[m] = col[m] if np.ndim(col) == 3 else col
        if outline:  # contorno selectivo: más claro arriba-izquierda, oscuro abajo-derecha
            r = ring(m); lit = shift(m, 1, 1) & r
            s.img[r & lit] = P["dark"][2]; s.img[r & ~lit] = P["dark"][0]
        s.masks[part] |= m

def tone(mat, idx): return P[mat][np.clip(idx, 0, 4)]

def draw_device(d, knob=-0.6, closed=True, ext=0.0, disc_flipped=False, invar_out=None, glint=None):
    e = d.e
    io = (16 * e) if invar_out is None else invar_out
    # 5 · varilla sensora: varilla interior de invar, tubo de cobre, collarín de latón
    m = d.rect(-1, 46, 1, 48 + ROD + io, 5)
    d.fill(m, P["steel"][3], 5, outline=False)
    tube_end = 48 + ROD + ext
    m = d.rect(-3.2, 48, 3.2, tube_end, 5)
    lx = d.lx(5, 0)
    d.fill(m, tone("copper", lvl(0.55 - 0.55 * lx / 3.2 + 0.25 * (np.abs(lx + 1.2) < 0.9))), 5)
    if glint is not None: d.img[m & (np.abs(Y - glint) < 3)] = P["copper"][4]
    d.fill(d.ell(0, tube_end, 3.2, 2.5, 5) & ~d.rect(-4, tube_end - 4, 4, tube_end, 5), P["copper"][1], 5)
    if d.mode == "real":  # marcas de corte: la varilla sigue, pero se dibuja acortada
        for k in (0, 4): d.img[d.seg(-6, 88 + k, 6, 84 + k, 0.5, 5)] = P["plastic"][4]
    m = d.rect(-6, 41, 6, 49, 5, r=1)
    d.fill(m, tone("brass", lvl(0.7 - 0.4 * (d.lx(5, 0) > 0))), 5)
    # 4 · microrruptor (por dentro del cabezal)
    def switch():
        m = d.rect(-11, 24, 11, 35, 4, r=1)
        d.fill(m, tone("dark", lvl(0.35 + 0.2 * (Y < d.px(0, 27, 4)[1]))), 4)
        d.fill(d.rect(-3, 21, 3, 24, 4), P["plastic"][4], 4)
        d.fill(d.seg(-10, 22, 9, 20 if closed else 15, 0.8, 4), P["light"][4] if d.xray else P["steel"][4], 4, outline=False)
        for tx in (-7, 0, 7): d.fill(d.rect(tx - 1, 35, tx + 1, 39, 4), P["brass"][3], 4, outline=False)
    switch()
    # 6 · disco bimetálico de seguridad (por dentro), con su botón de rearme que asoma arriba
    disc = d.ell(16, 13, 6, 6, 6)
    a, b = d.px(16, 13, 6)
    sh = ((X - a) * (1 if not disc_flipped else -1) + (Y - b) * (1 if not disc_flipped else -1)) / (6 * d.sc)
    d.fill(disc, tone("steel", lvl(0.6 - 0.45 * sh)), 6)
    d.fill(d.ell(16, 13, 2.5, 2.5, 6), P["steel"][4 if not disc_flipped else 1], 6, outline=False)
    # 2 · carcasa
    m = d.rect(-25, 0, 25, 42, 2, r=4)
    yl = (Y - d.px(0, 0, 2)[1]) / (42 * d.sc)
    xl = d.lx(2, 0) / 25
    d.fill(m, tone("plastic", lvl(0.78 - 0.25 * xl - 0.2 * yl)), 2, see=d.xray)
    for sx in (-19, 19):
        d.fill(d.ell(sx, 36, 1.6, 1.6, 2), P["plastic"][1], 2, outline=False, see=d.xray)
    for k in range(9):  # escala de la perilla
        a_ = -2.3 + 4.6 * k / 8
        d.fill(d.seg(15 * math.sin(a_), 20 - 15 * math.cos(a_), 17.5 * math.sin(a_), 20 - 17.5 * math.cos(a_), 0.5, 2),
               P["red"][2] if k >= 6 else P["dark"][1], 2, outline=False, see=d.xray)
    # 1 · perilla
    m = d.ell(0, 20, 11.5, 11.5, 1)
    cx, cy = d.px(0, 20, 1)
    ang = np.arctan2(Y - cy, X - cx)
    notch = (np.cos(ang * 12) > 0.6) & ~d.ell(0, 20, 9.8, 9.8, 1)
    d.fill(m, tone("dark", lvl(0.55 - 0.3 * ((X - cx) + (Y - cy)) / (11.5 * d.sc)) + notch * 1), 1)
    d.fill(d.seg(0, 20, 8.5 * math.sin(knob), 20 - 8.5 * math.cos(knob), 1.0, 1), P["plastic"][4], 1, outline=False)
    # botón de rearme (va con la seguridad)
    pop = 2.5 if disc_flipped else 0
    d.fill(d.rect(13, 2 - pop, 20, 8 - pop, 6, r=1), tone("red", lvl(np.where(d.lx(6, 16.5) < 0, 0.8, 0.5))), 6)
    # 3 · bornes faston de 6,35 mm
    for tx in (-14, 0, 14):
        m = d.rect(tx - 3.2, -9, tx + 3.2, 0, 3)
        d.fill(m, tone("brass", lvl(np.where(d.lx(3, tx) < 0, 0.85, 0.55))), 3)
        d.fill(d.ell(tx, -5, 1.2, 1.2, 3), P["dark"][0], 3, outline=False)
    if d.xray: switch()                                                  # en la vista transparente, el interruptor va al frente

# ---------- escenarios ----------
def backdrop(f, blueprint=False):
    if blueprint:
        img = np.broadcast_to(P["paper"][2], (H, W, 3)).copy()
        img[(X % 12 == 0) | (Y % 12 == 0)] = P["paper"][3]
        return img
    v = 0.15 + 0.3 * np.exp(-((X - 140) ** 2 + (Y - 230) ** 2) / 26000)
    img = P["bg"][lvl(v, 1.0)]
    img[(X % 16 == 0) & (Y % 16 == 0)] = P["bg"][3]
    return img

def thermometer(img, x, y0, y1, T, tmax=100):
    tube = (X >= x - 3) & (X < x + 4) & (Y >= y0) & (Y < y1)
    img[ring(tube)] = P["dark"][0]; img[tube] = P["plastic"][4]
    lv = y1 - (y1 - y0) * min(T, tmax) / tmax
    c = P["red"][2] if T > 75 else P["hot"][2] if T > 40 else P["water"][2]
    img[(X >= x - 1) & (X < x + 2) & (Y >= lv) & (Y < y1 + 3)] = c
    bulb = (X - x - 0.5) ** 2 + (Y - y1 - 6) ** 2 <= 36
    img[ring(bulb)] = P["dark"][0]; img[bulb] = c
    for k in range(0, tmax + 1, 20):
        yy = round(y1 - (y1 - y0) * k / tmax); img[(Y == yy) & (X >= x + 5) & (X < x + 9)] = P["plastic"][2]

def lamp(img, emis, x, y, on):
    m = (X - x) ** 2 + (Y - y) ** 2 <= 30
    img[ring(m)] = P["dark"][0]; img[m] = P["ok"][4] if on else P["red"][0]
    if on: emis[m] = hexc("#a8ffb8") * 1.3

def tank_scene(f, img, emis):
    tx0, tx1, ty0, ty1 = 60, 210, 92, 390
    shell = (X >= tx0) & (X < tx1) & (Y >= ty0) & (Y < ty1) & (((X - np.clip(X, tx0 + 30, tx1 - 30)) ** 2 + (Y - np.clip(Y, ty0 + 30, ty1 - 30)) ** 2) <= 900)
    inner = (X >= tx0 + 5) & (X < tx1 - 5) & (Y >= ty0 + 5) & (Y < ty1 - 5) & (((X - np.clip(X, tx0 + 30, tx1 - 30)) ** 2 + (Y - np.clip(Y, ty0 + 30, ty1 - 30)) ** 2) <= 625)
    img[shell] = P["plastic"][lvl(0.75 - 0.3 * (X > 135))][shell]; img[ring(shell)] = P["dark"][0]
    hot = B4 < np.clip((250 - Y) / 30 + 0.5, 0, 1)
    img[inner] = np.where(hot[inner][:, None], P["hot"][3], P["water"][3])
    k = np.arange(0, 9)  # resistencia en zigzag, encendida
    pts = [(110 + (5 if i % 2 else -5), 378 - i * 12) for i in k]
    for (a, b), (c, d) in zip(pts, pts[1:]):
        dx, dy = c - a, d - b
        u = np.clip(((X - a) * dx + (Y - b) * dy) / (dx * dx + dy * dy), 0, 1)
        m = (X - a - u * dx) ** 2 + (Y - b - u * dy) ** 2 <= 2.2
        img[m] = P["light"][4]; emis[m] = hexc("#ffb060")
    vaina = (X >= 156) & (X < 166) & (Y >= 240) & (Y < 392)
    img[vaina] = P["steel"][2]; img[ring(vaina)] = P["dark"][0]
    img[(X >= 96) & (X < 176) & (Y >= 386) & (Y < 394)] = P["steel"][3]
    d = Dev(img, 161, 430, 0.62, flip=True)
    draw_device(d)
    if f % 20 < 12:
        for k in range(6): img[(np.abs(X - 161) <= 1) & (np.abs(Y - (245 + ((f // 2) * 3 + k * 25) % 140)) <= 1) & vaina] = P["light"][3]

CAPS = []
def frame_img(f):
    """devuelve (imagen cuantizada, lista de textos (str, fuente, cx, y, color))"""
    emis = np.zeros((H, W, 3)); texts = []
    ox, oy, sc = 135, 150, 1.8
    if f < 160:  # boceto que se dibuja al ritmo, luego se "materializa"
        sk = backdrop(f, True)
        d = Dev(sk, ox, oy, sc, mode="sketch"); draw_device(d)
        reveal = Y < 60 + (f // BEAT) * 32                                  # cada tiempo baja una franja del dibujo
        sk[d.lines & reveal] = P["line"][4]
        if f >= 70:  # cotas
            yh = round(d.px(0, -14, 2)[1]); xa, xb = round(d.px(-25, 0, 2)[0]), round(d.px(25, 0, 2)[0])
            sk[(Y == yh) & (X >= xa) & (X <= xb)] = P["line"][3]
            xr = round(d.px(-14, 0, 5)[0]); ya, yb = round(d.px(0, 48, 5)[1]), round(d.px(0, 48 + ROD, 5)[1])
            sk[(X == xr) & (Y >= ya) & (Y <= yb)] = P["line"][3]
            texts += [("50 mm", F10, ox, yh - 12, P["line"][4]), ("220 mm", F10, xr - 24, (ya + yb) // 2, P["line"][4]),
                      ("Ø 6 mm", F10, ox + 34, (ya + yb) // 2 + 30, P["line"][4]), ("(varilla acortada en el dibujo)", F10, W / 2, 456, P["line"][3])]
        img = sk
        if f >= 120:
            real = backdrop(f); draw_device(Dev(real, ox, oy, sc))
            img = np.where((B8 < ((f - 120) // BEAT + 1) / 4)[..., None], real, sk)
        texts += [("EL TERMOSTATO DE VARILLA", F14, W / 2, 16, P["light"][4]), ("boceto técnico · vista frontal", F10, W / 2, 36, P["line"][4])]
    elif f < 240:
        img = backdrop(f); tank_scene(f, img, emis)
        texts += cap(["Se instala desde abajo: la varilla", "entra en una vaina, junto a la", "resistencia, y así mide el agua."])
        texts += [("vaina", F10, 210, 300, P["plastic"][4]), ("resistencia", F10, 60, 330, P["plastic"][4]), ("termostato", F10, 215, 432, P["plastic"][4])]
    elif f < 840:
        img = backdrop(f)
        if f < 320:
            shake = [0, 1, 0, -1][(f // 2) % 4] * (1 if f >= 280 else 0)
            d = Dev(img, ox + shake, oy, sc); draw_device(d, glint=150 + (f - 240) * 4 if f < 280 else None)
            texts += cap(["Ahora, desarmémoslo", "pieza por pieza."])
        else:
            e = ease(320, 328, f - (f % 2), back=True)
            part = (f - 360) // 80 + 1 if f >= 360 else None
            st = dict(knob=-0.6, closed=True, ext=0.0, disc_flipped=False)
            local = (f - 360) % 80
            if part == 1: st["knob"] = [-1.6, -0.6, 0.6, 1.6, 0.6, -0.6, -1.6, -0.6][(local // BEAT) % 8]
            if part == 4: st["closed"] = (local // 20) % 2 == 0
            if part == 5: st["ext"] = 6 * ease(0, 50, local)
            if part == 6: st["disc_flipped"] = local >= 40
            d = Dev(img, ox, oy, sc, e=e); draw_device(d, **st)
            if part:  # foco: todo lo demás se apaga un tono
                keep = d.masks[part]
                img[~keep] *= 0.42
                glow = ring(keep) & ~keep
                img[glow] = P["light"][3]
                if part == 3:  # corriente entrando por los bornes
                    for k in range(3):
                        yy = d.px(0, -9, 3)[1] - 6 - ((local * 2 + k * 9) % 26)
                        for tx in (-14, 0, 14):
                            xx = d.px(tx, 0, 3)[0]
                            m = (np.abs(X - xx) <= 1) & (np.abs(Y - yy) <= 1); img[m] = P["light"][4]; emis[m] = hexc("#ffe08a")
                if part == 5 and local > 4:
                    a, b = d.px(0, 268 + st["ext"], 5)
                    img[(np.abs(X - a) <= 0.5) & (Y > b + 3) & (Y < b + 12)] = P["hot"][4]
                texts += PARTCAPS[part]
            if f >= 330:
                for k in range(1, 7):
                    cx, cy = TAGPOS[k]; a, b = d.px(cx, cy, k)
                    texts.append(("TAG" + str(k), F10, a, b, P["light"][4] if part in (None, k) else P["plastic"][1]))
    else:
        img = backdrop(f)
        if f < 900:  # se rearma: una pieza por tiempo
            k_done = (f - 840) // BEAT + 1
            d = Dev(img, ox, oy, sc, e=0.0)
            d.e = 0
            # dibuja armado y desplaza a las piezas que aún no llegan (orden 5,4,6,2,1,3)
            order = [5, 4, 6, 2, 1, 3]
            pending = order[k_done:]
            EX_SAVE = dict(EXPLODE)
            for p_ in EXPLODE: EXPLODE[p_] = EX_SAVE[p_] if p_ in pending else (0, 0)
            d.e = 1.0; draw_device(d)
            EXPLODE.update(EX_SAVE)
            texts += cap(["Todo junto otra vez..."])
        else:
            T, closed, flipped, knob = work_state(f)
            ox2 = 145
            d = Dev(img, ox2, oy, sc, xray=True)
            draw_device(d, knob=knob, closed=closed, ext=8 * max(T - 20, 0) / 70, disc_flipped=flipped)
            thermometer(img, 40, 150, 380, T)
            lamp(img, emis, 232, 150, closed and not flipped)
            texts += [(f"{int(T)} °C", F12, 42, 392, P["plastic"][4]), ("resistencia", F10, 232, 160, P["plastic"][4]),
                      ("ENCENDIDA" if closed and not flipped else "APAGADA", F10, 232, 172, P["ok"][4] if closed and not flipped else P["red"][3]),
                      ("vista transparente", F10, 160, 456, P["plastic"][1])]
            texts.append(("microrruptor", F10, 145, 232, P["light"][3]))
            if f < 1000: texts += cap(["Fijas 60 °C. El agua se calienta,", "el tubo crece y... ¡clic!", "la resistencia se apaga."])
            elif f < 1040: texts += cap(["Al enfriarse unos grados, el tubo", "se acorta y vuelve a encender."])
            elif f < 1080: texts += cap(["¿Y si el interruptor se pega?", "La temperatura sigue subiendo..."])
            elif f < 1100: texts += cap(["¡El disco de seguridad salta", "y corta todo!"])
            else: texts += cap(["Solo vuelve a funcionar apretando", "el botón de rearme, después de", "revisar por qué falló."])
            if 1080 <= f < 1092: img[...] = img + (1 - img) * 0.3 * (1 - (f - 1080) / 12)   # destello del disparo
    img = quantize(bloom(img, emis, 5, 0.6))
    return img, texts

def work_state(f):
    knob = -0.6 + 0.9 * ease(900, 910, f)
    if f < 1000: T = 20 + 41 * ease(915, 998, f)
    elif f < 1040: T = 61 - 6 * ease(1000, 1038, f)
    elif f < 1080: T = 55 + 37 * ease(1040, 1080, f)
    else: T = 92 - 4 * ease(1080, 1160, f)
    if f < 1000: closed = True
    elif f < 1040: closed = False
    else: closed = True                          # en la falla, el contacto queda pegado
    return T, closed, 1080 <= f < 1104, knob                         # el disco se rearma al apretar el botón

F10, F12, F14 = ImageFont.truetype(SANS, 10), ImageFont.truetype(SANS, 12), ImageFont.truetype(SANS, 14)
def cap(lines, y=10):
    return [(s, F12, W / 2, y + k * 15, P["plastic"][4]) for k, s in enumerate(lines)]
def pcap(title, lines):
    return [(title, F14, W / 2, 8, P["light"][4])] + cap(lines, 28)
PARTCAPS = {
    1: pcap("1 · PERILLA", ["Con ella eliges a qué temperatura", "se apaga la resistencia."]),
    2: pcap("2 · CARCASA", ["Plástico que cubre y aísla las", "piezas que llevan corriente."]),
    3: pcap("3 · BORNES", ["Aquí se conectan los cables: entra", "la corriente y va a la resistencia."]),
    4: pcap("4 · MICRORRUPTOR", ["Es el interruptor: con un clic", "deja pasar o corta la corriente."]),
    5: pcap("5 · VARILLA SENSORA", ["Tubo de cobre con una varilla que", "casi no se dilata. Con el calor el", "tubo crece y empuja el interruptor."]),
    6: pcap("6 · DISCO DE SEGURIDAD", ["Si el agua pasa de unos 90 °C, se", "da vuelta y corta todo. Queda", "bloqueado hasta rearmarlo."]),
}
TAGPOS = {1: (-15, 6), 2: (-29, 4), 3: (-21, -5), 4: (-15, 26), 5: (-9, 110), 6: (24, -2)}

def frame(f):
    img, texts = frame_img(f)
    if f >= 160 and f < 168:  # disolución tramada entre escenas, al ritmo
        prev, _ = frame_img(159); img = np.where((B8 < ((f - 160) // 2 + 1) / 4)[..., None], img, prev)
    im = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    dr = ImageDraw.Draw(im); dr.fontmode = "1"
    for s, fnt, cx, y, col in texts:
        if s.startswith("TAG"):
            dr.ellipse((cx - 6, y - 6, cx + 6, y + 6), fill=rgb(P["dark"][0]), outline=rgb(col))
            dr.text((cx - 3, y - 6), s[3:], font=fnt, fill=rgb(col))
        else: text(im, s, fnt, cx, y, rgb(col), rgb(P["dark"][0]))
    out = np.asarray(im)
    if f % 97 == 0:
        bad = {tuple(c) for c in out.reshape(-1, 3)} - {rgb(c) for c in PAL}
        assert not bad, f"colores fuera de paleta en {f}: {len(bad)}"
    return out

# ---------- música: todo calzado a la grilla de 10 cuadros por tiempo ----------
SR = 44100
def music(path):
    n = int(SR * N / FPS); t = np.arange(n) / SR
    beat = BEAT / FPS; bar = 4 * beat
    def T_(fr): return fr / FPS
    def mtof(m): return 440 * 2 ** ((m - 69) / 12)
    def lp(x, a):
        y, acc = np.empty_like(x), 0.0
        for i, v in enumerate(x.tolist()): acc += a * (v - acc); y[i] = acc
        return y
    def saw(fr, tt, det=(0,)): return sum(((tt * fr * (1 + d) + 0.31 * k) % 1) * 2 - 1 for k, d in enumerate(det)) / len(det)
    def add(buf, st, sig):
        i0 = int(st * SR); L = min(len(sig), n - i0)
        if L > 0 and i0 >= 0: buf[i0:i0 + L] += sig[:L]
    rng = np.random.default_rng(11)
    pads, bass, lead, drums, fx = (np.zeros(n) for _ in range(5))
    prog = [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]]     # Dm Bb F C
    STOP0, STOP1 = T_(1080), T_(1100)
    alive = ~((t >= STOP0) & (t < STOP1))                              # silencio cuando salta el disco
    nbars = 29
    for b in range(nbars):
        ch = prog[b % 4]; s0 = b * bar; L = int(bar * SR); tt = np.arange(L) / SR
        for m in ch + [ch[0] + 12]:
            add(pads, s0, saw(mtof(m), tt, (-0.011, -0.004, 0.005, 0.012)) * 0.08)
        if 4 <= b < 27 or b >= 27 and s0 >= STOP1 - 0.01 or b == 27:
            for k in range(8):
                st = s0 + (k + 0.5) * beat / 2; Lb = int(beat / 2 * 0.9 * SR); tb = np.arange(Lb) / SR
                add(bass, st, (saw(mtof(ch[0] - 12), tb, (-0.004, 0.004)) + 0.7 * np.sin(2 * np.pi * mtof(ch[0] - 24) * tb)) * np.exp(-tb * 4) * 0.3)
    pump = np.where((t >= T_(320)) & (t < T_(1080)), 1 - 0.72 * np.exp(-((t / beat) % 1) * 9), 1.0)
    open_ = np.clip((t - T_(240)) / T_(80), 0, 1)
    pads = lp(pads, 0.05) * pump * np.where(t < T_(320), 0.4 + 0.6 * open_, 1)
    bass = lp(bass, 0.12) * pump
    # intro: un pluck por tiempo, como lápiz que dibuja
    for k in range(16):
        tt = np.arange(int(0.3 * SR)) / SR; m = [74, 77, 81, 77][k % 4] + (0 if k < 8 else 2)
        add(lead, k * beat, np.sin(2 * np.pi * mtof(m) * tt) * np.exp(-tt * 12) * 0.12)
    # sección de piezas: melodía original en corcheas, y un "blip" que sube un grado por cada pieza
    phrase = [74, 77, 79, 81, 79, 77, 74, 72, 70, 72, 74, 77, 74, 72, 69, 72]
    for b in range(9, 27):
        for k in range(8):
            m = phrase[((b - 9) % 2) * 8 + k]
            st = b * bar + k * beat / 2; Ll = int(beat / 2 * 0.8 * SR); tl = np.arange(Ll) / SR
            sig = (np.sign(np.sin(2 * np.pi * mtof(m) * tl)) * 0.5 + saw(mtof(m), tl, (-0.003, 0.003)) * 0.5) * np.exp(-tl * 3) * 0.08
            add(lead, st, sig * (0.6 if b >= 21 else 1))
    scale = [62, 65, 67, 69, 72, 74]
    for p in range(6):
        tt = np.arange(int(0.5 * SR)) / SR; fr = mtof(scale[p] + 12)
        add(fx, T_(360 + p * 80), np.sin(2 * np.pi * fr * tt + 2 * np.exp(-tt * 10) * np.sin(2 * np.pi * fr * 2 * tt)) * np.exp(-tt * 5) * 0.16)
    for p in range(6):  # rearmado: arpegio ascendente, una nota por pieza que encaja
        tt = np.arange(int(0.3 * SR)) / SR
        add(fx, T_(840 + p * BEAT), np.sin(2 * np.pi * mtof(scale[p] + 12) * tt) * np.exp(-tt * 9) * 0.15)
        add(fx, T_(840 + p * BEAT), rng.standard_normal(len(tt)) * np.exp(-tt * 90) * 0.15)
    lead = lp(lead, 0.4)
    # batería
    for k in range(int(N / BEAT)):
        st = k * beat
        if st >= T_(160) and not (STOP0 <= st < STOP1):
            tt = np.arange(int(0.25 * SR)) / SR
            add(drums, st, np.sin(2 * np.pi * (45 + 150 * np.exp(-tt * 35)) * tt) * np.exp(-tt * 9) * (1 if st >= T_(320) else 0.6))
        if st >= T_(320) and k % 2 == 1 and not (STOP0 <= st < STOP1):
            tt = np.arange(int(0.16 * SR)) / SR; add(drums, st, np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt * 20) * 0.15)
        if st >= T_(160) and not (STOP0 <= st < STOP1):
            tt = np.arange(int(0.05 * SR)) / SR; add(drums, st + beat / 2, np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt * 60) * 0.07)
    for k in range(48):  # redoble que acelera hacia la explosión
        st = T_(240) + T_(80) * (1 - (1 - k / 48) ** 1.7)
        tt = np.arange(int(0.04 * SR)) / SR; add(drums, st, rng.standard_normal(len(tt)) * np.exp(-tt * 70) * 0.1 * (0.3 + 0.7 * k / 48))
    riser = np.diff(rng.standard_normal(n + 1)) * np.clip((t - T_(280)) / T_(40), 0, 1) ** 2 * (t < T_(320)) * 0.12
    for fr_, amp in ((320, 1.0), (1080, 1.2)):  # impactos: explosión y disparo del disco
        tt = np.arange(int(1.5 * SR)) / SR
        add(fx, T_(fr_), (np.sin(2 * np.pi * (40 + 100 * np.exp(-tt * 20)) * tt) * np.exp(-tt * 3) * 0.6 + rng.standard_normal(len(tt)) * np.exp(-tt * 6) * 0.25) * amp)
    for fr_ in [360 + 80 * 3 + k * 20 for k in range(4)] + [1000, 1040]:  # clics del microrruptor, en el tiempo
        tt = np.arange(int(0.05 * SR)) / SR; add(fx, T_(fr_), (rng.standard_normal(len(tt)) * 0.6 + np.sin(2 * np.pi * 2600 * tt)) * np.exp(-tt * 110) * 0.35)
    tt = np.arange(int(3 * SR)) / SR  # rearme: acorde final
    for m in [62, 65, 69, 74, 77]: add(fx, T_(1100), np.sin(2 * np.pi * mtof(m) * tt) * np.exp(-tt * 1.2) * 0.06)
    mix = (pads + bass + lead + drums) * alive + fx + riser
    out = np.tanh(mix * 1.4); out *= 0.89 / np.abs(out).max()
    out *= np.minimum(1, (n - np.arange(n)) / (0.6 * SR))
    st = np.stack([out + 0.12 * np.roll(lead, 400) * alive, out + 0.12 * np.roll(pads, 600) * alive], 1)
    st *= 0.89 / np.abs(st).max()
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())

if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).resize((W * 2, H * 2), Image.NEAREST).save(sys.argv[3]); sys.exit()
    from multiprocessing import Pool
    wav, mp4 = os.path.join(HERE, "despiece.wav"), os.path.join(HERE, "termostato_despiece.mp4")
    music(wav)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for fr in pool.imap(frame, range(N), chunksize=4): ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("listo:", mp4)
