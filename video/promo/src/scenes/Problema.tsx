import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Entrance, Exit, KenBurns, WordReveal, body, headline } from "../components";
import { theme } from "../theme";

/** Gancho: mascota tibia + pregunta. Se mueve desde el cuadro 0. */
export const Gancho: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: theme.spring.bouncy });
  const float = Math.sin(frame / 18) * 6;
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 300 }}>
        <WordReveal text="¿Tu ducha sale tibia?" highlight={["tibia?"]} per={4} style={{ ...headline, width: 900 }} />
        <div style={{ width: 1020, height: 945, marginTop: 70, opacity: pop,
          transform: `translateY(${interpolate(pop, [0, 1], [120, 0]) + float}px) scale(${interpolate(pop, [0, 1], [0.85, 1])})` }}>
          <KenBurns src="img/tibia.webp" zoomTo={1.07} />
        </div>
      </AbsoluteFill>
    </Exit>
  );
};

/** El sarro como causa. */
export const Sarro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: theme.spring.smooth });
  return (
    <Exit>
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 300 }}>
        <WordReveal text="Es el sarro." highlight={["sarro."]} style={{ ...headline }} />
        <Entrance delay={14}><p style={{ ...body, width: 860, margin: "28px 0 0" }}>Gasta más luz y acorta la vida de tu termo.</p></Entrance>
        <div style={{ width: 1020, height: 945, marginTop: 30, opacity: p, transform: `scale(${interpolate(p, [0, 1], [1.12, 1])})` }}>
          <KenBurns src="img/sarro.webp" zoomFrom={1.06} zoomTo={1} pan={18} />
        </div>
      </AbsoluteFill>
    </Exit>
  );
};
