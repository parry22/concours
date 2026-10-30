// Builds one voice clip per scene from narration.json, then writes src/timings.json with each clip's length.
// Scene lengths in the video follow the clips, so swapping the voice re-times the whole cut.
//
//   node scripts/voice.mjs                       Sarvam (bulbul, SARVAM_API_KEY in .env), the default
//   node scripts/voice.mjs --provider=say        macOS `say` (no account needed)
//   ELEVENLABS_API_KEY=... node scripts/voice.mjs --provider=elevenlabs
//   node scripts/voice.mjs --provider=files      keep clips already in public/voice/ (e.g. exported from
//                                                Fish Audio, one <scene id>.wav or .mp3 each) and only re-measure
//   --only=<scene id>                            redo one line
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const narration = JSON.parse(readFileSync(join(root, "narration.json"), "utf8"));
const outDir = join(root, "public", "voice");
mkdirSync(outDir, { recursive: true });

// Keys live in video/.env (gitignored), never in the repo.
const envFile = join(root, ".env");
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, "utf8").split("\n")) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
}

const arg = process.argv.find((a) => a.startsWith("--provider="));
const provider = arg ? arg.split("=")[1] : "sarvam";
const only = process.argv.find((a) => a.startsWith("--only="))?.split("=")[1];

const duration = (file) =>
  Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]).toString().trim());

const findClip = (id) => ["wav", "mp3"].map((ext) => join(outDir, `${id}.${ext}`)).find((f) => existsSync(f));

// One format for the video: 48 kHz mono wav, leading and trailing silence trimmed so timing is the speech itself.
function finish(src, id) {
  const tmp = join(outDir, `${id}.tmp.wav`);
  execFileSync("ffmpeg", [
    "-v", "error", "-y", "-i", src,
    // Pauses inside the line are capped at voice.maxPause seconds so the read stays brisk.
    "-af", `silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse${
      narration.voice.maxPause ? `,silenceremove=stop_periods=-1:stop_duration=${narration.voice.maxPause}:stop_threshold=-42dB` : ""}`,
    "-ar", "48000", "-ac", "1", tmp,
  ]);
  rmSync(src);
  execFileSync("mv", [tmp, join(outDir, `${id}.wav`)]);
}

async function sarvam(scene) {
  const key = process.env.SARVAM_API_KEY;
  if (!key) throw new Error("Set SARVAM_API_KEY in video/.env");
  const { model, speaker, pace, temperature } = narration.voice.sarvam;
  const res = await fetch("https://api.sarvam.ai/text-to-speech", {
    method: "POST",
    headers: { "api-subscription-key": key, "content-type": "application/json" },
    body: JSON.stringify({ text: scene.text, language_code: "en-IN", model, speaker, pace, temperature, speech_sample_rate: 48000 }),
  });
  if (!res.ok) throw new Error(`Sarvam ${res.status}: ${await res.text()}`);
  const { audios } = await res.json();
  const raw = join(outDir, `${scene.id}.raw.wav`);
  writeFileSync(raw, Buffer.concat(audios.map((a) => Buffer.from(a, "base64"))));
  finish(raw, scene.id);
}

async function elevenlabs(scene) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) throw new Error("Set ELEVENLABS_API_KEY");
  const { voiceId, model } = narration.voice.elevenlabs;
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}?output_format=mp3_44100_128`, {
    method: "POST",
    headers: { "xi-api-key": key, "content-type": "application/json" },
    body: JSON.stringify({ text: scene.text, model_id: model, voice_settings: { stability: 0.5, similarity_boost: 0.75 } }),
  });
  if (!res.ok) throw new Error(`ElevenLabs ${res.status}: ${await res.text()}`);
  const mp3 = join(outDir, `${scene.id}.mp3`);
  writeFileSync(mp3, Buffer.from(await res.arrayBuffer()));
  finish(mp3, scene.id);
}

function say(scene) {
  const { voice, rate } = narration.voice.say;
  const aiff = join(outDir, `${scene.id}.aiff`);
  execFileSync("say", ["-v", voice, "-r", String(rate), "-o", aiff, scene.text]);
  finish(aiff, scene.id);
}

// Drop clips for scenes that no longer exist.
const ids = new Set(narration.scenes.map((s) => s.id));
for (const f of readdirSync(outDir)) if (!ids.has(f.replace(/\.(wav|mp3)$/, ""))) rmSync(join(outDir, f));

const timingsFile = join(root, "src", "timings.json");
const timings = existsSync(timingsFile) ? (JSON.parse(readFileSync(timingsFile, "utf8")).clips ?? {}) : {};
for (const scene of narration.scenes) {
  if (only && scene.id !== only) continue;
  if (provider === "sarvam") await sarvam(scene);
  else if (provider === "say") say(scene);
  else if (provider === "elevenlabs") await elevenlabs(scene);
  else if (provider !== "files") throw new Error(`Unknown provider ${provider}`);
  const clip = findClip(scene.id);
  if (!clip) throw new Error(`No clip for ${scene.id} in public/voice/`);
  timings[scene.id] = { file: `voice/${clip.split("/").pop()}`, seconds: Number(duration(clip).toFixed(3)) };
  console.log(`${scene.id.padEnd(10)} ${timings[scene.id].seconds.toFixed(2)}s`);
}
// Phrase timings: split the line at punctuation and match each break to a real pause in the clip, so visual cues
// land on the phrase (character share is only used inside a phrase).
function phrases(scene, file, seconds) {
  const parts = scene.text.match(/[^.,:;!?]+[.,:;!?]*/g).map((p) => p.trim()).filter(Boolean);
  const out = execFileSync("sh", ["-c", `ffmpeg -hide_banner -i "${file}" -af silencedetect=n=-36dB:d=0.09 -f null - 2>&1`]).toString();
  const starts = [...out.matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
  const ends = [...out.matchAll(/silence_end: ([\d.]+)/g)].map((m) => Number(m[1]));
  const pauses = starts.map((s, i) => ({ s, e: ends[i] ?? s, d: (ends[i] ?? s) - s })).filter((p) => p.s > 0.05 && p.e < seconds - 0.05);
  // Expected break points by character share; take the pause nearest each, in order.
  const total = scene.text.length;
  let acc = 0;
  const breaks = [];
  let lastPause = -1;
  for (let i = 0; i < parts.length - 1; i++) {
    acc += parts[i].length + 1;
    const guess = (acc / total) * seconds;
    let best = null;
    for (let k = lastPause + 1; k < pauses.length; k++) {
      if (!best || Math.abs((pauses[k].s + pauses[k].e) / 2 - guess) < Math.abs((best.p.s + best.p.e) / 2 - guess)) best = { p: pauses[k], k };
    }
    if (best && Math.abs((best.p.s + best.p.e) / 2 - guess) < 1.2) {
      breaks.push([best.p.s, best.p.e]);
      lastPause = best.k;
    } else {
      const floor = (breaks.at(-1)?.[1] ?? 0) + 0.15 * parts[i].length / 2;
      breaks.push([Math.max(guess, floor), Math.max(guess, floor)]);
    }
  }
  return parts.map((text, i) => ({
    text,
    start: Number((i === 0 ? 0 : breaks[i - 1][1]).toFixed(3)),
    end: Number((i === parts.length - 1 ? seconds : breaks[i][0]).toFixed(3)),
  }));
}

// Lay the scenes end to end: lead-in silence, the clip, then a tail (plus any hold for the visuals to land).
const { fps, lead, tail } = narration.timing;
let from = 0;
const scenes = narration.scenes.map((scene) => {
  const t = timings[scene.id];
  const voiceAt = Math.round((scene.lead ?? lead) * fps);
  const frames = voiceAt + Math.ceil(t.seconds * fps) + Math.round((tail + (scene.hold ?? 0)) * fps);
  const row = { id: scene.id, text: scene.text, file: t.file, seconds: t.seconds, from, frames, voiceAt,
    phrases: phrases(scene, join(root, "public", t.file), t.seconds) };
  from += frames;
  return row;
});
for (const id of Object.keys(timings)) if (!ids.has(id)) delete timings[id];
writeFileSync(timingsFile, JSON.stringify({ fps, totalFrames: from, scenes, clips: timings }, null, 2) + "\n");
console.log(`video ${(from / fps).toFixed(1)}s`);
