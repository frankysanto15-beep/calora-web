"""Monta la locución sobre termos_pixel.mp4: cada frase del guion estira su tramo de vídeo hasta durar lo que dura en la voz,
y suma efectos de Kenney (CC0, en sfx/) sobre la palabra clave.
Uso: python3 locucion_render.py locucion.mp3 [salida.mp4]
"""
import sys, os, re, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.join(HERE, "termos_pixel.mp4")

# (frase leída, tramo del vídeo en s según sus subtítulos, efecto, palabra donde suena)
SCRIPT = [
    ("Pones un depósito de agua, una resistencia dentro y lo enchufas.", 0.0, 3.0, None, None),
    ("Ya tienes un termo.", 3.0, 4.0, "confirmation_001", "termo"),
    ("Pero no deja de calentar y el agua hierve.", 4.0, 5.75, "phaserUp3", "hierve"),
    ("Entonces pones una varilla que corta la corriente al llegar a sesenta grados.", 5.75, 9.0, "click_002", "corta"),
    # en la voz no hay pausa entre estas dos frases: van juntas
    ("Es el termostato. Por eso va a sesenta, para que no crezca la legionela, una bacteria.", 9.0, 13.25, "confirmation_002", "termostato"),
    ("Pero en cuanto corta, el agua se enfría y vuelve a gastar luz.", 13.25, 16.25, "lowDown", "enfría"),
    ("Entonces lo envuelves en una capa gorda de espuma.", 16.25, 18.25, "maximize_006", "envuelves"),
    ("Es el aislante.", 18.25, 19.0, "confirmation_002", "aislante"),
    ("Pero al ducharte entra agua fría, se mezcla con la caliente y sale tibia.", 19.0, 22.25, "error_004", "tibia"),
    ("Entonces metes un tubo que lleva el agua fría hasta el fondo.", 22.25, 25.0, "maximize_006", "tubo"),
    ("Es el tubo de entrada.", 25.0, 26.0, "confirmation_002", "tubo"),
    ("Por eso la caliente se queda arriba, y cuando se acaba, sale fría de golpe.", 26.0, 29.25, "impactPunch_heavy_000", "golpe"),
    ("Pero el agua caliente se come el acero y el depósito se oxida.", 29.25, 32.25, "glitch_001", "oxida"),
    ("Entonces cuelgas dentro una barra de magnesio que se oxida antes.", 32.25, 35.25, "impactMetal_light_001", "barra"),
    ("Es el ánodo de sacrificio.", 35.25, 36.5, "powerUp2", "ánodo"),
    ("Pero ochenta litros, al calentarse, crecen más de un litro, y el depósito revienta.", 36.5, 40.0, "impactMetal_heavy_002", "revienta"),
    ("Entonces pones una válvula que suelta agua cuando aprieta demasiado.", 40.0, 43.5, "drop_003", "suelta"),
    ("Es la válvula de seguridad.", 43.5, 44.75, "confirmation_002", "válvula"),
    ("Por eso gotea un poquito cada vez que el termo calienta.", 44.75, 47.0, "drop_001", "gotea"),
    ("Mándaselo a quien se ducha el último.", 47.0, 49.8, "jingles_NES03", "último"),
]

def speech_chunks(mp3):
    log = subprocess.run(["ffmpeg", "-i", mp3, "-af", "silencedetect=n=-35dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    dur = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", log).group(3)) + 60 * int(re.search(r"Duration: (\d+):(\d+)", log).group(2))
    starts, ends = [0.0] + en, st + [dur]
    return [(a, b) for a, b in zip(starts, ends) if b - a > 0.05], dur

def align(chunks, lens):
    """reparte los tramos hablados entre las frases (en orden) para que cada frase dure lo que pide su largo en letras."""
    rate = sum(b - a for a, b in chunks) / sum(lens)
    n, m = len(chunks), len(lens)
    INF = float("inf"); cost = np.full((m + 1, n + 1), INF); back = np.zeros((m + 1, n + 1), int); cost[0, 0] = 0
    for j in range(1, m + 1):
        for i in range(j, n + 1):
            for k in range(j - 1, i):  # frase j usa los tramos k..i-1
                d = sum(b - a for a, b in chunks[k:i])
                c = cost[j - 1, k] + (d - lens[j - 1] * rate) ** 2
                if c < cost[j, i]: cost[j, i], back[j, i] = c, k
    first, i = [], n
    for j in range(m, 0, -1): first.append(back[j, i]); i = back[j, i]
    return first[::-1]  # índice del primer tramo de cada frase

if __name__ == "__main__":
    mp3 = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "termos_pixel_locucion.mp4")
    chunks, total = speech_chunks(mp3)
    first = align(chunks, [len(s) for s, *_ in SCRIPT])
    assert len(first) == len(SCRIPT) and first == sorted(set(first)), first
    t0 = [0.0] + [chunks[k][0] for k in first[1:]]
    t1 = t0[1:] + [total + 0.6]
    fc, ins = [], ["-i", VIDEO, "-i", mp3]
    sfx_lbl = []
    for j, ((s, v0, v1, fx, word), a, b) in enumerate(zip(SCRIPT, t0, t1)):
        print(f"{a:6.2f}-{b:6.2f}  x{(b - a) / (v1 - v0):.2f}  {s}")
        fc.append(f"[0:v]trim={v0}:{v1},setpts=(PTS-STARTPTS)*{(b - a) / (v1 - v0):.5f}[v{j}]")
        if fx:  # la palabra clave cae en proporción a su posición en la frase
            at = a + (b - a) * s.lower().index(word.lower()) / len(s)
            ins += ["-i", os.path.join(HERE, "sfx", fx + ".ogg")]
            k = len(ins) // 2 - 1
            fc.append(f"[{k}:a]volume=0.45,adelay={int(at * 1000)}:all=1[s{j}]"); sfx_lbl.append(f"[s{j}]")
    fc.append("".join(f"[v{j}]" for j in range(len(SCRIPT))) + f"concat=n={len(SCRIPT)}:v=1:a=0,fps=24[v]")
    fc.append(f"[1:a]{''.join(sfx_lbl)}amix=inputs={1 + len(sfx_lbl)}:duration=first:normalize=0,apad=pad_dur=0.6[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    print("listo:", out)
