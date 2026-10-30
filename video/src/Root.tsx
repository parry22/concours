import React from "react";
import { Composition } from "remotion";
import { Demo } from "./Demo";
import "./fonts";
import timings from "./timings.json";

export const Root: React.FC = () => (
  <Composition id="Demo" component={Demo} durationInFrames={timings.totalFrames + 10} fps={timings.fps} width={1920} height={1080} />
);
