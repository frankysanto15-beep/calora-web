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

    <Audio src={staticFile("sfx/music.wav")} volume={0.6} />
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
