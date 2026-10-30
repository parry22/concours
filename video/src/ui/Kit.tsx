import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, clamp01, GRAD, IN, keys, MONO, OUT, prog, SANS } from "../lib";

// UI pieces in the reference's language: white cards, light grey rows, thin borders, a soft long shadow,
// one accent. Content and copy come from the Concours product.

export const SHADOW = "0 1px 2px rgba(16,16,24,0.04), 0 30px 80px -20px rgba(16,16,24,0.18)";

// Arrives out of a blur and a short rise; leaves the same way.
export const Enter: React.FC<{ at: number; exit?: number; y?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at, exit, y = 30, children, style }) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 20, OUT);
  const out = exit !== undefined ? prog(f, exit, exit + 14, IN) : 0;
  if (f < at - 1 || out >= 1) return null;
  return (
    <div style={{ opacity: clamp01(p * 1.3) * (1 - out), transform: `translateY(${(1 - p) * y - out * 16}px)`, filter: p < 1 || out > 0 ? `blur(${(1 - p) * 8 + out * 8}px)` : undefined, ...style }}>
      {children}
    </div>
  );
};

export const Surface: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ background: C.card, borderRadius: 22, border: `1px solid ${C.border}`, boxShadow: SHADOW, fontFamily: SANS, color: C.fg, ...style }}>{children}</div>
);

export const Row: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ background: C.row, borderRadius: 14, display: "flex", alignItems: "center", ...style }}>{children}</div>
);

type Tone = "ok" | "warn" | "danger" | "neutral";
const TONES: Record<Tone, { bg: string; fg: string }> = {
  ok: { bg: C.okBg, fg: C.ink },
  warn: { bg: C.warnBg, fg: C.warn },
  danger: { bg: C.dangerBg, fg: C.danger },
  neutral: { bg: C.row, fg: C.subtle },
};
export const Badge: React.FC<{ tone?: Tone; children: React.ReactNode; size?: number; dot?: boolean; style?: React.CSSProperties }> = ({ tone = "ok", children, size = 22, dot = true, style }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: size * 0.4, background: TONES[tone].bg, color: TONES[tone].fg, borderRadius: 999,
    padding: `${size * 0.28}px ${size * 0.7}px`, fontSize: size, fontWeight: 500, fontFamily: SANS, whiteSpace: "nowrap", ...style }}>
    {dot && <span style={{ width: size * 0.34, height: size * 0.34, borderRadius: 9, background: TONES[tone].fg }} />}
    {children}
  </span>
);

// Square checkbox like the reference's task lists, in the Concours gradient.
export const CheckBox: React.FC<{ at: number; size?: number }> = ({ at, size = 30 }) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 10, OUT);
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0, borderRadius: size * 0.24, border: p < 1 ? `2px solid #d4d4d8` : "none", background: "#fff" }}>
      <div style={{ position: "absolute", inset: p < 1 ? -2 : 0, borderRadius: size * 0.24, background: GRAD, opacity: p, transform: `scale(${0.6 + 0.4 * p})` }} />
      <svg width={size} height={size} viewBox="0 0 24 24" style={{ position: "absolute", left: p < 1 ? -2 : 0, top: p < 1 ? -2 : 0 }}>
        <path d="M6 12.5l4 4 8-9" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={20}
          strokeDashoffset={20 * (1 - prog(f, at + 3, at + 13, OUT))} />
      </svg>
    </div>
  );
};

export const Spinner: React.FC<{ size?: number }> = ({ size = 26 }) => {
  const f = useCurrentFrame();
  return <div style={{ width: size, height: size, borderRadius: 99, border: `2.5px solid #e4e4e7`, borderTopColor: C.violet, transform: `rotate(${f * 14}deg)`, flexShrink: 0 }} />;
};

export const Button: React.FC<{ children: React.ReactNode; press?: number; size?: number; style?: React.CSSProperties }> = ({ children, press, size = 26, style }) => {
  const f = useCurrentFrame();
  const down = press !== undefined && f >= press - 2 && f < press + 5 ? 0.94 : 1;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: GRAD, color: "#fff", borderRadius: 14, padding: `${size * 0.55}px ${size * 1.1}px`,
      fontSize: size, fontWeight: 600, fontFamily: SANS, transform: `scale(${down})`, boxShadow: "0 10px 30px -10px rgba(168,85,247,0.6)", whiteSpace: "nowrap", ...style }}>
      {children}
    </div>
  );
};

// Text typed into a field, with a caret that blinks while idle.
export const Typing: React.FC<{ text: string; at: number; cps?: number; style?: React.CSSProperties; caretUntil?: number }> = ({ text, at, cps = 1.6, style, caretUntil }) => {
  const f = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor((f - at) * cps)));
  const showCaret = (caretUntil === undefined || f < caretUntil) && (n < text.length || Math.floor(f / 15) % 2 === 0);
  return (
    <span style={style}>
      {text.slice(0, n)}
      {showCaret && <span style={{ display: "inline-block", width: 3, height: "1.05em", background: C.violet, marginLeft: 2, verticalAlign: "-0.15em" }} />}
    </span>
  );
};

export const CountUp: React.FC<{ from?: number; to: number; at: number; dur?: number; prefix?: string; style?: React.CSSProperties }> = ({ from = 0, to, at, dur = 26, prefix = "$", style }) => {
  const f = useCurrentFrame();
  const v = interpolate(f, [at, at + dur], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: OUT });
  return <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>{prefix}{Math.round(v).toLocaleString("en-US")}</span>;
};

export const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => <span style={{ fontFamily: MONO, ...style }}>{children}</span>;

// A camera over the stage: pan, zoom and a little tilt, all on one ease. Values are keyframed by frame.
type Cam = { f: number; x?: number; y?: number; z?: number; rx?: number; ry?: number };
export const Stage: React.FC<{ cam: Cam[]; children: React.ReactNode }> = ({ cam, children }) => {
  const f = useCurrentFrame();
  const v = (k: "x" | "y" | "z" | "rx" | "ry", d: number) => keys(f, cam.map((c) => [c.f, c[k] ?? d] as [number, number]));
  // The point (x, y) in stage coordinates is brought to the centre of the frame and scaled by z.
  const x = v("x", 960);
  const y = v("y", 540);
  const z = v("z", 1);
  return (
    <div style={{ position: "absolute", inset: 0, perspective: 2400 }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, transformOrigin: `${x}px ${y}px`,
        transform: `translate(${960 - x}px, ${540 - y}px) scale(${z}) rotateX(${v("rx", 0)}deg) rotateY(${v("ry", 0)}deg)` }}>
        {children}
      </div>
    </div>
  );
};

// The reference's pointing-hand cursor. It glides on the long ease and presses on click frames.
export const Hand: React.FC<{ path: { f: number; x: number; y: number }[]; clicks?: number[]; show: number; hide?: number }> = ({ path, clicks = [], show, hide }) => {
  const f = useCurrentFrame();
  const op = prog(f, show, show + 8) * (hide !== undefined ? 1 - prog(f, hide, hide + 8) : 1);
  if (op <= 0) return null;
  const x = keys(f, path.map((p) => [p.f, p.x]));
  const y = keys(f, path.map((p) => [p.f, p.y]));
  const press = clicks.reduce((m, c) => Math.max(m, f >= c - 3 && f < c + 6 ? 1 - Math.abs(f - c) / 6 : 0), 0);
  return (
    <div style={{ position: "absolute", left: x - 14, top: y - 4, opacity: op, zIndex: 50, transform: `scale(${1 - press * 0.12})`, transformOrigin: "14px 4px" }}>
      <svg width={52} height={58} viewBox="0 0 26 29" style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.25))" }}>
        <path d="M9.2 2.2c1 0 1.8.8 1.8 1.8v8.1l.6-.1V9.6c0-1 .8-1.8 1.8-1.8s1.8.8 1.8 1.8v2.3l.6-.1v-1.4c0-1 .8-1.8 1.8-1.8s1.8.8 1.8 1.8v1.9l.5-.1c0-.9.8-1.6 1.7-1.6 1 0 1.8.8 1.8 1.8v5.9c0 4.6-3 8.2-7.6 8.2h-1.6c-2.4 0-4.3-1-5.8-3.1L3.1 17.6c-.6-.8-.4-1.9.4-2.5.8-.6 1.9-.5 2.6.2l1.3 1.4V4c0-1 .8-1.8 1.8-1.8z"
          fill="#fff" stroke="#111" strokeWidth={1.3} strokeLinejoin="round" />
        <path d="M11 15.5v4.5M14.8 15.5v4.5M18.6 15.5v4.5" stroke="#111" strokeWidth={1.1} strokeLinecap="round" />
      </svg>
    </div>
  );
};

// One step of a progress checklist: spinner while working, checkbox when done, row brightens.
export const Step: React.FC<{ done: number; children: React.ReactNode; sub?: React.ReactNode; size?: number }> = ({ done, children, sub, size = 30 }) => {
  const f = useCurrentFrame();
  const ok = f >= done;
  return (
    <Row style={{ gap: 20, padding: "20px 24px", alignItems: "flex-start" }}>
      <div style={{ paddingTop: 2 }}>{ok ? <CheckBox at={done} size={size} /> : <Spinner size={size} />}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: size * 0.95, color: ok ? C.fg : C.subtle, fontWeight: 500 }}>{children}</div>
        {sub}
      </div>
    </Row>
  );
};
