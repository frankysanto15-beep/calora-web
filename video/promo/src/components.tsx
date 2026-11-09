import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { theme } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const BgMesh: React.FC = () => {
  const frame = useCurrentFrame();
  const d1 = Math.sin(frame / 55) * 50, d2 = Math.cos(frame / 70) * 40;
  return (
    <AbsoluteFill style={{ background: theme.colors.bg }}>
      <div style={{ position: "absolute", width: 1300, height: 1300, borderRadius: "50%", top: -520, left: -380 + d1, filter: "blur(60px)",
        background: `radial-gradient(circle, ${theme.colors.peach}, transparent 62%)` }} />
      <div style={{ position: "absolute", width: 1000, height: 1000, borderRadius: "50%", bottom: -420, right: -300 - d2, filter: "blur(70px)",
        background: `radial-gradient(circle, ${theme.colors.bgAlt}, transparent 65%)` }} />
    </AbsoluteFill>
  );
};

export const Grade: React.FC = () => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <AbsoluteFill style={{ backgroundColor: theme.colors.primary, mixBlendMode: "soft-light", opacity: 0.1 }} />
    <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(29,58,51,0.08), transparent 26%, transparent 74%, rgba(29,58,51,0.14))" }} />
  </AbsoluteFill>
);

export const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  const noise = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='220'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='220' height='220' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E")`;
  return <AbsoluteFill style={{ pointerEvents: "none", backgroundImage: noise, backgroundSize: "220px",
    backgroundPosition: `${(frame * 7) % 220}px ${(frame * 13) % 220}px`, opacity: 0.06, mixBlendMode: "multiply" }} />;
};

export const Vignette: React.FC = () => (
  <AbsoluteFill style={{ pointerEvents: "none", background: "radial-gradient(ellipse at center, transparent 58%, rgba(29,58,51,0.2) 100%)" }} />
);

/** Entrada: opacidad + subida + escala, con resorte. */
export const Entrance: React.FC<{ delay?: number; children: React.ReactNode; style?: React.CSSProperties; from?: number }> = ({ delay = 0, children, style, from = 40 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: theme.spring.smooth });
  return (
    <div style={{ opacity: p, transform: `translateY(${interpolate(p, [0, 1], [from, 0])}px) scale(${interpolate(p, [0, 1], [0.94, 1])})`, ...style }}>
      {children}
    </div>
  );
};

/** Salida de escena: más rápida que la entrada (10 cuadros). */
export const Exit: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = [durationInFrames - 11, durationInFrames - 1];
  const y = interpolate(frame, t, [0, -60], { easing: theme.ease.in, ...clamp });
  const o = interpolate(frame, t, [1, 0], { easing: theme.ease.in, ...clamp });
  const s = interpolate(frame, t, [1, 0.97], { easing: theme.ease.in, ...clamp });
  return <AbsoluteFill style={{ opacity: o, transform: `translateY(${y}px) scale(${s})` }}>{children}</AbsoluteFill>;
};

/** Titular palabra por palabra; las palabras en `highlight` van en el color héroe. */
export const WordReveal: React.FC<{ text: string; delay?: number; per?: number; highlight?: string[]; style?: React.CSSProperties }> = ({ text, delay = 0, per = 3, highlight = [], style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 26, rowGap: 0, ...style }}>
      {text.split(" ").map((w, i) => {
        const p = spring({ frame: frame - delay - i * per, fps, config: theme.spring.snappy });
        return (
          <span key={i} style={{ display: "inline-block", opacity: p, color: highlight.includes(w) ? theme.colors.primary : undefined,
            transform: `translateY(${interpolate(p, [0, 1], [34, 0])}px) scale(${interpolate(p, [0, 1], [0.9, 1])})` }}>{w}</span>
        );
      })}
    </div>
  );
};

export const headline: React.CSSProperties = {
  fontFamily: theme.fonts.display, fontWeight: 700, fontSize: 112, lineHeight: 1.02, letterSpacing: "-0.035em",
  color: theme.colors.ink, textAlign: "center",
};
export const body: React.CSSProperties = { fontFamily: theme.fonts.body, fontWeight: 500, fontSize: 46, lineHeight: 1.3, color: theme.colors.inkSoft, textAlign: "center" };

/** Imagen fija con Ken Burns (zoom lento + paneo). */
export const KenBurns: React.FC<{ src: string; zoomTo?: number; zoomFrom?: number; pan?: number; style?: React.CSSProperties }> = ({ src, zoomFrom = 1, zoomTo = 1.08, pan = -20, style }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [zoomFrom, zoomTo], { easing: theme.ease.inOut, ...clamp });
  const x = interpolate(frame, [0, durationInFrames], [0, pan], { easing: theme.ease.inOut, ...clamp });
  return <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "contain", transform: `scale(${scale}) translateX(${x}px)`, ...style }} />;
};

export const Drop: React.FC<{ size: number }> = ({ size }) => (
  <svg viewBox="0 0 22 28" width={size} height={(size * 28) / 22}>
    <path d="M11 1C11 1 2 11.5 2 18a9 9 0 0 0 18 0C20 11.5 11 1 11 1Z" fill="none" stroke={theme.colors.ink} strokeWidth="2.4" />
    <path d="M3.2 18h15.6a7.8 7.8 0 0 1-15.6 0Z" fill={theme.colors.primary} />
  </svg>
);

export const Check: React.FC<{ size: number; color: string; progress?: number }> = ({ size, color, progress = 1 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size}>
    <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke={color} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"
      strokeDasharray="24" strokeDashoffset={24 * (1 - progress)} />
  </svg>
);

export const WaIcon: React.FC<{ size: number; color: string }> = ({ size, color }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill={color}>
    <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.3-.4.8-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.3c0-.1-.2-.2-.4-.3Z" />
  </svg>
);
