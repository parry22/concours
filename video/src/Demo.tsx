import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import timings from "./timings.json";
import { C, EASE, IN, prog, SANS, SceneInfo } from "./lib";
import { Close, Drift, Gates, Holdout, Hook, Intro, Problem, Protect, Questions, Queue, Solvers, Trust, Upload, V1, V2 } from "./scenes";
import { Wash } from "./ui/Atmos";

const SCENES: Record<string, React.FC<{ scene: SceneInfo }>> = {
  hook: Hook, problem: Problem, intro: Intro, upload: Upload, questions: Questions, protect: Protect, holdout: Holdout,
  v1: V1, queue: Queue, drift: Drift, solvers: Solvers, gates: Gates, v2: V2, trust: Trust, close: Close,
};
const scenes = timings.scenes as SceneInfo[];
const OVERLAP = 10;

// How much colour wash sits behind each scene: near-white for the opening type, full wash for the brand
// moments, a light wash under the product, warm for the drift beat.
const WASH: Record<string, number> = { hook: 0.12, problem: 0.12, intro: 1, close: 1 };
const WARM: Record<string, number> = { drift: 1 };

// Scenes hand over with a short dissolve and a slight push.
const Shell: React.FC<{ frames: number; children: React.ReactNode; first: boolean }> = ({ frames, children, first }) => {
  const f = useCurrentFrame();
  const inP = first ? 1 : prog(f, 0, OVERLAP, EASE);
  const outP = prog(f, frames, frames + OVERLAP, IN);
  return (
    <AbsoluteFill style={{ opacity: inP * (1 - outP), transform: `scale(${0.985 + 0.015 * inP + 0.02 * outP})`,
      filter: outP > 0 || inP < 1 ? `blur(${(1 - inP) * 8 + outP * 8}px)` : undefined }}>
      {children}
    </AbsoluteFill>
  );
};

const Background: React.FC = () => {
  const f = useCurrentFrame();
  const level = (m: Record<string, number>, d: number) => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const s of scenes) {
      xs.push(s.from, s.from + s.frames - 1);
      ys.push(m[s.id] ?? d, m[s.id] ?? d);
    }
    return interpolate(f, xs, ys, { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  };
  return <Wash amount={level(WASH, 0.5)} warm={level(WARM, 0)} />;
};

// Music sits up between lines and ducks under the voice.
const voiceWindows = scenes.map((s) => [s.from + s.voiceAt, s.from + s.voiceAt + Math.ceil(s.seconds * 30)]);
const musicVolume = (f: number) => {
  let duck = 0;
  for (const [a, b] of voiceWindows) {
    duck = Math.max(duck, interpolate(f, [a - 5, a, b, b + 8], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  }
  return 0.55 - 0.3 * duck;
};

export const Demo: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, color: C.fg }}>
    <Background />
    {scenes.map((s, i) => {
      const Scene = SCENES[s.id];
      return (
        <Sequence key={s.id} from={s.from} durationInFrames={s.frames + OVERLAP} name={s.id}>
          <Shell frames={s.frames} first={i === 0}>
            <Scene scene={s} />
          </Shell>
          <Sequence from={s.voiceAt} layout="none" name={`voice ${s.id}`}>
            <Audio src={staticFile(s.file)} volume={1} />
          </Sequence>
        </Sequence>
      );
    })}
    <Audio src={staticFile("music.wav")} volume={musicVolume} />
  </AbsoluteFill>
);
