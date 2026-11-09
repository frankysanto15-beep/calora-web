import React from "react";
import { AbsoluteFill, Audio, Sequence, Series, staticFile } from "remotion";
import { BgMesh, Grade, Grain, Vignette } from "./components";
import { Gancho, Sarro } from "./scenes/Problema";
import { Agendar, CHAT, Pasos, SELLO_AT } from "./scenes/Agendar";
import { Cta, Marcas, Resultado } from "./scenes/Cierre";

const FPS = 30;
const s = (sec: number) => Math.round(sec * FPS);
const ESCENAS = [
  { C: Gancho, dur: s(2.6) },
  { C: Sarro, dur: s(2.8) },
  { C: Agendar, dur: s(8) },
  { C: Pasos, dur: s(2.6) },
  { C: Marcas, dur: s(3.4) },
  { C: Resultado, dur: s(3.2) },
  { C: Cta, dur: s(4) },
];
export const PROMO_FRAMES = ESCENAS.reduce((a, e) => a + e.dur, 0);
const inicio = (i: number) => ESCENAS.slice(0, i).reduce((a, e) => a + e.dur, 0);

// Locución (public/voz/locucion.mp3): tramos [desde, hasta] del archivo, en segundos (cortados en sus pausas),
// y en qué segundo del video suena cada uno. Algunos entran un poco antes del corte para que la voz lleve al cambio de escena.
const VOZ = [
  { desde: 0.16, hasta: 1.48, en: 0.25 }, // ¿Tu ducha sale tibia?
  { desde: 1.67, hasta: 3.02, en: 2.45 }, // Es el sarro.
  { desde: 3.41, hasta: 4.93, en: 3.95 }, // Y te sube la cuenta de la luz.
  { desde: 5.26, hasta: 13.02, en: 5.55 }, // Con Calora, agendar… ¡y listo, quedas agendado! (chat)
  { desde: 13.17, hasta: 15.49, en: 16.2 }, // Atendemos termos a muro de todas las marcas.
  { desde: 15.62, hasta: 17.26, en: 19.6 }, // Agua caliente otra vez.
  { desde: 17.40, hasta: 19.47, en: 22.9 }, // Escríbenos por WhatsApp y agenda hoy.
];
// La música baja (0.6 → 0.22) mientras habla la voz, con rampas de 0.2 s.
const musica = (f: number) => {
  const t = f / FPS;
  const habla = Math.max(0, ...VOZ.map((v) => {
    const fin = v.en + v.hasta - v.desde;
    return Math.min(1, Math.max(0, (t - v.en + 0.2) / 0.2), Math.max(0, (fin + 0.2 - t) / 0.2));
  }));
  return 0.6 - 0.38 * habla;
};

export const Promo: React.FC = () => (
  <AbsoluteFill>
    <BgMesh />
    <Series>
      {ESCENAS.map(({ C, dur }, i) => (
        <Series.Sequence key={i} durationInFrames={dur}><C /></Series.Sequence>
      ))}
    </Series>
    <Grade />
    <Grain />
    <Vignette />

    <Audio src={staticFile("sfx/music.wav")} volume={musica} />
    {VOZ.map((v, i) => (
      <Sequence key={"v" + i} from={s(v.en)} durationInFrames={s(v.hasta - v.desde) + 1}>
        <Audio src={staticFile("voz/locucion.mp3")} trimBefore={s(v.desde)} trimAfter={s(v.hasta) + 1} volume={1} />
      </Sequence>
    ))}
    {/* whoosh 3 cuadros antes de cada corte */}
    {ESCENAS.slice(1).map((_, i) => (
      <Sequence key={"w" + i} from={inicio(i + 1) - 3} durationInFrames={s(1)}><Audio src={staticFile("sfx/whoosh.wav")} volume={0.7} /></Sequence>
    ))}
    {/* "pop" de cada mensaje y campanita del sello */}
    {CHAT.map((m, i) => (
      <Sequence key={"p" + i} from={inicio(2) + s(m.at) - 2} durationInFrames={s(0.6)}><Audio src={staticFile("sfx/pop.wav")} volume={0.9} /></Sequence>
    ))}
    <Sequence from={inicio(2) + s(SELLO_AT) - 2} durationInFrames={s(1.5)}><Audio src={staticFile("sfx/ding.wav")} volume={0.8} /></Sequence>
    <Sequence from={inicio(6) + 20} durationInFrames={s(1.5)}><Audio src={staticFile("sfx/ding.wav")} volume={0.6} /></Sequence>
  </AbsoluteFill>
);
