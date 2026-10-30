import React from "react";
import { useCurrentFrame } from "remotion";
import { measure } from "../fonts";
import { C, clamp01, FPS, GRAD_X, IN, OUT, prog, SANS, SceneInfo } from "../lib";

export type Word = { w: string; at: number };

// Word timings for a phrase of the voice line: each word lands when the voice reaches it.
export const wordsOf = (scene: SceneInfo, i: number, text?: string): Word[] => {
  const p = scene.phrases[i];
  const src = text ?? p.text;
  const parts = src.split(" ");
  let acc = 0;
  return parts.map((w) => {
    const k = p.text.indexOf(w.replace(/[.,:]/g, ""), acc);
    const share = (k >= 0 ? k : acc) / p.text.length;
    if (k >= 0) acc = k + 1;
    return { w, at: Math.round(scene.voiceAt + (p.start + share * (p.end - p.start)) * FPS) - 2 };
  });
};

// Evenly spaced words from a start frame, for lines that are not spoken.
export const wordsAt = (text: string, start: number, gap = 3): Word[] => text.split(" ").map((w, i) => ({ w, at: start + i * gap }));

// The reference's signature move: words arrive one by one and the line stays centred, so the words already on
// screen glide aside to make room. Each word opens its space first, then fades up out of a blur.
export const Line: React.FC<{
  words: Word[];
  size?: number;
  weight?: number;
  color?: string;
  accent?: string[];
  accentColor?: string;
  exit?: number;
  exitDur?: number;
  align?: "center" | "left";
  x?: number;
  y?: number;
  dim?: string[];
}> = ({ words, size = 76, weight = 500, color = C.fg, accent = [], accentColor, exit, exitDur = 16, align = "center", x = 960, y = 540, dim = [] }) => {
  const f = useCurrentFrame();
  // Widths include the tight tracking applied below, so spacing matches what is drawn.
  const ls = -size * 0.03;
  const space = measure(" ", size, weight) + ls;
  const widths = words.map((w) => measure(w.w, size, weight) + ls * w.w.length);
  const open = words.map((w) => prog(f, w.at - 4, w.at + 12, OUT));
  const total = widths.reduce((s, w, i) => s + (w + (i ? space : 0)) * open[i], 0);
  const out = exit !== undefined ? prog(f, exit, exit + exitDur, IN) : 0;
  if (out >= 1 || f < words[0].at - 6) return null;
  let cursor = align === "center" ? x - total / 2 : x;
  return (
    <div style={{ position: "absolute", left: 0, top: y - size * 0.62, width: 1920, height: size * 1.4, opacity: 1 - out, filter: `blur(${out * 10}px)`, transform: `translateY(${-out * 18}px)` }}>
      {words.map((w, i) => {
        const left = cursor + (i ? space * open[i] : 0);
        cursor = left + widths[i] * open[i];
        const p = prog(f, w.at, w.at + 16, OUT);
        const clean = w.w.replace(/[.,:]/g, "");
        const isAccent = accent.some((a) => a.replace(/[.,:]/g, "") === clean);
        const style: React.CSSProperties = isAccent
          ? accentColor ? { color: accentColor } : { backgroundImage: GRAD_X, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }
          : { color: dim.includes(clean) ? C.subtle : color };
        return (
          <span key={i} style={{ position: "absolute", left, top: 0, fontFamily: SANS, fontSize: size, fontWeight: weight, letterSpacing: ls, whiteSpace: "pre",
            lineHeight: 1.25, opacity: clamp01(p * 1.2), filter: `blur(${(1 - p) * 9}px)`, transform: `translateY(${(1 - p) * size * 0.22}px)`, ...style }}>
            {w.w}
          </span>
        );
      })}
    </div>
  );
};

// Small label above or beside a visual.
export const Kicker: React.FC<{ text: string; at: number; exit?: number; x?: number; y?: number; align?: "center" | "left"; color?: string; size?: number }> = ({
  text, at, exit, x = 960, y = 540, align = "center", color = C.subtle, size = 24,
}) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 18);
  const out = exit !== undefined ? prog(f, exit, exit + 14, IN) : 0;
  return (
    <div style={{ position: "absolute", left: align === "center" ? 0 : x, width: align === "center" ? 1920 : undefined, top: y, textAlign: align,
      fontFamily: SANS, fontSize: size, fontWeight: 500, letterSpacing: 0.2, color, opacity: p * (1 - out), filter: `blur(${(1 - p + out) * 6}px)`, transform: `translateY(${(1 - p) * 10}px)` }}>
      {text}
    </div>
  );
};
