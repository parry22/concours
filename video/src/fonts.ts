import { continueRender, delayRender, staticFile } from "remotion";

// Geist and Geist Mono, the product's faces. Every frame waits for them, and text is measured only after they load.
const handle = delayRender("fonts");
let loaded = false;
export const fontsReady: Promise<void> = Promise.all([
  new FontFace("Geist", `url(${staticFile("fonts/geist-latin.woff2")})`, { weight: "100 900" }).load(),
  new FontFace("Geist Mono", `url(${staticFile("fonts/geist-mono-latin.woff2")})`, { weight: "100 900" }).load(),
]).then((faces) => {
  faces.forEach((f) => document.fonts.add(f));
  loaded = true;
  continueRender(handle);
});

const ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
const cache = new Map<string, number>();
export const measure = (text: string, size: number, weight: number, family = "Geist") => {
  const key = `${text}|${size}|${weight}|${family}`;
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  if (!ctx) return text.length * size * 0.5;
  ctx.font = `${weight} ${size}px ${family}`;
  const w = ctx.measureText(text).width;
  if (loaded) cache.set(key, w);
  return w;
};
