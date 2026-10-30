import React from "react";
import { Audio, Easing, interpolate, Sequence, staticFile } from "remotion";

// Light theme for the video, in the reference's style: white canvas, flat cards, thin borders, one accent family.
// The accent is the Concours gradient, taken a step deeper so it reads on white.
export const C = {
  bg: "#ffffff",
  fg: "#0e0e10",
  subtle: "#5f5f67",
  muted: "#9a9aa2",
  border: "#e8e8eb",
  row: "#f5f5f6",
  card: "#ffffff",
  violet: "#8b5cf6",
  ink: "#6d28d9",
  pink: "#ec4899",
  peach: "#fbb39c",
  warn: "#b45309",
  warnBg: "#fef3c7",
  danger: "#dc2626",
  dangerBg: "#fee2e2",
  okBg: "#ede9fe",
};
export const GRAD = "linear-gradient(180deg, #f4845f 0%, #ec4899 34%, #a855f7 66%, #6366f1 100%)";
export const GRAD_X = "linear-gradient(90deg, #f4845f 0%, #ec4899 34%, #a855f7 66%, #6366f1 100%)";
export const SANS = "Geist, ui-sans-serif, system-ui, sans-serif";
export const MONO = "Geist Mono, ui-monospace, Menlo, monospace";
export const FPS = 30;

export type Phrase = { text: string; start: number; end: number };
export type SceneInfo = { id: string; text: string; file: string; seconds: number; from: number; frames: number; voiceAt: number; phrases: Phrase[] };

// Two curves for everything: a long ease-in-out for camera and layout moves, an expo-out for arrivals.
export const EASE = Easing.bezier(0.65, 0, 0.35, 1);
export const OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const IN = Easing.bezier(0.7, 0, 0.84, 0);

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// 0..1 progress between two frames with a curve.
export const prog = (f: number, a: number, b: number, ease = OUT) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

// Keyframed value: [[frame, value], ...], eased between each pair.
export const keys = (f: number, k: [number, number][], ease = EASE) => {
  if (f <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) {
    if (f <= k[i][0]) return lerp(k[i - 1][1], k[i][1], ease(clamp01((f - k[i - 1][0]) / Math.max(1, k[i][0] - k[i - 1][0]))));
  }
  return k[k.length - 1][1];
};

// Frame (inside a scene) when phrase `i` starts, or when the voice reaches `word` within it.
export const at = (scene: SceneInfo, i: number, word?: string) => {
  const p = scene.phrases[i];
  if (!p) throw new Error(`phrase ${i} not in ${scene.id}`);
  let s = p.start;
  if (word) {
    const k = p.text.indexOf(word);
    if (k < 0) throw new Error(`"${word}" not in phrase ${i} of ${scene.id}`);
    s = p.start + (k / p.text.length) * (p.end - p.start);
  }
  return Math.round(scene.voiceAt + s * FPS);
};
export const endOf = (scene: SceneInfo, i: number) => Math.round(scene.voiceAt + scene.phrases[i].end * FPS);

export const Sfx: React.FC<{ at: number; name: string; volume?: number }> = ({ at: f, name, volume = 0.5 }) => (
  <Sequence from={Math.max(0, Math.round(f))} durationInFrames={150} layout="none">
    <Audio src={staticFile(`sfx/${name}.wav`)} volume={volume} />
  </Sequence>
);
