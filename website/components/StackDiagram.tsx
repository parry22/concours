import type { CSSProperties } from "react";
import { LogoMark } from "./Logo";

// Isometric layer stack from the reference hero, in the product's colours: a dashed ghost slab, the Concours slab
// (brand gradient, with the mark standing on it), the customer's stack (grey cylinder tone) and two plain data slabs, with labelled inputs on the left and outputs on the right.
// All coordinates are CSS pixels at desktop size; x = 0 is the centre of the stack.

const HW = 139; // half width of a slab's top face
const HH = 76; // half height of a slab's top face
const T = 27; // slab thickness
const K = HH / HW;
const R_SIDE = 10; // corner radius at the left and right vertices
const R_TIP = 22; // corner radius at the back and front vertices

type Pt = [number, number];

function roundedPath(pts: Pt[], radii: number[]) {
  const n = pts.length;
  let d = "";
  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const a = pts[(i - 1 + n) % n];
    const b = pts[(i + 1) % n];
    const r = radii[i];
    const la = Math.hypot(a[0] - p[0], a[1] - p[1]);
    const lb = Math.hypot(b[0] - p[0], b[1] - p[1]);
    const p1: Pt = [p[0] + ((a[0] - p[0]) / la) * r, p[1] + ((a[1] - p[1]) / la) * r];
    const p2: Pt = [p[0] + ((b[0] - p[0]) / lb) * r, p[1] + ((b[1] - p[1]) / lb) * r];
    d += `${i === 0 ? "M" : "L"}${p1[0]} ${p1[1]}Q${p[0]} ${p[1]} ${p2[0]} ${p2[1]}`;
  }
  return d + "Z";
}

/** Rounded rhombus whose back vertex is at (0, top). */
function face(top: number) {
  return roundedPath(
    [[0, top], [HW, top + HH], [0, top + 2 * HH], [-HW, top + HH]],
    [R_TIP, R_SIDE, R_TIP, R_SIDE],
  );
}

/** Front half of a face (left vertex, front vertex, right vertex), matching face()'s rounding. */
function frontEdge(top: number) {
  const inset = (R_SIDE * Math.cos(Math.atan(K))) / 2;
  const sideY = top + HH;
  const frontY = top + 2 * HH;
  const ux = HW / Math.hypot(HW, HH);
  const uy = HH / Math.hypot(HW, HH);
  return (
    `M${-HW + inset} ${sideY}` +
    `Q${-HW} ${sideY} ${-HW + ux * R_SIDE} ${sideY + uy * R_SIDE}` +
    `L${-ux * R_TIP} ${frontY - uy * R_TIP}` +
    `Q0 ${frontY} ${ux * R_TIP} ${frontY - uy * R_TIP}` +
    `L${HW - ux * R_SIDE} ${sideY + uy * R_SIDE}` +
    `Q${HW} ${sideY} ${HW - inset} ${sideY}`
  );
}

const SIDE_INSET = (R_SIDE * Math.cos(Math.atan(K))) / 2;

type SlabTone = { side: string; stroke: string; faceStroke?: string; stripes?: boolean };

function Slab({ top, tone, p }: { top: number; tone: SlabTone; p: string }) {
  const x = -HW + SIDE_INSET;
  const sides = (
    <>
      <path d={face(top + T)} />
      <rect x={x} y={top + HH} width={2 * (HW - SIDE_INSET)} height={T} />
    </>
  );
  return (
    <g>
      <g fill={tone.side}>{sides}</g>
      {tone.stripes && <g fill={`url(#${p}stripes)`}>{sides}</g>}
      <path d={frontEdge(top + T)} fill="none" stroke={tone.stroke} strokeWidth={1.1} />
      <path d={`M${x} ${top + HH}v${T}M${-x} ${top + HH}v${T}`} stroke={tone.stroke} strokeWidth={1.1} />
      <path d={face(top)} fill="var(--card)" stroke={tone.faceStroke ?? tone.stroke} strokeWidth={1.1} />
    </g>
  );
}

function Ghost({ top }: { top: number }) {
  const x = -HW;
  return (
    <g className="anim-float-slow" fill="none" stroke="#4a4a50" strokeWidth={1} strokeDasharray="2 4" strokeLinecap="round">
      <path d={face(top)} />
      <path d={frontEdge(top + T)} />
      <path d={`M${x} ${top + HH}v${T}M${-x} ${top + HH}v${T}`} />
    </g>
  );
}

// Pills: mono label, 36px tall. Width comes from the label so the text never touches the edge.
const PILL_H = 36;
const CHAR_W = 9.75; // Geist Mono at 15px with 0.05em tracking
const PILL_PAD = 15;

type Node = { label: string; y: number; tone: keyof typeof SQUARE };

const INPUTS: Node[] = [
  { label: "TRANSACTIONS", y: 166, tone: "grey" },
  { label: "YOUR STACK", y: 258, tone: "light" },
  { label: "LABELS", y: 349, tone: "grey" },
];

const OUTPUTS: Node[] = [
  { label: "REVIEW QUEUE", y: 211, tone: "brand" },
  { label: "NEW VERSIONS", y: 302, tone: "grey" },
];

// Inputs are grey, the customer's own stack is light, the highlighted output carries the brand.
const SQUARE = { grey: "var(--muted)", light: "var(--foreground)", brand: "var(--c-peach)" } as const;

function Pill({ node, side, delay, p }: { node: Node; side: "left" | "right"; delay: number; p: string }) {
  const w = node.label.length * CHAR_W + PILL_PAD * 2;
  const edge = side === "left" ? -293 : 281; // pill edge nearest the stack
  const x = side === "left" ? edge - w : edge;
  const sq = side === "left" ? -172 : 168;
  const lineFrom = side === "left" ? edge + 10 : sq + 10;
  const lineTo = side === "left" ? sq - 10 : edge - 6;
  const hot = node.tone === "brand";
  return (
    <g>
      <path
        d={`M${lineFrom} ${node.y}H${lineTo}`}
        stroke="#3a3a40"
        strokeWidth={1.4}
        strokeDasharray="0 6"
        className="anim-flow"
        strokeLinecap="round"
      />
      {/* A data packet travelling the connector: inputs flow into the stack, outputs flow out to their pill. */}
      <circle
        cx={lineFrom}
        cy={node.y}
        r={2.6}
        fill={side === "left" ? "var(--c-peach)" : "var(--c-orchid)"}
        className="anim-packet"
        style={{ "--d": `${lineTo - lineFrom}px`, animationDelay: `${delay}s` } as CSSProperties}
      />
      <rect x={sq - 4} y={node.y - 4} width={8} height={8} rx={1} fill={SQUARE[node.tone]} className={hot ? "anim-breathe" : undefined} />
      <rect
        x={x}
        y={node.y - PILL_H / 2}
        width={w}
        height={PILL_H}
        rx={PILL_H / 2}
        fill={hot ? `url(#${p}pill-brand)` : "var(--card-2)"}
        stroke={hot ? "none" : "var(--border-strong)"}
        filter={hot ? `url(#${p}pill-glow)` : undefined}
      />
      <text
        x={x + w / 2}
        y={node.y + 0.5}
        textAnchor="middle"
        dominantBaseline="central"
        fill={hot ? "var(--accent-ink)" : "var(--subtle)"}
        style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 500, letterSpacing: "0.05em" }}
      >
        {node.label}
      </text>
    </g>
  );
}

const STACK_TOP = 117; // back vertex of the Concours slab
const PITCH = 45; // distance between slabs
const ORBIT_CY = 255; // centre of the orbit ring, about the middle of the stack
const ORBIT_R = 250;

/** A flat ring around the stack with three dots circling it. Rotation happens in the ring's own plane, then the
 * plane is squashed to match the isometric view. The unpainted circle gives the group a box centred on 0,0. */
function Orbit() {
  const dots = [
    { a: 20, c: "var(--c-peach)" },
    { a: 150, c: "var(--c-pink)" },
    { a: 260, c: "var(--c-indigo)" },
  ];
  return (
    <g transform={`translate(0 ${ORBIT_CY}) scale(1 0.48)`} aria-hidden>
      <circle r={ORBIT_R} fill="none" stroke="var(--border-strong)" strokeDasharray="2 7" strokeLinecap="round" opacity={0.7} />
      <g className="anim-orbit anim-box">
        <circle r={ORBIT_R} fill="none" stroke="none" />
        {dots.map((d) => (
          <circle
            key={d.a}
            cx={ORBIT_R * Math.cos((d.a * Math.PI) / 180)}
            cy={ORBIT_R * Math.sin((d.a * Math.PI) / 180)}
            r={5}
            fill={d.c}
          />
        ))}
      </g>
    </g>
  );
}

/**
 * `compact` is the phone version: the view is cropped to the stack and its orbit and the side pills are left out
 * (the hero lists them as chips instead). Both versions are on the page at once, so each prefixes its gradient
 * ids; otherwise the hidden copy would own the gradients and the visible one would lose them.
 */
export function StackDiagram({ compact = false, className = "" }: { compact?: boolean; className?: string }) {
  const p = compact ? "sm-" : "";
  return (
    <svg
      viewBox={compact ? "-262 30 524 440" : "-450 0 900 500"}
      className={`relative mx-auto h-auto w-full ${compact ? "max-w-[520px]" : "max-w-[900px]"} ${className}`}
      role="img"
      aria-label="Transactions, your stack and labels flow into Concours, which returns a review queue and new model versions."
    >
      <defs>
        <linearGradient id={`${p}side-brand`} gradientUnits="userSpaceOnUse" x1="0" y1={STACK_TOP + HH} x2="0" y2={STACK_TOP + 2 * HH + T}>
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.34" stopColor="#f472b6" />
          <stop offset="0.66" stopColor="#c084fc" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <linearGradient id={`${p}edge-brand`} gradientUnits="userSpaceOnUse" x1={-HW} y1="0" x2={HW} y2="0">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.34" stopColor="#f472b6" />
          <stop offset="0.66" stopColor="#c084fc" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <linearGradient
          id={`${p}side-grey`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1={STACK_TOP + PITCH + HH}
          x2="0"
          y2={STACK_TOP + PITCH + 2 * HH + T}
        >
          <stop offset="0" stopColor="#4a4a4f" />
          <stop offset="1" stopColor="#2c2c30" />
        </linearGradient>
        <linearGradient id={`${p}pill-brand`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.34" stopColor="#f472b6" />
          <stop offset="0.66" stopColor="#c084fc" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <radialGradient id={`${p}mark-glow`}>
          <stop offset="0" stopColor="#fbb39c" stopOpacity="0.45" />
          <stop offset="1" stopColor="#f472b6" stopOpacity="0" />
        </radialGradient>
        <pattern id={`${p}stripes`} width="3" height="10" patternUnits="userSpaceOnUse">
          <rect width="1" height="10" fill="#fff" opacity="0.08" />
        </pattern>
        <filter id={`${p}pill-glow`} x="-30%" y="-60%" width="160%" height="220%">
          <feDropShadow dx="0" dy="2" stdDeviation="6" floodColor="#f472b6" floodOpacity="0.4" />
        </filter>
      </defs>

      <Orbit />
      {!compact && INPUTS.map((n, i) => (
        <Pill p={p} key={n.label} node={n} side="left" delay={i * -0.9} />
      ))}
      {!compact && OUTPUTS.map((n, i) => (
        <Pill p={p} key={n.label} node={n} side="right" delay={-0.5 + i * -1.3} />
      ))}

      {/* Rings spreading from the Concours slab, behind the stack. */}
      {[0, -1.8].map((d) => (
        <path
          key={d}
          d={face(STACK_TOP)}
          fill="none"
          stroke={`url(#${p}edge-brand)`}
          strokeWidth={1.2}
          className="anim-ring anim-box"
          style={{ animationDelay: `${d}s` }}
        />
      ))}

      <Slab p={p} top={STACK_TOP + 3 * PITCH} tone={{ side: "#0f0f11", stroke: "var(--border-strong)" }} />
      <Slab p={p} top={STACK_TOP + 2 * PITCH} tone={{ side: "#0f0f11", stroke: "var(--border-strong)" }} />
      <Slab p={p} top={STACK_TOP + PITCH} tone={{ side: `url(#${p}side-grey)`, stroke: "#3a3a40", stripes: true }} />
      {/* The Concours slab lifts gently off the stack, carrying its mark. */}
      <g className="anim-float-slow">
        <Slab
          p={p}
          top={STACK_TOP}
          tone={{ side: `url(#${p}side-brand)`, stroke: `url(#${p}edge-brand)`, faceStroke: `url(#${p}edge-brand)`, stripes: true }}
        />
        <ellipse cx="0" cy={STACK_TOP + HH} rx="58" ry="30" fill={`url(#${p}mark-glow)`} className="anim-breathe" />
        <g className="anim-float">
          <LogoMark id={`${p}stack-logo`} x={-22} y={STACK_TOP + HH - 49} width={44} height={56} overflow="visible" />
        </g>
      </g>
      <Ghost top={STACK_TOP - 47} />
    </svg>
  );
}
