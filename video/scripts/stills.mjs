// Renders preview stills: node scripts/stills.mjs 120 313 ...  (frames), or no args for one per scene.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync, readFileSync } from "node:fs";

const t = JSON.parse(readFileSync("src/timings.json", "utf8"));
const frames = process.argv.slice(2).length
  ? process.argv.slice(2).map(Number)
  : t.scenes.flatMap((s) => [s.from + Math.round(s.frames * 0.45), s.from + Math.round(s.frames * 0.9)]);
const serveUrl = await bundle({ entryPoint: "src/index.ts" });
const composition = await selectComposition({ serveUrl, id: "Demo" });
mkdirSync("out/stills", { recursive: true });
for (const frame of frames) {
  const id = t.scenes.findLast((s) => s.from <= frame)?.id ?? "x";
  await renderStill({ composition, serveUrl, frame, output: `out/stills/${String(frame).padStart(4, "0")}-${id}.jpg`, imageFormat: "jpeg", jpegQuality: 80, scale: 0.5 });
  console.log(frame, id);
}
