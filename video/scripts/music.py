"""Synthesises the cinematic score and sound effects, so the video ships with no licensed audio.

A hybrid-trailer score in D minor that follows the story in src/timings.json:
  hook → stale     low drone, felt piano, a ticking clock and a heartbeat: tension and space
  intro            reverse swell and Shepard riser, then a braam and sub boom as "This is Concours" lands
  questions → queue  low-string ostinato, wide string pad (Dm–Bb–F–C) and taiko drums, building
  drift            the pulse drops out: a minor-second cluster, heartbeat, filtered riser
  solvers → gates  the pulse returns and builds, a hit on each gate, a Shepard riser across the gates
  v2               impact and the resolution to F major: the emotional peak
  trust → close    piano motif over the drone, a last low boom, a long reverb tail

Replace public/music.wav with any track of your own; the video ducks it under the voice either way.

    ../backend/.venv/bin/python scripts/music.py
"""
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
BPM = 88
BEAT = 60 / BPM
BAR = 4 * BEAT
ROOT = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(11)

layout = json.loads((ROOT / "src" / "timings.json").read_text())
fps = layout["fps"]
scenes = {s["id"]: s for s in layout["scenes"]}
S = {k: s["from"] / fps for k, s in scenes.items()}  # scene starts (s)
V = {k: (s["from"] + s["voiceAt"]) / fps for k, s in scenes.items()}  # voice starts (s)
END = layout["totalFrames"] / fps
TOTAL = END + 1.0
N = int(TOTAL * SR)
t_all = np.arange(N) / SR

# Beat grid anchored so "This is Concours" falls on a downbeat.
GRID0 = V["intro"] % BAR


def grid(t, step=BEAT):
    """Nearest grid time at or after t."""
    k = np.ceil((t - GRID0) / step - 1e-6)
    return GRID0 + k * step


# ---------------------------------------------------------------- building blocks

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def lowpass(x, hz, order=2):
    return sosfilt(butter(order, min(hz, SR / 2 - 100), "low", fs=SR, output="sos"), x)


def highpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def morph_lowpass(x, cutoff, bank=(150, 300, 600, 1200, 2400, 4800)):
    """Time-varying lowpass: crossfade between fixed filters along a per-sample cutoff curve."""
    outs = [lowpass(x, f) for f in bank]
    pos = np.interp(np.log2(np.clip(cutoff, bank[0], bank[-1])), np.log2(bank), np.arange(len(bank)))
    i = np.clip(pos.astype(int), 0, len(bank) - 2)
    w = pos - i
    stack = np.stack(outs)
    idx = np.arange(len(x))
    return stack[i, idx] * (1 - w) + stack[i + 1, idx] * w


def saw(freq, n, phase=0.0):
    """Band-limited (polyBLEP) sawtooth."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    ph = (np.cumsum(f) / SR + phase) % 1.0
    dt = f / SR
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def supersaw(freq, n, voices=7, cents=18):
    """Detuned saw ensemble split across the stereo field."""
    L = np.zeros(n)
    R = np.zeros(n)
    for v in range(voices):
        d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * cents
        s = saw(freq * 2 ** (d / 1200), n, rng.random())
        pan = 0.5 + 0.45 * (v - (voices - 1) / 2) / ((voices - 1) / 2)
        L += s * np.sqrt(1 - pan)
        R += s * np.sqrt(pan)
    return L / voices, R / voices


def adsr(n, a, r, hold=None):
    t = np.arange(n) / SR
    env = np.minimum(1, t / max(a, 1e-4))
    if hold is not None:
        env *= np.where(t > hold, np.exp(-(t - hold) / r), 1.0)
    return env


def place(buf, sig, at):
    i = int(round(at * SR))
    if i < 0:
        sig = sig[-i:]
        i = 0
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def curve(points):
    """Piecewise-linear gain over the whole track from (seconds, gain) points."""
    xs, ys = zip(*sorted(points))
    return np.interp(t_all, xs, ys)


class Bus:
    """Stereo bus with a reverb send."""

    def __init__(self):
        self.L, self.R = np.zeros(N), np.zeros(N)
        self.sL, self.sR = np.zeros(N), np.zeros(N)

    def add(self, at, l, r=None, send=0.3, pan=0.5):
        r = l if r is None else r
        gl, gr = np.sqrt(1 - pan) * 1.414, np.sqrt(pan) * 1.414
        place(self.L, l * gl, at)
        place(self.R, r * gr, at)
        if send:
            place(self.sL, l * gl * send, at)
            place(self.sR, r * gr * send, at)


def reverb_ir(seconds=3.8, predelay=0.03, seed=0):
    """Decorrelated hall IR: bright early part that darkens as it decays."""
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    noise = r.standard_normal(n)
    bright = lowpass(noise, 6000) * np.exp(-t / 0.35)
    dark = lowpass(noise, 1800) * np.exp(-t * 6.9 / seconds)
    ir = 0.5 * bright + dark
    ir *= np.minimum(1, t / 0.02)
    ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
    return ir / np.sqrt(np.sum(ir ** 2))


IR_L, IR_R = reverb_ir(seed=1), reverb_ir(seed=2)


def reverb(l, r, irl=IR_L, irr=IR_R):
    return fftconvolve(l, irl)[: len(l)], fftconvolve(r, irr)[: len(r)]


# ---------------------------------------------------------------- instruments

def piano(note, dur=5.0, vel=1.0):
    """Felt piano: inharmonic partials, higher ones decaying faster, a soft hammer thump."""
    f0 = midi(note)
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    B = 0.00035
    for k in range(1, 14):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        if fk > 9000:
            break
        tau = 2.8 / (1 + 0.7 * (k - 1)) * (220 / max(f0, 110)) ** 0.3
        out += np.sin(2 * np.pi * fk * t + rng.random() * 6.28) * np.exp(-t / tau) / k ** 1.3
    out *= np.minimum(1, t / 0.004)
    hammer = lowpass(rng.standard_normal(n), 900) * np.exp(-t / 0.012) * 0.15
    out = lowpass(out + hammer, 2600) * vel
    return out * np.minimum(1, (dur - t) / 0.3)


def taiko(vel=1.0, big=False):
    n = int((1.6 if big else 0.9) * SR)
    t = np.arange(n) / SR
    f = 40 + 22 * np.exp(-t / 0.05) if not big else 32 + 30 * np.exp(-t / 0.08)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.5 if big else 0.28))
    thump = lowpass(rng.standard_normal(n), 260) * np.exp(-t / 0.04) * 0.9
    slap = bandpass(rng.standard_normal(n), 600, 1800) * np.exp(-t / 0.012) * 0.25
    return np.tanh((body + thump + slap) * 1.4) * vel


def spiccato(note, vel=1.0):
    """Short bowed low string."""
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    s = saw(midi(note) * (1 + 0.002 * np.sin(2 * np.pi * 5 * t)), n, rng.random())
    env = np.minimum(1, t / 0.006) * np.exp(-t / 0.075)
    return bandpass(s, 70, 1700) * env * vel


def boom(dur=3.0, f_hi=55, f_lo=28):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.25)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)
    thump = lowpass(rng.standard_normal(n), 180) * np.exp(-t / 0.08)
    return np.tanh((s + 0.6 * thump) * 1.6)


def braam(dur=4.5, notes=(26, 38, 45, 50), bright=3200):
    """Brass-like low stack: fast filter opening that closes slowly, saturated."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    L = np.zeros(n)
    R = np.zeros(n)
    for note in notes:
        l, r = supersaw(midi(note), n, voices=5, cents=12)
        L += l
        R += r
    cut = 180 + bright * np.minimum(1, t / 0.06) * np.exp(-t / 0.9)
    env = np.minimum(1, t / 0.03) * np.exp(-t / 1.6)
    L = np.tanh(morph_lowpass(L, cut) * 3.5) * env
    R = np.tanh(morph_lowpass(R, cut) * 3.5) * env
    return L, R


def crash(dur=3.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = highpass(lowpass(rng.standard_normal(n), 8500), 2500) * np.exp(-t / 0.9)
    return s * np.minimum(1, t / 0.002)


def shepard(dur, base=110, octaves=6, rate=None):
    """Endlessly rising tone: octave-spaced sines gliding up under a fixed bell-shaped loudness curve."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rate = rate or (1.0 / dur)  # octaves per second
    out = np.zeros(n)
    for k in range(octaves):
        pos = (k + rate * t) % octaves  # position in octaves above base
        f = base * 2 ** pos
        amp = np.exp(-((pos - octaves / 2) ** 2) / 2.2)
        out += np.sin(2 * np.pi * np.cumsum(f) / SR) * amp
    return lowpass(out / octaves, 5000)


def noise_riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    cut = 300 * (16 ** (t / dur))
    return morph_lowpass(highpass(x, 120), cut) * (t / dur) ** 2.2


def reverse_cymbal(dur=2.2):
    return crash(dur)[::-1] * np.linspace(0, 1, int(dur * SR)) ** 1.5


def tick(pitch=2600, vel=1.0):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * pitch * t) * np.exp(-t / 0.006) + 0.4 * highpass(rng.standard_normal(n), 3000) * np.exp(-t / 0.002)
    return s * vel


def heartbeat():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    beat = lambda f: np.sin(2 * np.pi * np.cumsum(f * (1 + 0.4 * np.exp(-t / 0.03))) / SR) * np.exp(-t / 0.11) * np.minimum(1, t / 0.008)
    out = beat(52.0)
    dub = beat(46.0) * 0.7
    k = int(0.24 * SR)
    out[k:] += dub[: n - k]
    return out


# ---------------------------------------------------------------- score

mus = Bus()   # pitched material
drm = Bus()   # drums and hits
fx = Bus()    # risers, swells

# Drone under everything: D1/D2 detuned saws through a slow breathing filter, plus a sine sub.
dL, dR = supersaw(midi(26), N, voices=5, cents=9)
d2L, d2R = supersaw(midi(38), N, voices=5, cents=12)
lfo = 0.5 + 0.5 * np.sin(2 * np.pi * t_all / 9.0)
drone_cut = curve([(0, 160), (V["intro"], 260), (V["intro"] + 0.1, 900), (S["drift"], 500), (S["solvers"], 700),
                   (V["v2"], 1200), (S["trust"], 400), (TOTAL, 200)]) * (0.7 + 0.6 * lfo)
dL = morph_lowpass(dL + 0.6 * d2L, drone_cut)
dR = morph_lowpass(dR + 0.6 * d2R, drone_cut)
sub = np.sin(2 * np.pi * midi(26) * t_all) * 0.3
drone_g = curve([(0, 0), (1.5, 0.2), (V["intro"] - 0.5, 0.32), (V["intro"], 0.7), (S["questions"], 0.3), (S["drift"], 0.6),
                 (S["solvers"], 0.35), (V["v2"], 0.2), (S["trust"], 0.32), (END - 2, 0.25), (TOTAL, 0)])
mus.add(0, (dL + sub) * drone_g * 0.32, (dR + sub) * drone_g * 0.32, send=0.25)

# Felt piano in the opening: a sparse falling motif.
motif = [62, 65, 69, 67, 65, 64, 62, 57]
k = 0
t = grid(0.6)
while t < V["intro"] - 3.4:
    note = motif[k % len(motif)]
    p = piano(note, 6.0, 0.3)
    if k % 2 == 0:
        p = p + piano(note - 12, 6.0, 0.15)
    mus.add(t, p, p, send=0.55, pan=0.35 + 0.3 * (k % 2))
    k += 1
    t += BAR / 2 if k % 3 else BAR

# Clock: tick-tock on each beat through the opening.
t = grid(0.4)
k = 0
while t < V["intro"] - 0.6:
    vel = min(1, (t + 0.5) / 4)
    drm.add(t, tick(2400 if k % 2 == 0 else 1900, 0.16 * vel), send=0.15, pan=0.4 if k % 2 else 0.6)
    k += 1
    t += BEAT

# Heartbeat from the problem scene, and again through drift.
for a, b in ((S["problem"], V["intro"] - 2.5), (S["drift"], S["solvers"] - 0.8)):
    t = grid(a, 2 * BEAT)
    while t < b:
        drm.add(t, heartbeat() * 0.45, send=0.12)
        t += 2 * BEAT

# Into "This is Concours": reverse cymbal, Shepard riser, noise riser; then braam, boom and crash.
HIT = V["intro"]
fx.add(HIT - 2.2, reverse_cymbal(2.2) * 0.35, send=0.3)
fx.add(HIT - 3.2, shepard(3.2, base=55, rate=0.9) * 0.4, send=0.4)
fx.add(HIT - 3.0, noise_riser(3.0) * 0.18, send=0.4)
bl, br = braam(5.5)
mus.add(HIT, bl * 0.8, br * 0.8, send=0.5)
drm.add(HIT, boom(4.0) * 1.0, send=0.35)
drm.add(HIT, taiko(1.0, big=True) * 0.8, send=0.5)
fx.add(HIT, crash(3.5) * 0.12, send=0.5)

# Chord progression for the product run: Dm–Bb–F–C, two bars each, voiced for strings.
PROG_A = [[50, 57, 62, 65, 69], [46, 53, 58, 62, 65], [41, 53, 57, 60, 65], [48, 55, 60, 64, 67]]
ROOTS_A = [38, 34, 41, 36]
# Gates: Dm–Bb–C–C, pushing to F.
PROG_B = [[50, 57, 62, 65, 69], [46, 53, 58, 62, 65], [48, 55, 60, 64, 67], [48, 55, 60, 64, 67]]
ROOTS_B = [38, 34, 36, 36]
# Resolution: F–C/E–Dm–Bb, high and wide.
PROG_C = [[53, 60, 65, 69, 72, 77], [52, 60, 64, 67, 72, 76], [50, 57, 62, 65, 69, 74], [46, 58, 62, 65, 70, 74]]
ROOTS_C = [41, 40, 38, 34]


def strings(chords, t0, t1, bars_per=2, cutoff=2200, gain=1.0, attack=1.2):
    t = t0
    k = 0
    while t < t1:
        dur = min(bars_per * BAR, t1 - t)
        n = int((dur + 2.0) * SR)
        L = np.zeros(n)
        R = np.zeros(n)
        for note in chords[k % len(chords)]:
            l, r = supersaw(midi(note), n, voices=7, cents=16)
            L += l
            R += r
        env = adsr(n, attack, 0.9, hold=dur)
        L = lowpass(L, cutoff) * env * gain
        R = lowpass(R, cutoff) * env * gain
        mus.add(t, L, R, send=0.55)
        t += bars_per * BAR
        k += 1


def ostinato(roots, t0, t1, gain_curve, bars_per=2, octave=True):
    pat = [0, 0, 12, 0, 0, 7, 0, 12, 0, 0, 12, 0, 3, 0, 7, 0]
    t = t0
    step = BEAT / 4
    i = 0
    while t < t1:
        chord_idx = int((t - t0) // (bars_per * BAR))
        r = roots[chord_idx % len(roots)]
        g = gain_curve(t)
        accent = 1.0 if i % 4 == 0 else 0.7
        s = spiccato(r + pat[i % 16], g * accent)
        mus.add(t, s, s, send=0.18, pan=0.42)
        if octave:
            s2 = spiccato(r + 12 + pat[i % 16], 0.45 * g * accent)
            mus.add(t + 0.006, s2, s2, send=0.2, pan=0.6)
        t += step
        i += 1


def drums(t0, t1, density, gain):
    """Taiko pattern; density 1 = beats 1 and 3, 2 = every beat, 3 = adds eighths."""
    t = t0
    i = 0
    while t < t1:
        d = density(t)
        g = gain(t)
        beat_in_bar = i % 8  # eighths
        hit = beat_in_bar in (0, 4) or (d >= 2 and beat_in_bar % 2 == 0) or (d >= 3 and beat_in_bar in (3, 7))
        if hit and g > 0.01:
            v = (1.0 if beat_in_bar == 0 else 0.7) * g
            drm.add(t, taiko(v), send=0.45, pan=0.5 + (0.12 if beat_in_bar % 4 == 2 else 0))
        t += BEAT / 2
        i += 1


# Product run: questions → end of queue.
A0 = grid(S["questions"] - 0.2, BAR)
A1 = S["drift"]
# Bridge: a low Dm string chord holds the space between the braam and the ostinato.
strings([[38, 50, 57, 62, 65]], HIT + 0.4, A0, bars_per=8, cutoff=1500, gain=0.5, attack=1.8)
strings(PROG_A, A0, A1, cutoff=2000, gain=0.55)
ost_gain_a = lambda t: np.interp(t, [A0, A0 + 4, S["v1"], A1 - 1, A1], [0.15, 0.45, 0.75, 0.85, 0.0])
ostinato(ROOTS_A, A0, A1 - 0.1, ost_gain_a)
drums(grid(S["protect"], BAR), A1 - 0.2,
      density=lambda t: 1 if t < V["v1"] else (2 if t < S["queue"] else 3),
      gain=lambda t: np.interp(t, [S["protect"], S["holdout"], V["v1"], A1 - 0.5], [0.35, 0.5, 0.8, 0.9]))
# Soft impacts: sealing the holdout, and v1 landing.
for at, g in ((S["holdout"] + 0.2, 0.55), (V["v1"], 0.7)):
    drm.add(at, boom(3.0, 50, 30) * g, send=0.4)
    fx.add(at, crash(2.5) * 0.06 * g, send=0.5)

# Drift: the pulse drops out; a minor-second cluster trembles; a filtered riser into the solvers.
D0, D1 = S["drift"], S["solvers"]
n = int((D1 - D0 + 1.5) * SR)
tt = np.arange(n) / SR
cl_L = np.zeros(n)
cl_R = np.zeros(n)
for note in (50, 51, 57, 58):
    l, r = supersaw(midi(note), n, voices=5, cents=10)
    cl_L += l
    cl_R += r
trem = 0.75 + 0.25 * np.sin(2 * np.pi * 6.0 * tt)
cl_env = adsr(n, 1.5, 0.6, hold=D1 - D0) * trem
mus.add(D0, lowpass(cl_L, 1300) * cl_env * 0.32, lowpass(cl_R, 1300) * cl_env * 0.32, send=0.6)
drm.add(D0 + 0.05, boom(3.0, 45, 26) * 0.6, send=0.4)
fx.add(D1 - 4.0, noise_riser(4.0) * 0.16, send=0.4)
fx.add(D1 - 1.6, reverse_cymbal(1.6) * 0.25, send=0.3)

# Solvers → gates: the pulse returns and builds; a hit on each gate; a Shepard riser across the gates.
B0 = grid(D1 - 0.1, BAR)
B1 = V["v2"]
strings(PROG_B, B0, B1, cutoff=2600, gain=0.6, attack=0.8)
ost_gain_b = lambda t: np.interp(t, [B0, S["gates"], B1 - 0.3, B1], [0.4, 0.75, 1.0, 0.0])
ostinato(ROOTS_B, B0, B1 - 0.05, ost_gain_b)
drums(B0, B1 - 0.1,
      density=lambda t: 2 if t < S["gates"] else 3,
      gain=lambda t: np.interp(t, [B0, S["gates"], B1], [0.55, 0.8, 1.0]))
g = scenes["gates"]
# The five gates tick off on screen at these times (src/scenes.tsx GATE_TICKS uses the same spacing).
gate_hits = [V["gates"] + 0.9 + 0.45 * i for i in range(5)]
for i, at in enumerate(gate_hits):
    drm.add(at, taiko(0.9 + 0.05 * i) * 0.9, send=0.5)
    drm.add(at, tick(1600 + 200 * i, 0.35), send=0.4, pan=0.45)
    fx.add(at, crash(1.2) * 0.03, send=0.4)
G0 = V["gates"] - 0.5
fx.add(G0, shepard(B1 - G0, base=110, rate=0.35) * 0.32, send=0.45)
fx.add(B1 - 2.4, reverse_cymbal(2.4) * 0.4, send=0.3)
fx.add(B1 - 2.0, noise_riser(2.0) * 0.2, send=0.3)

# v2: impact and the resolution to F major.
HIT2 = V["v2"]
bl, br = braam(5.0, notes=(29, 41, 48, 53), bright=2600)
mus.add(HIT2, bl * 0.4, br * 0.4, send=0.5)
drm.add(HIT2, boom(4.5, 58, 28) * 1.0, send=0.4)
drm.add(HIT2, taiko(1.0, big=True), send=0.6)
fx.add(HIT2, crash(4.0) * 0.16, send=0.6)
C0 = HIT2
C1 = S["trust"] + 0.3
strings(PROG_C, C0, C1, bars_per=1, cutoff=3400, gain=0.62, attack=0.5)
ostinato(ROOTS_C, grid(C0, BEAT / 4), S["trust"] - 0.2,
         lambda t: np.interp(t, [C0, S["trust"] - 1.0, S["trust"]], [0.9, 0.8, 0.0]), bars_per=1)
drums(grid(C0 + BEAT / 2, BEAT / 2), S["trust"] - 0.3, density=lambda t: 2, gain=lambda t: 0.75)
# Soaring top line over the resolution.
for i, note in enumerate([77, 79, 81, 84]):
    n = int(3.0 * SR)
    l, r = supersaw(midi(note), n, voices=5, cents=8)
    env = adsr(n, 0.6, 0.8, hold=1.6)
    mus.add(HIT2 + 0.4 + i * BAR / 2.2, lowpass(l, 3800) * env * 0.12, lowpass(r, 3800) * env * 0.12, send=0.7)

# Trust → close: piano motif over the drone, a last boom, the long tail.
close_motif = [(0.0, 69), (BEAT, 67), (2 * BEAT, 65), (3 * BEAT, 64), (5 * BEAT, 62), (7 * BEAT, 65)]
T0 = S["trust"] + 0.3
for dt, note in close_motif:
    p = piano(note, 6.0, 0.32)
    mus.add(T0 + dt, p, p, send=0.6, pan=0.45)
CL = V["close"]
drm.add(CL, boom(5.0, 50, 26) * 0.55, send=0.55)
fx.add(CL - 1.8, reverse_cymbal(1.8) * 0.25, send=0.3)
for note, at in ((53, 0.0), (57, 0.05), (60, 0.1), (65, 0.15), (41, 0.0)):  # F major over the D drone
    p = piano(note, 7.5, 0.2)
    mus.add(CL + at, p, p, send=0.7, pan=0.5)
n = int((END - CL + 1) * SR)
l, r = supersaw(midi(65), n, voices=7, cents=12)
env = adsr(n, 1.5, 1.2, hold=END - CL - 2.0)
mus.add(CL, lowpass(l, 2000) * env * 0.05, lowpass(r, 2000) * env * 0.05, send=0.8)

# ---------------------------------------------------------------- mix

def stem(bus, gain, wet=1.0):
    wl, wr = reverb(bus.sL, bus.sR)
    return (bus.L + wet * wl) * gain, (bus.R + wet * wr) * gain


ML, MR = stem(mus, 1.0)
DL, DR = stem(drm, 0.9)
FL, FR = stem(fx, 0.8)
L = ML + DL + FL
R = MR + DR + FR
master = curve([(0, 0), (0.3, 1), (END - 1.5, 1), (TOTAL - 0.05, 0), (TOTAL, 0)])
L, R = highpass(L, 28) * master, highpass(R, 28) * master
L, R = lowpass(L, 11000), lowpass(R, 11000)
L -= L.mean()
R -= R.mean()
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
drive = 1.6
L = np.tanh(L / peak * drive) / np.tanh(drive)
R = np.tanh(R / peak * drive) / np.tanh(drive)
out = np.stack([L, R], axis=1) * 0.89  # about -1 dBFS
wavfile.write(ROOT / "public" / "music.wav", SR, (out * 32767).astype(np.int16))


# ---------------------------------------------------------------- sound effects

def write(name, l, r=None):
    r = l if r is None else r
    st = np.stack([l, r], 1)
    st -= st.mean(0)
    st = st / max(1e-9, np.max(np.abs(st))) * 0.708  # -3 dBFS
    fade = int(0.004 * SR)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    out = ROOT / "public" / "sfx"
    out.mkdir(exist_ok=True)
    wavfile.write(out / f"{name}.wav", SR, (st * 32767).astype(np.int16))


small_ir_l, small_ir_r = reverb_ir(1.2, 0.015, 5), reverb_ir(1.2, 0.015, 6)


def sweep(dur, peak_at, lo, hi, width):
    """Airy noise swept up then down, panning left to right."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-((t - peak_at) / width) ** 2)
    cut = lo + (hi - lo) * env
    x = morph_lowpass(highpass(rng.standard_normal(n), 150), cut, bank=(200, 400, 800, 1600, 3200, 6400))
    pan = np.clip(t / dur, 0, 1)
    return x * env * np.sqrt(1 - pan), x * env * np.sqrt(pan)


l, r = sweep(0.8, 0.42, 300, 3800, 0.16)
wl, wr = reverb(l, r, small_ir_l, small_ir_r)
write("whoosh", l + 0.3 * wl, r + 0.3 * wr)

l, r = sweep(1.4, 0.95, 200, 4200, 0.32)
n = len(l)
tt = np.arange(n) / SR
swell = np.sin(2 * np.pi * np.cumsum(40 + 30 * tt / 1.4) / SR) * np.exp(-((tt - 0.95) / 0.3) ** 2) * 0.6
wl, wr = reverb(l + swell, r + swell, small_ir_l, small_ir_r)
write("whoosh_big", l + swell + 0.35 * wl, r + swell + 0.35 * wr)

b = boom(3.0)
c = crash(3.0) * 0.08
wl, wr = reverb(b + c, b + c)
write("impact", b + c + 0.35 * wl, b + c + 0.35 * wr)

n = int(2.0 * SR)
tt = np.arange(n) / SR
f = 28 + 62 * np.exp(-tt / 0.35)
sd = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.7) * np.minimum(1, tt / 0.005)
write("sub_drop", np.tanh(sd * 1.5))

rs = shepard(2.0, base=110, rate=1.2) * 0.6 + noise_riser(2.0) * 0.5
wl, wr = reverb(rs, rs, small_ir_l, small_ir_r)
write("riser", rs + 0.3 * wl, rs + 0.3 * wr)

write("tick", tick(2400, 1.0))

# Glitch: stuttered slices of crushed square and noise.
n = int(0.4 * SR)
gl = np.zeros(n)
gr = np.zeros(n)
pos = 0
while pos < n:
    seg = int(rng.integers(600, 3500))
    kind = rng.integers(0, 3)
    tt = np.arange(seg) / SR
    if kind == 0:
        s = np.sign(np.sin(2 * np.pi * rng.uniform(200, 1400) * tt))
    elif kind == 1:
        s = np.round(rng.standard_normal(seg) * 3) / 3
    else:
        s = np.zeros(seg)
    s = s[: n - pos] * rng.uniform(0.3, 1.0)
    gl[pos: pos + len(s)] += s
    gr[pos: pos + len(s)] += s * rng.uniform(0.3, 1.0)
    pos += seg
env = np.exp(-np.arange(n) / SR / 0.25)
write("glitch", lowpass(gl, 7000) * env, lowpass(gr, 7000) * env)

# Shimmer: a soft scatter of high bell partials.
n = int(1.6 * SR)
sl = np.zeros(n)
sr_ = np.zeros(n)
for i in range(14):
    at = rng.uniform(0, 0.6)
    note = rng.choice([84, 88, 89, 91, 93, 96])
    m = int((1.6 - at) * SR)
    tt = np.arange(m) / SR
    p = np.sin(2 * np.pi * midi(note) * tt) * np.exp(-tt / 0.35) * np.minimum(1, tt / 0.003) * rng.uniform(0.3, 1)
    pan = rng.random()
    k0 = int(at * SR)
    sl[k0: k0 + m] += p * np.sqrt(1 - pan)
    sr_[k0: k0 + m] += p * np.sqrt(pan)
wl, wr = reverb(sl, sr_, small_ir_l, small_ir_r)
write("shimmer", lowpass(sl + 0.6 * wl, 8000), lowpass(sr_ + 0.6 * wr, 8000))

n = int(0.06 * SR)
tt = np.arange(n) / SR
write("click", highpass(rng.standard_normal(n), 2000) * np.exp(-tt / 0.004) + 0.5 * np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.01))

# Names the previous cut used, kept so older scene code still finds a file.
n = int(0.25 * SR)
tt = np.arange(n) / SR
write("pop", np.sin(2 * np.pi * (520 + 380 * np.exp(-tt / 0.03)) * tt) * np.exp(-tt / 0.06))
write("chime", lowpass(sl + 0.6 * wl, 8000), lowpass(sr_ + 0.6 * wr, 8000))
write("alert", lowpass(gl, 4000) * env)

print(f"music {TOTAL:.1f}s, intro hit {HIT:.2f}s, v2 hit {HIT2:.2f}s, close boom {CL:.2f}s, gate hits "
      + ", ".join(f"{x:.2f}" for x in gate_hits))
