"""Explicador en pixel art: por qué un termo lleva cada pieza (45 s, 1080x1920).
Cada problema añade una pieza: resistencia, termostato, aislante, tubo de entrada, ánodo y válvula de seguridad.
Reutiliza escenario, mascota, termómetro, resistencia, composición, cierre con logo y música de termostato_render.py.
Uso: python3 termo_partes_render.py [--still N salida.png]
"""
import sys, os, math, subprocess
import numpy as np
from PIL import Image
import termostato_render as tr
from termostato_render import P, stage, host, coil, lamp, thermometer, leader, ease
from pixel_render import X, Y, B4, seg, rect, ell, paint, tone, lvl, dilate

N = tr.N = 1080                                                       # la música lee tr.N
CX, CY, CR = 90, 168, 44
RN = np.random.default_rng(3).random((110, 70)).repeat(3, 0).repeat(3, 1)[:320, :180]  # ruido en bloques de 3 px para el óxido

def tank(img, emis, f, heat, on=False, res=1.0, plug=1.0, therm=0.0, insul=0.0, dip=0.0, anode=0.0, corr=0.0,
         rust=0.0, bulge=0.0, valve=0.0, drip=False, losses=False, appear=1.0, boil=False, flow=False):
    t12 = f // 2
    R = max(CR * appear + 3 * bulge, 1)
    cx = CX + ((t12 % 2) * 2 - 1 if bulge > 0.5 else 0)               # tiembla cuando aprieta
    hh = 0.65 * R
    d = np.sqrt((X - cx) ** 2 + (Y - CY - np.clip(Y - CY, -hh, hh)) ** 2)
    top, bot = CY - hh - R + 4, CY + hh + R - 4
    G = P["green"]
    # tubos: entrada fría arriba a la izquierda (con válvula), salida caliente arriba al centro
    if appear >= 1:
        img[rect(10, 70, cx - 16, 75) | rect(cx - 21, 70, cx - 16, top + 6)] = P["water"][1]
        img[rect(cx - 3, 62, cx + 3, top + 2)] = P["hot"][1]
        if valve > 0:
            vy = 60 + 12 * valve                                       # baja hasta su sitio
            paint(img, rect(24, vy - 8, 36, vy + 6), P["red"][2], (G[1], G[0]))
            img[rect(28, vy - 12, 32, vy - 8)] = P["steel"][2]; img[rect(29, vy + 6, 31, vy + 12)] = P["steel"][1]
            if drip:
                dy = vy + 14 + (t12 * 5) % 70
                img[ell(30, dy, 1.2, 2) & (Y < 120)] = P["rain"][4]
    if insul > 0:
        paint(img, d <= R + 6 * insul, tone(P, "brass", np.where(B4 < 0.5, 3, 4)), (G[1], G[0]))
    shell, inner = d <= R, d <= R - 4
    paint(img, shell, tone(P, "body", lvl(0.55 + 0.35 * ((X - cx) < 0))), (G[2], G[0]), (X - cx) < 0, 2)
    if rust > 0:
        img[(d <= R) & (d > R - 6) & (RN < rust * 0.7)] = P["roof"][1]
    if isinstance(heat, tuple):                                       # ("capas", fracción caliente): frontera tramada
        boundary = top + (bot - top) * heat[1]
        h = np.clip((boundary - Y) / 14 + 0.5, 0, 1)
    else: h = np.full((320, 180), heat)
    img[inner] = np.where((B4 < h)[inner][:, None], P["hot"][3], P["water"][3])
    if rust > 0:
        img[inner & (d > R - 7) & (RN < rust * 0.7)] = P["roof"][2]
    if on or boil:  # burbujas que suben desde la resistencia
        for k in range(18 if boil else 9):
            bx = 66 + (k * 23) % 40; by = bot - ((t12 * (5 if boil else 3) + k * 17) % (bot - top))
            img[ell(bx, by, 2 if boil else 1, 2 if boil else 1) & inner] = P["frame"][4]
    if boil:  # vapor saliendo por arriba
        for k in range(5):
            sy = top - 6 - (t12 * 2 + k * 9) % 40; sx = cx - 20 + k * 10 + ((t12 + k) % 3)
            img[ell(sx, sy, 4, 3) & (B4 < 0.6)] = P["frame"][4]
    if dip > 0:  # tubo de entrada hasta el fondo
        tb = top + 6 + (bot - 14 - top) * dip
        img[rect(cx - 21, top, cx - 16, tb)] = P["steel"][1]; img[rect(cx - 20, top, cx - 17, tb)] = P["frame"][4]
        if flow and dip >= 1:
            for k in range(4):
                fy = top + 4 + (t12 * 4 + k * 30) % int(tb - top - 4)
                img[rect(cx - 20, fy, cx - 17, fy + 3)] = P["water"][1]
    if flow:  # agua caliente que sale por arriba
        for k in range(3):
            fy = top + 2 - (t12 * 3 + k * 8) % 24
            img[rect(cx - 1, fy, cx + 2, fy + 3)] = P["hot"][4]
    if anode > 0:  # barra de magnesio colgando de arriba; se gasta al corroerse
        ax0 = cx + 18; L = (bot - top - 70) * (1 - 0.45 * corr)
        a_top = top - 10 - 60 * (1 - anode)
        rod = rect(ax0, a_top, ax0 + 4 - (corr > 0.6), a_top + L)
        img[rod] = P["steel"][2]; img[rod & (X == ax0)] = P["steel"][4]
        img[rod & (RN < corr * 0.8)] = P["roof"][1]
    # brida, resistencia, vaina del termostato y caja eléctrica (entran desde abajo)
    oy = 70 * (1 - res)
    if res > 0:
        img[rect(68, bot + 2 + oy, 114, bot + 8 + oy)] = P["steel"][2]; img[rect(68, bot + 2 + oy, 114, bot + 3 + oy)] = P["steel"][4]
        coil(img, emis, 80, bot + oy, 80, bot - 46 + oy, on and res >= 1, n=8, amp=5)
    if therm > 0:
        ty = 60 * (1 - therm)
        img[rect(cx + 11, bot - 44 + ty, cx + 15, bot + ty)] = P["brass"][2]; img[rect(cx + 11, bot - 44 + ty, cx + 12, bot + ty)] = P["brass"][4]
    if res >= 1:
        paint(img, rect(84, bot + 8, 106, bot + 20), G[1], (G[2], G[0]))
        lamp(img, emis, 95, bot + 14, on)
        if plug > 0:  # cable al enchufe de la pared
            px, py = 106 + 58 * plug, bot + 14
            img[seg(106, bot + 14, px, py - 18 * plug, 0.8)] = G[0]
            paint(img, rect(160, bot - 10, 172, bot + 2), P["frame"][4], (G[1], G[0]))
            img[rect(164, bot - 6, 165, bot - 2) | rect(167, bot - 6, 168, bot - 2)] = G[0]
    if losses:  # el calor se escapa por las paredes
        for k in range(8):
            a = k * math.pi / 4 + 0.3; rr = R + 4 + (t12 * 2 + k * 5) % 16
            x0, y0 = cx + rr * math.cos(a), CY + 0.65 * R * np.sign(math.sin(a)) + rr * math.sin(a)
            img[seg(x0, y0, x0 + 2 * math.cos(a + 1.2), y0 + 2 * math.sin(a + 1.2), 0.6)] = P["hot"][1]
    if bulge > 0.8:  # grietas
        img[seg(cx + R - 2, CY - 10, cx + R - 8, CY - 4, 0.6) | seg(cx + R - 8, CY - 4, cx + R - 3, CY + 3, 0.6)] = P["red"][1]
    return top, bot

def cap(l, a, b, cut=80):  # pie de texto: primera frase hasta l=cut, luego la segunda
    return [(a if l < cut else b, 8)]

def scene_build(f):
    img, emis = stage(f)
    T = 15 + 85 * ease(70, 140, f)
    on = f >= 62
    tank(img, emis, f, (T - 15) / 85, on=on, res=ease(18, 40, f), plug=ease(44, 62, f), appear=ease(0, 16, f), boil=T > 90)
    thermometer(img, emis, 16, 120, 230, T, tmax=100)
    labels = [(f"{int(T)} °C", 16, 244)]
    if 20 <= f < 80: leader(img, 140, 214, 86, 214); labels += [("Depósito", 150, 112), ("Resistencia", 150, 204)]
    host(img, f, "sad" if T > 90 else "happy")
    return img, emis, cap(f, ["Un depósito, una", "resistencia y un", "enchufe: ya es un termo."], ["Pero nunca se apaga:", "el agua acaba", "hirviendo."]), labels

def scene_thermostat(f):
    l = f - 160; img, emis = stage(f)
    T = 15 + 45 * ease(28, 96, l); on = l < 96
    tank(img, emis, f, 0.9 * (T - 15) / 45, on=on, therm=ease(4, 26, l))
    thermometer(img, emis, 16, 120, 230, T, tmax=100)
    leader(img, 140, 196, 106, 206)
    labels = [(f"{int(T)} °C", 16, 244), ("Termostato", 150, 184), ("ENCENDIDA" if on else "APAGADA", 95, 262)]
    host(img, f)
    return img, emis, cap(l, ["Por eso lleva un", "termostato: corta la", "corriente a 60 °C."], ["A 60 °C no crece la", "legionela, una", "bacteria peligrosa."], 96), labels

def scene_insulation(f):
    l = f - 320; img, emis = stage(f)
    T = 60 - 5 * ease(0, 60, l) + 5 * ease(60, 76, l) if l < 80 else 60
    on = 60 <= l < 76
    ins = ease(80, 110, l)
    tank(img, emis, f, 0.9 * (T - 15) / 45, on=on, therm=1, insul=ins, losses=l < 80)
    thermometer(img, emis, 16, 120, 230, T, tmax=100)
    labels = [(f"{int(round(T))} °C", 16, 244), ("ENCENDIDA" if on else "APAGADA", 95, 262)]
    if ins > 0.5: leader(img, 146, 124, 128, 136); labels.append(("Aislante", 150, 112))
    host(img, f, "sad" if l < 80 else "happy")
    return img, emis, cap(l, ["Al cortar, el agua se", "enfría y el termo", "vuelve a gastar luz."], ["Por eso va envuelto", "en aislante: guarda", "el calor por horas."]), labels

def scene_diptube(f):
    l = f - 480; img, emis = stage(f)
    if l < 80:
        heat = 0.95 - 0.45 * ease(6, 60, l); dip = 0
    else:
        heat = ("capas", 0.55); dip = ease(84, 104, l)
    tank(img, emis, f, heat, therm=1, insul=1, dip=dip, flow=True)
    labels = []
    if 56 <= l < 80 and (f // 4) % 3: labels.append(("BIGTIBIA", 90, 150))
    if dip >= 1:
        labels += [("caliente", 150, 112), ("fría", 150, 210)]
        leader(img, 40, 196, 70, 196); labels.append(("Tubo de", 30, 172)); labels.append(("entrada", 30, 182))
    host(img, f, "sad" if l < 80 else "happy")
    return img, emis, cap(l, ["Al ducharse, entra", "agua fría, se mezcla", "y sale tibia."], ["Un tubo la lleva al", "fondo: caliente arriba", "y fría abajo."]), labels

def scene_anode(f):
    l = f - 640; img, emis = stage(f)
    move = ease(100, 150, l)
    tank(img, emis, f, ("capas", 0.55), therm=1, insul=1, dip=1, rust=ease(4, 50, l) * (1 - move), anode=ease(80, 96, l), corr=move)
    labels = []
    if l >= 96: leader(img, 146, 124, 112, 130); labels += [("Ánodo de", 150, 104), ("magnesio", 150, 114)]
    if 20 <= l < 80: labels.append(("óxido", 150, 150))
    host(img, f, "sad" if l < 80 else "happy")
    return img, emis, cap(l, ["Con los años, el agua", "oxida el depósito", "por dentro."], ["Una barra de magnesio", "se oxida antes, en su", "lugar: es el ánodo."]), labels

def scene_valve(f):
    l = f - 800; img, emis = stage(f)
    bulge = ease(4, 40, l) * (1 - ease(92, 104, l))
    tank(img, emis, f, 0.95, on=l < 92, therm=1, insul=1, dip=1, anode=1, corr=1, bulge=bulge, valve=ease(78, 92, l), drip=l >= 92)
    labels = []
    if l >= 92: leader(img, 40, 100, 30, 86); labels += [("Válvula de", 44, 104), ("seguridad", 44, 114)]
    if l < 80 and bulge > 0.5: labels.append(("¡aprieta!", 150, 150))
    host(img, f, "sad" if l < 92 else "happy")
    return img, emis, cap(l, ["Al calentarse, el agua", "se dilata y aprieta", "el depósito."], ["La válvula suelta un", "poco: por eso gotea", "cuando calienta."]), labels

def scene_outro(f):  # tr.compose dibuja el logo desde f=960 cuando la escena es tr.scene_outro
    img, emis = stage(f)
    tr.termo(img, P, 90, 190, 30, (-1, -2, 2), "happy", f // 2, wave=True)
    return img, emis, ([(["Compártalo con quien", "se ducha al último."], 252)] if f >= 1000 else []), []

tr.scene_outro = scene_outro
tr.SCENES = SCENES = [(0, scene_build), (160, scene_thermostat), (320, scene_insulation), (480, scene_diptube),
                      (640, scene_anode), (800, scene_valve), (960, scene_outro)]
frame = tr.frame

if __name__ == "__main__":
    if sys.argv[1:2] == ["--still"]:
        Image.fromarray(frame(int(sys.argv[2]))).resize((540, 960), Image.NEAREST).save(sys.argv[3]); sys.exit()
    from multiprocessing import Pool
    HERE = os.path.dirname(os.path.abspath(__file__))
    wav, mp4 = os.path.join(HERE, "termo_partes.wav"), os.path.join(HERE, "calora_termo_partes.mp4")
    tr.music(wav, clicks=(256, 892))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "180x320", "-r", "24", "-i", "-", "-i", wav,
                           "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for fr in pool.imap(frame, range(N), chunksize=4): ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("listo:", mp4)
