import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Drop, Entrance, Exit, KenBurns, WaIcon, WordReveal, body, headline } from "../components";
import { theme } from "../theme";

const TERMOS = ["img/splendid.jpg", "img/ariston.jpg", "img/rheem.webp", "img/tesy.jpg"];

/** Termos a muro de todas las marcas (fotos del cliente). */
export const Marcas: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 280 }}>
        <WordReveal text="Termos a muro de todas las marcas" highlight={["muro"]} per={3} style={{ ...headline, fontSize: 100, width: 960 }} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34, marginTop: 70 }}>
          {TERMOS.map((src, i) => {
            const p = spring({ frame: frame - 12 - i * 5, fps, config: theme.spring.smooth });
            const tilt = [-3, 2.5, -2, 3][i];
            const float = Math.sin(frame / 26 + i * 1.3) * 5;
            const zoom = interpolate(frame, [0, 4 * fps], [1, 1.06], { easing: theme.ease.inOut, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={src} style={{ width: 440, height: 520, borderRadius: 48, background: "#fff", overflow: "hidden", padding: 26,
                boxShadow: "0 30px 60px -24px rgba(29,58,51,0.35)", opacity: p,
                transform: `translateY(${interpolate(p, [0, 1], [90, 0]) + float}px) rotate(${interpolate(p, [0, 1], [tilt * 3, tilt])}deg) scale(${interpolate(p, [0, 1], [0.86, 1])})` }}>
                <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "contain", transform: `scale(${zoom})` }} />
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </Exit>
  );
};

/** Resultado: termo limpio + precio con contador. */
export const Resultado: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const precio = interpolate(frame, [18, 18 + fps], [0, 49990], { easing: theme.ease.out, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const p = spring({ frame: frame - 4, fps, config: theme.spring.smooth });
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 280 }}>
        <WordReveal text="Agua caliente otra vez" highlight={["caliente"]} per={3} style={{ ...headline, width: 920 }} />
        <div style={{ width: 1000, height: 926, marginTop: 20, opacity: p, transform: `scale(${interpolate(p, [0, 1], [0.9, 1])})` }}>
          <KenBurns src="img/calora.webp" zoomTo={1.06} pan={-14} />
        </div>
        <Entrance delay={16}>
          <div style={{ background: theme.colors.ink, color: theme.colors.bg, borderRadius: 999, padding: "22px 48px", display: "flex", alignItems: "baseline", gap: 18 }}>
            <span style={{ fontFamily: theme.fonts.body, fontWeight: 700, fontSize: 42 }}>Desde</span>
            <span style={{ fontFamily: theme.fonts.display, fontWeight: 700, fontSize: 84, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em" }}>
              ${Math.round(precio).toLocaleString("es-CL")}
            </span>
          </div>
        </Entrance>
      </AbsoluteFill>
    </Exit>
  );
};

/** Llamado a la acción: la única cosa que brilla es el botón de WhatsApp. */
export const Cta: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const mark = spring({ frame, fps, config: theme.spring.bouncy });
  const btn = spring({ frame: frame - 22, fps, config: theme.spring.bouncy });
  const breathe = 1 + Math.sin(frame / 14) * 0.02;
  const glow = 50 + Math.sin(frame / 14) * 20;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 40 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22, opacity: mark,
        transform: `scale(${interpolate(mark, [0, 1], [0.6, 1])}) rotate(${interpolate(mark, [0, 1], [-10, 0])}deg)` }}>
        <Drop size={92} />
        <span style={{ fontFamily: theme.fonts.display, fontWeight: 600, fontSize: 150, color: theme.colors.ink, letterSpacing: "-0.03em" }}>calora</span>
      </div>
      <WordReveal text="Agenda tu mantención hoy" delay={8} style={{ ...headline, fontSize: 92, width: 900 }} />
      <div style={{ opacity: btn, transform: `translateY(${interpolate(btn, [0, 1], [60, 0])}px) scale(${interpolate(btn, [0, 1], [0.8, 1]) * breathe})`,
        background: theme.colors.wa, color: theme.colors.waInk, borderRadius: 999, padding: "34px 60px", display: "flex", alignItems: "center", gap: 22,
        fontFamily: theme.fonts.body, fontWeight: 800, fontSize: 56, boxShadow: `0 0 ${glow}px ${theme.colors.glow}, 0 0 ${glow * 2}px rgba(43,196,99,0.2)` }}>
        <WaIcon size={70} color={theme.colors.waInk} /> Escríbenos por WhatsApp
      </div>
      <Entrance delay={32}>
        <div style={{ ...body, fontFamily: theme.fonts.display, fontWeight: 600, fontSize: 68, color: theme.colors.ink, fontVariantNumeric: "tabular-nums" }}>+56 9 7376 5539</div>
        <div style={{ ...body, fontSize: 40, marginTop: 10 }}>Santiago y alrededores · Visita incluida</div>
      </Entrance>
    </AbsoluteFill>
  );
};
