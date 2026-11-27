"""Pasa un vídeo real al pixel art de Calora: 180x320 nativo, paleta de rampas de pixel_render con tramado ordenado,
animación a 12 fps (como los sprites), escalado x6 a 1080x1920 sin suavizado. Conserva el audio original.
Uso: python3 pixelate.py entrada.mp4 salida.mp4 [--still SEG salida.png]
"""
import sys, subprocess
import numpy as np
from PIL import Image
from pixel_render import W, H, palette, flatpal, quantize, rgb

FPS = 12
PAL = flatpal(palette("#ffffff", 0, 1))  # las 17 rampas de Calora sin tinte de escena

def pixel(fr):
    img = fr.astype(float) / 255
    img = np.clip((img - 0.5) * 1.12 + 0.5, 0, 1)      # algo más de contraste: el pixel art vive de valores marcados
    g = img.mean(-1, keepdims=True); img = np.clip(g + (img - g) * 1.25, 0, 1)  # y de color saturado
    return quantize(img, PAL, amp=0.08)

def frames(src, t=None):
    cmd = ["ffmpeg", "-loglevel", "error"] + (["-ss", str(t)] if t is not None else []) + ["-i", src,
           "-vf", f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=area,crop={W}:{H}",
           "-f", "rawvideo", "-pix_fmt", "rgb24"] + (["-frames:v", "1"] if t is not None else []) + ["-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while (b := p.stdout.read(W * H * 3)) and len(b) == W * H * 3:
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.wait()

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    pal = {rgb(c) for c in PAL}
    if sys.argv[3:4] == ["--still"]:
        out = (pixel(next(frames(src, float(sys.argv[4])))) * 255 + 0.5).astype(np.uint8)
        assert {tuple(c) for c in out.reshape(-1, 3)} <= pal  # autocomprobación: solo colores de la paleta
        Image.fromarray(out).resize((W * 3, H * 3), Image.NEAREST).save(sys.argv[5]); sys.exit()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", src, "-map", "0:v", "-map", "1:a?", "-vf", "scale=1080:1920:flags=neighbor", "-r", "24",
                           "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    for i, fr in enumerate(frames(src)):
        out = (pixel(fr) * 255 + 0.5).astype(np.uint8)
        if i % 120 == 0: assert {tuple(c) for c in out.reshape(-1, 3)} <= pal, f"fuera de paleta en {i}"
        ff.stdin.write(out.tobytes())
    ff.stdin.close(); ff.wait()
    print("listo:", dst)
