import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Check, Drop, Entrance, Exit, WordReveal, headline } from "../components";
import { theme } from "../theme";

// Momentos del chat, en segundos desde el inicio de la escena (se pasan a cuadros con fps).
export const CHAT = [
  { at: 1.2, out: true, text: "Hola! Quiero mantención para mi termo de 80 L a muro. Estoy en Ñuñoa." },
  { at: 2.9, out: false, typing: 2.1, text: "¡Hola! Son $49.990 con visita incluida. ¿Te sirve mañana a las 10:00?" },
  { at: 4.3, out: true, text: "¡Perfecto!" },
  { at: 5.5, out: false, typing: 4.8, text: "Listo, quedaste agendado", check: true },
];
export const SELLO_AT = 6.3;

const Bubble: React.FC<{ out: boolean; at: number; text: string; check?: boolean }> = ({ out, at, text, check }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - at * fps, fps, config: theme.spring.snappy });
  const draw = interpolate(frame - at * fps, [6, 22], [0, 1], { easing: theme.ease.out, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (p <= 0.001) return null;
  return (
    <div style={{ alignSelf: out ? "flex-end" : "flex-start", maxWidth: "82%", opacity: p,
      transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px) scale(${interpolate(p, [0, 1], [0.85, 1])})`,
      transformOrigin: out ? "100% 100%" : "0% 100%",
      background: out ? theme.colors.bubbleOut : theme.colors.bubbleIn, color: theme.colors.ink,
      borderRadius: 30, borderBottomRightRadius: out ? 8 : 30, borderBottomLeftRadius: out ? 30 : 8,
      padding: "20px 26px", fontFamily: theme.fonts.body, fontWeight: 500, fontSize: 38, lineHeight: 1.3,
      boxShadow: "0 2px 0 rgba(29,58,51,0.08)", display: "flex", alignItems: "center", gap: 12 }}>
      <span>{text}</span>
      {check && <Check size={44} color={theme.colors.wa} progress={draw} />}
    </div>
  );
};

const Typing: React.FC<{ from: number; to: number }> = ({ from, to }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const f = frame - from * fps;
  if (f < 0 || frame >= to * fps) return null;
  const p = spring({ frame: f, fps, config: theme.spring.snappy });
  return (
    <div style={{ alignSelf: "flex-start", background: theme.colors.bubbleIn, borderRadius: 30, borderBottomLeftRadius: 8, padding: "26px 28px",
      display: "flex", gap: 10, opacity: p, transform: `scale(${interpolate(p, [0, 1], [0.8, 1])})`, transformOrigin: "0% 100%" }}>
      {[0, 1, 2].map((i) => (
        <i key={i} style={{ width: 16, height: 16, borderRadius: 99, background: theme.colors.inkSoft,
          opacity: 0.35 + 0.65 * Math.max(0, Math.sin(f / 4 - i * 0.9)), transform: `translateY(${-6 * Math.max(0, Math.sin(f / 4 - i * 0.9))}px)` }} />
      ))}
    </div>
  );
};

export const Agendar: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phone = spring({ frame: frame - 10, fps, config: theme.spring.smooth });
  const sello = spring({ frame: frame - SELLO_AT * fps, fps, config: theme.spring.bouncy });
  const float = Math.sin(frame / 30) * 4;
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 250 }}>
        <WordReveal text="Agendar toma 1 minuto" highlight={["1", "minuto"]} per={3} style={{ ...headline, width: 960 }} />
        <div style={{ position: "relative", marginTop: 50, width: 780, height: 1060, opacity: phone,
          transform: `translateY(${interpolate(phone, [0, 1], [260, 0]) + float}px)` }}>
          <div style={{ position: "absolute", inset: 0, borderRadius: 84, border: `16px solid ${theme.colors.ink}`, background: "#ece4d6", overflow: "hidden",
            boxShadow: "0 50px 90px -30px rgba(29,58,51,0.45)", display: "flex", flexDirection: "column" }}>
            <div style={{ background: theme.colors.ink, padding: "44px 34px 26px", display: "flex", alignItems: "center", gap: 20 }}>
              <div style={{ width: 84, height: 84, borderRadius: 99, background: theme.colors.bg, display: "grid", placeItems: "center" }}><Drop size={40} /></div>
              <div style={{ fontFamily: theme.fonts.body, color: theme.colors.bg }}>
                <div style={{ fontWeight: 700, fontSize: 40 }}>Calora</div>
                <div style={{ fontWeight: 500, fontSize: 28, opacity: 0.75 }}>en línea</div>
              </div>
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 18, padding: "34px 30px" }}>
              {CHAT.map((m, i) => (
                <React.Fragment key={i}>
                  {m.typing != null && <Typing from={m.typing} to={m.at} />}
                  <Bubble out={m.out} at={m.at} text={m.text} check={m.check} />
                </React.Fragment>
              ))}
            </div>
          </div>
          <div style={{ position: "absolute", left: "50%", bottom: -40, opacity: sello,
            transform: `translateX(-50%) rotate(${interpolate(sello, [0, 1], [-14, -4])}deg) scale(${interpolate(sello, [0, 1], [1.6, 1])})`,
            background: theme.colors.wa, color: theme.colors.waInk, borderRadius: 999, padding: "22px 46px",
            fontFamily: theme.fonts.display, fontWeight: 700, fontSize: 64, letterSpacing: "-0.02em", whiteSpace: "nowrap",
            display: "flex", alignItems: "center", gap: 14, boxShadow: `0 0 60px ${theme.colors.glow}` }}>
            <Check size={64} color={theme.colors.waInk} progress={sello} /> ¡Agendado!
          </div>
        </div>
      </AbsoluteFill>
    </Exit>
  );
};

/** Paso a paso corto, para reforzar lo simple. */
export const Pasos: React.FC = () => {
  const items = ["Nos escribes", "Eliges el día", "Vamos a tu casa"];
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 46 }}>
        <WordReveal text="Así de simple:" style={{ ...headline, fontSize: 100 }} />
        <div style={{ display: "grid", gap: 26, width: 840 }}>
          {items.map((t, i) => (
            <Entrance key={t} delay={10 + i * 6}>
              <div style={{ display: "flex", alignItems: "center", gap: 30, background: theme.colors.card, borderRadius: 999, padding: "26px 40px 26px 26px" }}>
                <span style={{ width: 96, height: 96, borderRadius: 99, background: theme.colors.ink, color: theme.colors.bg, display: "grid", placeItems: "center",
                  fontFamily: theme.fonts.display, fontWeight: 700, fontSize: 56 }}>{i + 1}</span>
                <span style={{ fontFamily: theme.fonts.body, fontWeight: 700, fontSize: 56, color: theme.colors.ink }}>{t}</span>
              </div>
            </Entrance>
          ))}
        </div>
      </AbsoluteFill>
    </Exit>
  );
};
