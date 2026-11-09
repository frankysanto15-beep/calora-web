// Única fuente de colores, curvas y resortes. Paleta de calora-web.
import { Easing } from "remotion";

export const theme = {
  colors: {
    bg: "#f0eadc",
    bgAlt: "#e7dfcc",
    ink: "#1d3a33",
    inkSoft: "#3f5a52",
    primary: "#df6432", // color héroe: máximo un elemento por cuadro
    peach: "#f4d9c6",
    card: "#fbf7ef",
    wa: "#2bc463",
    waInk: "#0f2a1e",
    bubbleIn: "#ffffff",
    bubbleOut: "#d9fdd3",
    glow: "rgba(43, 196, 99, 0.45)",
  },
  fonts: { display: "Fraunces", body: "Figtree" },
  ease: {
    out: Easing.bezier(0.16, 1, 0.3, 1),
    inOut: Easing.bezier(0.83, 0, 0.17, 1),
    in: Easing.bezier(0.7, 0, 0.84, 0),
  },
  spring: {
    snappy: { damping: 14, stiffness: 160, mass: 0.6 },
    smooth: { damping: 20, stiffness: 90, mass: 1 },
    bouncy: { damping: 11, stiffness: 170, mass: 0.7 },
  },
} as const;
