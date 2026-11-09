// Genera música y efectos como WAV 16-bit en public/sfx (sin descargas, siempre igual).
import { writeFileSync, mkdirSync } from "node:fs";

const SR = 44100;
const out = new URL("../public/sfx/", import.meta.url);
mkdirSync(out, { recursive: true });

function wav(name, samples) {
  const buf = Buffer.alloc(44 + samples.length * 2);
  buf.write("RIFF", 0); buf.writeUInt32LE(36 + samples.length * 2, 4); buf.write("WAVE", 8);
  buf.write("fmt ", 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write("data", 36); buf.writeUInt32LE(samples.length * 2, 40);
  let peak = 1e-9; for (const v of samples) peak = Math.max(peak, Math.abs(v));
  samples.forEach((v, i) => buf.writeInt16LE(Math.round((v / peak) * 0.89 * 32767), 44 + i * 2));
  writeFileSync(new URL(name, out), buf);
}
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;

// --- música: 100 BPM, C–G–Am–F, pad + arpegio + bombo suave ---
{
  const BPM = 100, beat = 60 / BPM, dur = 27.5, n = Math.floor(dur * SR), m = new Float64Array(n);
  const chords = [[48, 55, 60, 64], [43, 50, 59, 62], [45, 52, 57, 60], [41, 48, 57, 60]];
  const bar = beat * 4;
  for (let i = 0; i < n; i++) {
    const t = i / SR, c = chords[Math.floor(t / bar) % 4], tb = t % bar;
    const env = Math.min(1, tb / 0.4) * (0.75 + 0.25 * Math.cos((tb / bar) * Math.PI));
    let v = 0;
    for (const k of c) v += (Math.sin(2 * Math.PI * hz(k) * t) + Math.sin(2 * Math.PI * hz(k) * 1.004 * t)) * 0.06 * env;
    // arpegio en corcheas, una octava arriba
    const step = Math.floor(t / (beat / 2)), ts = t % (beat / 2), note = c[[0, 2, 3, 2, 1, 3, 2, 3][step % 8]] + 12;
    v += Math.sin(2 * Math.PI * hz(note) * t) * Math.exp(-ts * 9) * 0.16;
    // bombo suave en cada tiempo
    const tk = t % beat;
    v += Math.sin(2 * Math.PI * (55 + 90 * Math.exp(-tk * 30)) * tk) * Math.exp(-tk * 11) * 0.38;
    const fade = Math.min(1, t / 0.6, (dur - t) / 1.6);
    m[i] = v * Math.max(0, fade);
  }
  wav("music.wav", Array.from(m));
}
// --- whoosh: ruido filtrado con barrido ---
{
  const n = Math.floor(0.45 * SR), w = []; let lp = 0;
  for (let i = 0; i < n; i++) { const t = i / n, a = 0.02 + 0.25 * Math.sin(Math.PI * t); lp += a * (rnd() - lp); w.push(lp * Math.sin(Math.PI * t) ** 2); }
  wav("whoosh.wav", w);
}
// --- pop: seno con caída de tono ---
{
  const n = Math.floor(0.18 * SR), p = [];
  for (let i = 0; i < n; i++) { const t = i / SR; p.push(Math.sin(2 * Math.PI * (300 + 700 * Math.exp(-t * 40)) * t) * Math.exp(-t * 28)); }
  wav("pop.wav", p);
}
// --- ding: dos parciales tipo campanita ---
{
  const n = Math.floor(1.2 * SR), d = [];
  for (let i = 0; i < n; i++) { const t = i / SR; d.push((Math.sin(2 * Math.PI * 1318.5 * t) + 0.5 * Math.sin(2 * Math.PI * 1975.5 * t) + 0.3 * Math.sin(2 * Math.PI * 2637 * t)) * Math.exp(-t * 4.5)); }
  wav("ding.wav", d);
}
console.log("sfx listos");
