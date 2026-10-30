# Concours demo video

A ~65-second demo built in [Remotion](https://www.remotion.dev) (React → MP4), light mode, in the style of the
reference launch video: one UI moment per spoken line, a close camera that follows each interaction, a hand cursor,
typed input and ticking checklists. The UI is redrawn in light mode from the real product screens and copy.

```
narration.json        the script: one line per scene, plus voice settings and extra seconds per scene
scripts/voice.mjs     one voice clip per scene, then src/timings.json (scene layout and phrase timings)
scripts/music.py      synthesised score and sound effects, following src/timings.json
scripts/stills.mjs    preview stills into out/stills/
src/scenes.tsx        every scene; src/Demo.tsx puts them in order with voice and music
src/ui/               kinetic type (Text), light UI kit and camera (Kit), colour wash (Atmos), logo
```

Scene lengths follow the voice clips, and pauses inside a line are capped at `voice.maxPause` (0.2 s) for pace. Words appear when the voice says them: `voice.mjs` finds the pauses in each
clip and matches them to the punctuation, so a new voice re-times everything.

## Render

```bash
npm install
npm run render            # out/concours-demo.mp4
npm run studio            # live preview with a timeline
node scripts/stills.mjs   # two stills per scene
```

## Voice

Default: Sarvam `bulbul:v4-flash`, speaker `girish_en_documentary`. The key goes in `video/.env`
(`SARVAM_API_KEY=...`, gitignored). Other speakers to try: `shubh_en_narration`, `sarang_en_narration`,
`simran_en_narration`, `shubh_en_ads`, `nachiket_en_ads`. Samples are in `out/voice-samples/`.

```bash
node scripts/voice.mjs                          # Sarvam
node scripts/voice.mjs --only=gates             # redo one line
ELEVENLABS_API_KEY=... node scripts/voice.mjs --provider=elevenlabs
node scripts/voice.mjs --provider=files         # your own clips in public/voice/<scene id>.wav (e.g. Fish Audio)
```

After any voice change, run `npm run music`, then `npm run render`.

## Music

`public/music.wav` is synthesised (no licence needed). To use a licensed track, replace that file with one at least
as long as the video. `src/Demo.tsx` ducks it under the voice. The five gate hits in the score match `gateTick` in `src/scenes.tsx`.

## Numbers on screen

Only figures shown by the product on the seeded sample project: v1 $3,714/day, v2 $3,961/day, the 200-case queue,
1,762,489 payments, and the five gate rules. Money figures carry a "Sample project · simulated card payments" label.
