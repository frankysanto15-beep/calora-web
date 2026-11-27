"""Explicador en pixel art: cómo funciona el termostato de un termo eléctrico (42 s, 1080x1920).
Reutiliza rampas, sel-out, termo, bloom, cuantizado y texto de pixel_render.py.
Uso: python3 termostato_render.py [--still N salida.png]
"""
import sys, os, math, wave, subprocess
import numpy as np
from PIL import Image, ImageFont
import pixel_render as pr
from pixel_render import X, Y, W, H, B4, B8, seg, rect, ell, paint, termo, bloom, quantize, text, rgb, hexc, lvl, tone

FPS, N = 24, 1008
HERE = os.path.dirname(os.path.abspath(__file__))
pr.BASES.update(water="#4f86c6", hot="#e2683a", steel="#9aa5ab", brass="#cfa64f", red="#d6453b", ok="#45a85e")
P = pr.palette("#ffffff", 0.0, 1.0)
PAL = pr.flatpal(P)
G0, CREAM = rgb(P["green"][0]), rgb(P["frame"][4])
F9, F11, F30 = ImageFont.truetype(pr.SANS, 9), ImageFont.truetype(pr.SANS, 11), ImageFont.truetype(pr.SERIF, 30)

def ease(a, b, f):
    t = min(max((f - a) / (b - a), 0), 1); return t * t * (3 - 2 * t)

BPM = 140
def stage(f):
    img = np.broadcast_to(P["frame"][3], (H, W, 3)).copy()
    kick = (f / FPS * BPM / 60) % 1 < 0.22                               # los puntos laten con el bombo
    img[(X % 10 == 5) & (Y % 10 == 5)] = P["orange"][3] if kick else P["frame"][2]
    return img, np.zeros((H, W, 3))

def host(img, f, mood="happy", wave=False):  # mascota que acompaña en la esquina
    t12 = f // 2
    termo(img, P, 154, 282 + (-1 if wave and t12 % 4 < 2 else 0), 10, (-1, -2, 2), mood, t12, wave=wave)

def thermometer(img, emis, x, y0, y1, T, tmax=90):
    tube = rect(x - 2, y0, x + 3, y1)
    paint(img, tube, P["frame"][4], (P["green"][1], P["green"][0]))
    lvl_y = y1 - (y1 - y0) * min(T, tmax) / tmax
    hotc = P["red"][2] if T > 70 else P["hot"][2] if T > 40 else P["water"][2]
    img[rect(x - 1, lvl_y, x + 2, y1 + 2)] = hotc
    paint(img, ell(x + 0.5, y1 + 5, 5, 5), hotc, (P["green"][1], P["green"][0]))
    img[ell(x - 1, y1 + 3, 1, 1)] = P["frame"][4]

def lamp(img, emis, x, y, on):
    m = ell(x, y, 4, 4)
    paint(img, m, P["ok"][4] if on else P["red"][1], (P["green"][1], P["green"][0]))
    if on: emis[m] = hexc("#9dffb0") * 1.2

def coil(img, emis, x0, y0, x1, y1, on, n=6, amp=4):
    pts = [(x0 + (x1 - x0) * k / n + (amp if k % 2 else -amp) * (k not in (0, n)) * (y1 != y0), y0 + (y1 - y0) * k / n + (amp if k % 2 else -amp) * (k not in (0, n)) * (y1 == y0)) for k in range(n + 1)]
    m = np.zeros((H, W), bool)
    for (a, b), (c, d) in zip(pts, pts[1:]): m |= seg(a, b, c, d, 1.0)
    img[pr.dilate(m, 1) & ~m] = P["green"][0]
    img[m] = P["light"][4] if on else P["steel"][2]
    if on: emis[m] = hexc("#ffb060") * 1.3

def leader(img, x0, y0, x1, y1):
    m = seg(x0, y0, x1, y1, 0.5) & ((X + Y) % 2 == 0)
    img[m] = P["green"][1]

# ---------- escenas: cada una devuelve (imagen 0..1, lista de textos) ----------
def scene_intro(f):
    img, emis = stage(f)
    termo(img, P, 90, 150, 34, (-1, -2, 2), "happy", f // 2, wave=f > 40)
    for k in range(3):  # signos de pregunta flotando, a 12 fps
        yy = 70 + ((f // 2) * 1 + k * 9) % 26
        img[rect(128 + k * 12, yy, 130 + k * 12, yy + 2)] = P["orange"][2]
    return img, emis, [(["¿Cómo sabe tu termo", "cuándo calentar?"], 22)], []

CUT_CX, CUT_CY, CUT_R = 90, 170, 52
def tank(img, emis, f, hot_frac, on):
    t12 = f // 2
    hh = 0.65 * CUT_R
    dyc = np.clip(Y - CUT_CY, -hh, hh)
    shell = (X - CUT_CX) ** 2 + (Y - CUT_CY - dyc) ** 2 <= CUT_R ** 2
    inner = (X - CUT_CX) ** 2 + (Y - CUT_CY - dyc) ** 2 <= (CUT_R - 5) ** 2
    paint(img, shell, tone(P, "body", lvl(0.55 + 0.35 * ((X - CUT_CX) < 0))), (P["green"][2], P["green"][0]), (X - CUT_CX) < 0, 2)
    top, bot = CUT_CY - hh - CUT_R + 5, CUT_CY + hh + CUT_R - 5
    boundary = top + (bot - top) * hot_frac
    is_hot = B4 < np.clip((boundary - Y) / 14 + 0.5, 0, 1)             # capas: el agua caliente sube (frontera tramada)
    img[inner] = np.where(is_hot[inner][:, None], P["hot"][3], P["water"][3])
    if on:  # convección: burbujas que suben de la resistencia
        for k in range(10):
            bx = 66 + (k * 23) % 30; by = 240 - ((t12 * 3 + k * 17) % 130)
            img[ell(bx, by, 1, 1) & inner] = P["frame"][4]
    # tubos de entrada fría (abajo) y salida caliente (arriba)
    img[rect(18, 236, 40, 241)] = P["water"][1]; img[rect(32, 241, 37, 250)] = P["water"][1]
    img[rect(87, 62, 93, 86)] = P["hot"][1]
    # ánodo, brida, resistencia y vaina del termostato
    img[rect(68, 92, 72, 176)] = P["steel"][1]; img[rect(68, 92, 69, 176)] = P["steel"][3]
    img[rect(68, 250, 114, 258)] = P["steel"][2]; img[rect(68, 250, 114, 251)] = P["steel"][4]
    coil(img, emis, 80, 248, 80, 196, on, n=8, amp=5)
    img[rect(101, 192, 105, 250)] = P["brass"][2]; img[rect(101, 192, 102, 250)] = P["brass"][4]
    paint(img, rect(96, 258, 112, 268), P["green"][1], (P["green"][2], P["green"][0]))
    lamp(img, emis, 104, 263, on)

def scene_cutaway(f):
    img, emis = stage(f)
    lf = f - 96
    hot_frac = 0.15 + 0.5 * ease(0, 190, lf)
    tank(img, emis, f, hot_frac, on=True)
    labels = []
    L = [("Salida caliente", 128, 50, 92, 66), ("Ánodo", 30, 112, 68, 128), ("Resistencia", 34, 196, 76, 214),
         ("Termostato", 146, 186, 106, 206), ("Entrada fría", 40, 262, 30, 246)]
    for k, (s, tx, ty, ax, ay) in enumerate(L):
        if lf >= 24 + k * 24:
            leader(img, tx, ty + 10, ax, ay); labels.append((s, tx, ty))
    host(img, f)
    return img, emis, [(["Por dentro: agua,", "una resistencia y", "un termostato."], 8)], labels

def therm_T(f):  # temperatura en el acercamiento al termostato
    return 20 + 41 * ease(300, 460, f)

def scene_rod(f):
    img, emis = stage(f)
    T = therm_T(f); closed = T < 60
    ext = round(10 * (T - 20) / 40)                                    # dilatación exagerada x mucho
    hotness = np.clip((T - 20) / 40, 0, 1)
    bg = rect(60, 132, 122, 290)
    img[bg] = np.where((B4[bg] < hotness)[:, None], P["hot"][4], P["water"][4])
    tube_end = 250 + ext
    paint(img, rect(82, 132, 98, tube_end), tone(P, "brass", lvl(np.where(X < 88, 0.85, 0.45))), (P["brass"][1], P["green"][0]))
    img[rect(87, 128, 93, tube_end - 3)] = P["steel"][3]; img[rect(87, 128, 88, tube_end - 3)] = P["steel"][4]
    img[rect(82, tube_end - 3, 98, tube_end)] = P["steel"][1]           # soldadura: tubo y varilla unidos abajo
    # cabezal con contactos de acción rápida
    head = rect(40, 84, 140, 130)
    paint(img, head, P["steel"][1], (P["green"][2], P["green"][0]), None, 2)
    img[rect(46, 90, 134, 124)] = P["green"][1]
    img[rect(76, 96, 104, 100)] = P["brass"][3]                         # contacto fijo
    blade_y = 101 if closed else 109
    img[seg(110, 112, 78, blade_y, 1.0)] = P["frame"][4]                # lámina móvil
    img[rect(80, blade_y - 1, 100, blade_y + 2)] = P["brass"][3]
    img[rect(89, blade_y + 2, 91, 128)] = P["steel"][3]                 # varilla tira de la lámina
    if not closed and therm_T(f - 2) < 60:
        for a in range(6): img[seg(90, 104, 90 + 9 * math.cos(a), 104 + 9 * math.sin(a), 0.5)] = P["light"][4]
    # cable a la resistencia y su estado
    img[rect(104, 97, 152, 99) | rect(150, 97, 152, 150)] = P["green"][0]
    coil(img, emis, 151, 150, 151, 186, closed, n=6, amp=4)
    lamp(img, emis, 151, 198, closed)
    if T > 22 and closed:  # ondas de calor alrededor del tubo
        for k in range(4):
            yy = 240 - ((f // 2) * 4 + k * 30) % 110
            for s in (-1, 1): img[seg(90 + s * 14, yy, 90 + s * 16, yy - 6, 0.5)] = P["hot"][1]
    thermometer(img, emis, 22, 140, 262, T)
    labels = [(f"{int(T)} °C", 22, 276), ("ENCENDIDA" if closed else "APAGADA", 151, 206)]
    if f >= 312:
        leader(img, 124, 232, 98, 232); labels += [("Tubo de", 150, 222), ("cobre", 150, 232)]
        leader(img, 124, 262, 91, 240); labels += [("Varilla de", 150, 252), ("invar", 150, 262)]
    labels.append(("(movimiento exagerado)", 90, 296))
    if not closed: img[seg(90, 252, 90, tube_end + 6, 0.5) & (Y > 252)] = P["red"][2]
    caps = [(["El termostato tiene un", "tubo y una varilla de", "metales distintos."], 10)] if f < 360 else \
           [(["Con el calor, el tubo", "se alarga más y tira", "de la varilla."], 10)] if f < 444 else \
           [(["Al llegar a 60 °C se", "abre el contacto: la", "resistencia se apaga."], 10)]
    return img, emis, caps, labels

def curve(t):  # temperatura y estado de la resistencia en el gráfico (t en 0..1)
    if t < 0.3: return 15 + 45 * t / 0.3, True
    if t < 0.52: return 60 - 5 * (t - 0.3) / 0.22, False
    if t < 0.6: return 55 + 5 * (t - 0.52) / 0.08, True
    if t < 0.72: return 60 - 2.5 * (t - 0.6) / 0.12, False
    if t < 0.76: return 57.5 - 3 * (t - 0.72) / 0.04, False
    if t < 0.8: return 54.5 - 9 * (t - 0.76) / 0.04, True           # ducha: llega agua fría
    if t < 0.97: return 45.5 + 14.5 * (t - 0.8) / 0.17, True
    return 60 - 0.5 * (t - 0.97) / 0.03, False

def scene_graph(f):
    img, emis = stage(f)
    x0, x1, yb = 24, 168, 240
    def py(T): return yb - (T - 10) * 130 / 60
    img[rect(x0, 100, x0 + 1, yb + 1) | rect(x0, yb, x1, yb + 1)] = P["green"][0]
    for T, c in ((60, "red"), (55, "ok")):
        img[rect(x0 + 2, py(T), x1, py(T) + 1) & (X % 4 < 2)] = P[c][2]
    reveal = ease(540, 700, f)
    xs = np.arange(x0 + 1, x1)
    pts = [(x, *curve((x - x0) / (x1 - x0))) for x in xs if (x - x0) / (x1 - x0) <= reveal]
    for (xa, ta, oa), (xb, tb, ob) in zip(pts, pts[1:]):
        img[seg(xa, py(ta), xb, py(tb), 1.0)] = P["hot"][1] if oa else P["water"][1]
    for x, t_, on in pts:
        img[rect(x, yb + 8, x + 1, yb + 14)] = P["hot"][3] if on else P["steel"][3]
    img[rect(30, yb + 32, 44, yb + 33) & (X % 4 < 2)] = P["red"][2]; img[rect(30, yb + 44, 44, yb + 45) & (X % 4 < 2)] = P["ok"][2]
    labels = [("60 °C: se apaga", 80, yb + 27), ("55 °C: se enciende", 86, yb + 39), ("°C", x0, 88),
              ("tiempo", x1 - 16, yb + 16), ("resistencia", 52, yb + 16)]
    if pts:
        x, t_, on = pts[-1]
        paint(img, ell(x, py(t_), 2.5, 2.5), P["frame"][4], (P["green"][1], P["green"][0]))
        labels.append((f"{int(round(t_))} °C", min(max(x, 30), 150), int(py(t_)) - 16))
        if reveal > 0.76: labels.append(("ducha", int(x0 + 0.78 * (x1 - x0)), int(py(46)) + 6))
    host(img, f)
    caps = [(["Al bajar unos grados", "(por enfriarse o por", "usar agua) se vuelve", "a encender."], 8)] if f < 624 else \
           [(["Ese margen evita que", "se prenda y apague", "a cada rato."], 10)]
    return img, emis, caps, labels

def scene_safety(f):
    img, emis = stage(f)
    T = 60 + 26 * ease(730, 800, f); tripped = T >= 85
    x = 90
    img[rect(x, 84, x + 2, 270)] = P["green"][0]
    img[rect(x - 20, 82, x + 22, 86)] = P["green"][0]
    # termostato principal: contacto pegado
    paint(img, rect(x - 14, 110, x + 16, 140), P["steel"][2], (P["green"][2], P["green"][0]))
    img[rect(x - 6, 122, x + 8, 128)] = P["brass"][3]
    if (f // 4) % 2: img[seg(x - 8, 118, x + 10, 132, 0.7) | seg(x + 10, 118, x - 8, 132, 0.7)] = P["red"][2]
    # termostato de seguridad con botón de rearme
    paint(img, rect(x - 14, 170, x + 16, 200), P["steel"][2], (P["green"][2], P["green"][0]))
    gap = 0 if not tripped else 6
    img[rect(x - 6, 182, x + 8, 185)] = P["brass"][3]; img[rect(x - 6, 186 + gap, x + 8, 189 + gap)] = P["brass"][3]
    img[rect(x, 184, x + 2, 187 + gap)] = P["frame"][3] if tripped else P["green"][0]
    by = 164 - (5 if tripped else 0)
    paint(img, rect(x + 18, by, x + 28, by + 8), P["red"][2], (P["red"][0], P["green"][0]))
    coil(img, emis, x + 1, 218, x + 1, 252, not tripped, n=6, amp=4)
    lamp(img, emis, x + 1, 262, not tripped)
    if tripped and T < 86 or (tripped and f < 808):
        for a in range(6): img[seg(x + 1, 186, x + 1 + 10 * math.cos(a), 186 + 10 * math.sin(a), 0.5)] = P["light"][4]
    thermometer(img, emis, 22, 140, 262, T, tmax=100)
    host(img, f, "happy" if tripped else "sad")
    labels = [(f"{int(T)} °C", 22, 276), ("Termostato", 146, 112), ("¡pegado!", 146, 124), ("Seguridad", 146, 174),
              ("rearme", 146, 186), ("ENCENDIDA" if not tripped else "APAGADA", x + 1, 272)]
    caps = [(["Si se pega el contacto,", "un termostato de", "seguridad corta cerca", "de 80-90 °C."], 6)] if f < 800 else \
           [(["Queda bloqueado hasta", "rearmarlo a mano.", "Eso lo revisa", "un técnico."], 6)]
    return img, emis, caps, labels

def scene_outro(f):
    img, emis = stage(f)
    t12 = f // 2
    if f < 960:
        termo(img, P, 90, 190, 30, (-1, -2, 2), "happy", t12, wave=True)
        caps = [(["60 °C es buen punto:", "frena la legionela", "sin gastar de más."], 8)] if f < 930 else \
               [(["El sarro cubre la", "resistencia y la vaina:", "todo trabaja de más."], 8)]
        if f >= 930:
            for k in range(14):
                sx = 62 + (k * 13) % 56; sy = 248 + (k * 7) % 6
                img[rect(sx, sy, sx + 3, sy + 2)] = P["frame"][1]
        return img, emis, caps, [("BIG60 °C", 90, 106)]
    termo(img, P, 90, 190, 30, (-1, -2, 2), "happy", t12, wave=True, glint=-1.2 + (f - 960) / 16 if f < 1000 else None)
    return img, emis, [], []

SCENES = [(0, scene_intro), (96, scene_cutaway), (288, scene_rod), (528, scene_graph), (720, scene_safety), (864, scene_outro)]

def compose(fn, f):
    img, emis, caps, labels = fn(f)
    img = quantize(bloom(img, emis, 5, 0.6), PAL)
    im = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    for lines, y in caps:
        for k, s in enumerate(lines): text(im, s, F11, W / 2, y + k * 13, G0, CREAM, shadow=False)
    for s, cx, y in labels:
        big = s.startswith("BIG")
        text(im, s[3:] if big else s, F30 if big else F9, cx, y, rgb(P["orange"][1]) if big else G0, CREAM, shadow=False)
    if fn is scene_outro and f >= 960:
        k = min((f - 960) // 2, 5); y = [-30, 20, 40, 52, 48, 50][k]
        text(im, "calora", F30, W / 2, y, CREAM, G0)
        if f >= 976: text(im, "Mantención de termos", F11, W / 2, 92, G0, CREAM, shadow=False)
    return np.asarray(im)

def frame(f):
    i = max(k for k, (s, _) in enumerate(SCENES) if f >= s)
    s0, fn = SCENES[i]
    out = compose(fn, f)
    if i and f < s0 + 8:  # disolución tramada desde el último cuadro de la escena anterior
        prev = compose(SCENES[i - 1][1], s0 - 1)
        out = np.where((B8 < ((f - s0) // 2 + 1) / 4)[..., None], out, prev)
    if f in (0, 200, 470, 650, 820, 990):
        pal = {rgb(c) for c in PAL}
        assert not {tuple(c) for c in out.reshape(-1, 3)} - pal, f"colores fuera de paleta en {f}"
    return out

# ---------- sonido: electro de 140 bpm estilo juego de ritmo (composición original) ----------
SR = 44100
def music(path):
    n = int(SR * N / FPS); t = np.arange(n) / SR
    beat = 60 / BPM; bar = 4 * beat
    def mtof(m): return 440 * 2 ** ((m - 69) / 12)
    def lp(x, a):
        y, acc = np.empty_like(x), 0.0
        for i, v in enumerate(x.tolist()): acc += a * (v - acc); y[i] = acc
        return y
    def saw(fr, tt, det=(0,)): return sum(((tt * fr * (1 + d) + 0.37 * k) % 1) * 2 - 1 for k, d in enumerate(det)) / len(det)
    rng = np.random.default_rng(9)
    DROP = 8 * bar                                                     # intro 4 compases, subida 4, luego el drop
    prog = [[53, 56, 60], [49, 53, 56], [56, 60, 63], [51, 55, 58]]     # Fm Db Ab Eb
    phase = (t / beat) % 1
    pump = np.where(t >= DROP, 1 - 0.75 * np.exp(-phase * 9), 1.0)    # "sidechain": todo se agacha con el bombo
    chords, bass, lead, drums = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    nbars = int(t[-1] / bar) + 1
    for b in range(nbars):
        ch = prog[b % 4]; s0 = b * bar; i0 = int(s0 * SR); L = min(int(bar * SR), n - i0)
        if L <= 0: break
        tt = np.arange(L) / SR
        amp = 0.5 if s0 < DROP else 1.0
        for m in ch + [ch[0] + 12]:
            chords[i0:i0 + L] += saw(mtof(m), tt, (-0.012, -0.005, 0, 0.006, 0.013)) * amp * 0.09
        for k in range(8):  # bajo en contratiempo
            st = s0 + (k + 0.5) * beat / 2; j0 = int(st * SR); Lb = min(int(beat / 2 * 0.9 * SR), n - j0)
            if s0 >= 4 * bar and Lb > 0:
                tb = np.arange(Lb) / SR
                bass[j0:j0 + Lb] += (saw(mtof(ch[0] - 12), tb, (-0.004, 0.004)) + 0.6 * np.sin(2 * np.pi * mtof(ch[0] - 24) * tb)) * np.exp(-tb * 4) * 0.33
    chords = lp(chords, 0.07 + 0.0 * t[0]) * pump
    sweep = np.clip((t - 4 * bar) / (4 * bar), 0, 1)                      # el filtro se abre durante la subida
    chords = chords * np.where(t < DROP, 0.35 + 0.65 * sweep, 1)
    bass = lp(bass, 0.12) * pump
    # melodía (original): frase de 2 compases en corcheas, variación en la repetición
    phrase = [72, 75, 77, 79, 77, 75, 72, 70, 68, 70, 72, 75, 72, 70, 68, 65]
    for b in range(nbars):
        s0 = b * bar
        if s0 < DROP - 0.01: 
            for k in range(16):  # arpegio de intro
                st = s0 + k * beat / 4; j0 = int(st * SR); Ll = min(int(0.12 * SR), n - j0)
                if Ll > 0:
                    tl = np.arange(Ll) / SR; m = prog[b % 4][k % 3] + 24
                    lead[j0:j0 + Ll] += np.sign(np.sin(2 * np.pi * mtof(m) * tl)) * np.exp(-tl * 25) * 0.05
            continue
        for k in range(8):
            idx = ((b - 8) % 2) * 8 + k
            m = phrase[idx] + (12 if (b - 8) % 4 == 3 and k > 4 else 0)
            st = s0 + k * beat / 2; j0 = int(st * SR); Ll = min(int(beat / 2 * 0.85 * SR), n - j0)
            if Ll <= 0: continue
            tl = np.arange(Ll) / SR; fr = mtof(m) * (1 + 0.004 * np.sin(2 * np.pi * 6 * tl))
            sq = np.sign(np.sin(2 * np.pi * fr * tl)) * 0.6 + saw(fr, tl, (-0.003, 0.003)) * 0.4
            lead[j0:j0 + Ll] += sq * np.minimum(tl / 0.005, 1) * np.exp(-tl * 2.5) * 0.13
    lead = lp(lead, 0.35)
    # batería
    nb = int(t[-1] / beat) + 1
    for k in range(nb):
        st = k * beat; j0 = int(st * SR)
        if j0 >= n: break
        if st >= 2 * bar or k % 4 == 0:  # bombo
            L = min(int(0.25 * SR), n - j0); tk = np.arange(L) / SR
            drums[j0:j0 + L] += np.sin(2 * np.pi * (45 + 140 * np.exp(-tk * 35)) * tk) * np.exp(-tk * 9) * (0.9 if st >= DROP or st < 4 * bar else 0.7)
        if st >= DROP and k % 2 == 1:  # palmas
            L = min(int(0.18 * SR), n - j0); tk = np.arange(L) / SR
            drums[j0:j0 + L] += np.diff(rng.standard_normal(L + 1)) * np.exp(-tk * 18) * 0.16
        if st >= 2 * bar:  # charles en contratiempo
            h0 = int((st + beat / 2) * SR); L = min(int(0.07 * SR), n - h0)
            if L > 0: drums[h0:h0 + L] += np.diff(rng.standard_normal(L + 1)) * np.exp(-np.arange(L) / SR * 45) * 0.08
    for k in range(64):  # redoble que acelera antes del drop
        st = 4 * bar + (4 * bar) * (1 - (1 - k / 64) ** 1.6)
        j0 = int(st * SR); L = min(int(0.05 * SR), n - j0)
        if L > 0: drums[j0:j0 + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 60) * 0.12 * (0.3 + 0.7 * k / 64)
    rise = (t >= 6 * bar) & (t < DROP)
    riser = np.diff(rng.standard_normal(n + 1)) * np.clip((t - 6 * bar) / (2 * bar), 0, 1) ** 2 * 0.1 * rise
    for fsn in (460, 800):  # chasquido del contacto
        i0 = int(fsn / FPS * SR); L = int(0.06 * SR); tt = np.arange(L) / SR
        drums[i0:i0 + L] += rng.standard_normal(L) * np.exp(-tt * 120) * 0.5 + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 80) * 0.25
    for k, m in enumerate([84, 87, 91, 96]):  # campanilla del logo
        i0 = int((960 / FPS + k * 0.07) * SR); L = min(int(1.4 * SR), n - i0); tt = np.arange(L) / SR
        drums[i0:i0 + L] += np.sin(2 * np.pi * mtof(m) * tt) * np.exp(-tt * 3) * 0.12
    mix = chords + bass + lead + drums + riser
    out = np.tanh(mix * 1.5); out *= 0.89 / np.abs(out).max()
    out *= np.minimum(1, (n - np.arange(n)) / (0.5 * SR))
    L_, R_ = out + 0.15 * np.roll(lead, 300), out + 0.15 * np.roll(chords, 500)
    st = np.stack([L_, R_], 1); st *= 0.89 / np.abs(st).max()
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())

if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).resize((W * 3, H * 3), Image.NEAREST).save(sys.argv[3]); sys.exit()
    from multiprocessing import Pool
    wav, mp4 = os.path.join(HERE, "termostato.wav"), os.path.join(HERE, "calora_termostato.mp4")
    music(wav)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for fr in pool.imap(frame, range(N), chunksize=4): ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("listo:", mp4)
