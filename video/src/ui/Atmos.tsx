import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// Soft colour wash on white, like the reference's mint fog but in the Concours family. `amount` 0 is plain white.
export const Wash: React.FC<{ amount?: number; warm?: number }> = ({ amount = 0.6, warm = 0 }) => {
  const f = useCurrentFrame();
  const blob = (x: number, y: number, r: number, color: string, ph: number) => (
    <div style={{ position: "absolute", left: x + Math.sin(f / 120 + ph) * 110 - r, top: y + Math.cos(f / 150 + ph) * 70 - r, width: r * 2, height: r * 2,
      borderRadius: "50%", background: `radial-gradient(circle, ${color} 0%, transparent 64%)` }} />
  );
  return (
    <AbsoluteFill style={{ background: "#ffffff", overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity: amount * (1 - warm) }}>
        {blob(1500, 220, 760, "rgba(236,72,153,0.20)", 0)}
        {blob(380, 900, 820, "rgba(139,92,246,0.20)", 2)}
        {blob(1750, 980, 600, "rgba(99,102,241,0.16)", 4)}
        {blob(250, 120, 560, "rgba(251,179,156,0.30)", 1)}
      </AbsoluteFill>
      <AbsoluteFill style={{ opacity: amount * warm }}>
        {blob(1500, 220, 760, "rgba(251,191,36,0.22)", 0)}
        {blob(380, 900, 820, "rgba(249,115,22,0.16)", 2)}
        {blob(1750, 980, 600, "rgba(244,63,94,0.12)", 4)}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
