import type { ReactNode } from "react";
import { ArrowRight } from "./icons";
import { LogoMark } from "./Logo";

// The product's two entry points (frontend/lib/copy.ts: home.secondary / home.primary). Facts come from copy.ts
// and CONCOURS.md; "jump forward" exists only on the sample, since it is hidden on real projects.

const ICONS = {
  db: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  queue: "M4 6h16M4 12h16M4 18h10",
  gates: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3zM9 12l2 2 4-4",
  forward: "M5 5l7 7-7 7M13 5l7 7-7 7",
  plug: "M9 2v6M15 2v6M6 8h12v4a6 6 0 01-12 0V8zM12 18v4",
  columns: "M4 4h16v16H4zM10 4v16M16 4v16",
  shield: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3z",
  pulse: "M3 12h4l3-8 4 16 3-8h4",
  key: "M15 7a4 4 0 11-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0115 7zM16.5 8.5h.01",
} as const;

function Icon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-[18px] shrink-0 text-muted"
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

const MONO = { fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em" } as const;

/** Swinging circles settling on the last stop: from upload to today's queue. */
function PendulumArt() {
  const pivot = [466, 4];
  const bobs = [
    { x: 296, y: 55, stroke: "#3a3a40" },
    { x: 313, y: 112, stroke: "#3a3a40" },
    { x: 350, y: 156, stroke: "#4a4a50" },
    { x: 406, y: 178, stroke: "#5a5a60" },
    { x: 466, y: 187, stroke: "var(--foreground)" },
  ];
  const R = 24;
  return (
    <svg viewBox="0 0 539 232" className="block h-auto w-full" aria-hidden>
      <defs>
        <linearGradient id="two-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--card)" stopOpacity="0" />
          <stop offset="1" stopColor="var(--card)" stopOpacity="0.6" />
        </linearGradient>
      </defs>
      <rect width="539" height="232" fill="url(#two-fade)" />
      <path d="M104 0V232" stroke="var(--border-strong)" strokeDasharray="3 4" />
      <path d="M491 0V232M0 212H539" stroke="var(--border)" />
      {bobs.map((b, i) => {
        const dx = b.x - pivot[0];
        const dy = b.y - pivot[1];
        const len = Math.hypot(dx, dy);
        const ex = b.x - (dx / len) * R;
        const ey = b.y - (dy / len) * R;
        return (
          <g key={i}>
            <path d={`M${pivot[0]} ${pivot[1]}L${ex} ${ey}`} stroke={i === 4 ? "var(--subtle)" : "#4a4a50"} />
            <circle cx={b.x} cy={b.y} r={R} fill={i === 4 ? "var(--card-2)" : "none"} stroke={b.stroke} strokeWidth={i === 4 ? 1.5 : 1} />
          </g>
        );
      })}
      <circle cx={466} cy={187} r={4} fill="var(--c-pink)" className="anim-breathe" />
      <path d="M104 79H296" stroke="var(--border-strong)" strokeDasharray="4 4" />
      <path d="M104 180H350" stroke="var(--border-strong)" strokeDasharray="4 4" />
      <circle cx={104} cy={79} r={3.5} fill="var(--foreground)" />
      <circle cx={296} cy={79} r={3.5} fill="var(--c-indigo)" />
      <circle cx={104} cy={180} r={3.5} fill="var(--c-peach)" />
      <circle cx={350} cy={180} r={3.5} fill="var(--foreground)" />
      <circle cx={104} cy={212} r={3.5} fill="var(--foreground)" />
      <circle cx={491} cy={212} r={3.5} fill="var(--foreground)" />
      <text x={40} y={83} fill="var(--muted)" style={MONO}>
        UPLOAD
      </text>
      <text x={28} y={184} fill="var(--muted)" style={MONO}>
        PROTECT
      </text>
      <text x={480} y={228} textAnchor="end" fill="var(--muted)" style={MONO}>
        QUEUE
      </text>
    </svg>
  );
}

/** Radial field of lines around the mark, with the four stages at the corners. */
function FieldArt() {
  const cx = 270;
  const cy = 116;
  const R = 100;
  const lines = [];
  for (let x = -96; x <= 96; x += 12) {
    const h = Math.sqrt(R * R - x * x);
    lines.push(<path key={x} d={`M${cx + x} ${cy - h}V${cy + h}`} stroke="#2e2e33" />);
  }
  const bars = [
    { x: -84, y1: -32, y2: -6, c: "var(--c-peach)" },
    { x: 84, y1: -8, y2: 18, c: "var(--c-pink)" },
    { x: 12, y1: -76, y2: -62, c: "var(--c-indigo)" },
    { x: -36, y1: 44, y2: 70, c: "var(--c-violet)" },
  ];
  return (
    <svg viewBox="0 0 539 232" className="block h-auto w-full" aria-hidden>
      {lines}
      {bars.map((b, i) => (
        <rect
          key={b.x}
          x={cx + b.x - 2}
          y={cy + b.y1}
          width={4}
          height={b.y2 - b.y1}
          rx={1}
          fill={b.c}
          className="anim-slide anim-box"
          style={{ animationDelay: `${i * -1.2}s` }}
        />
      ))}
      <circle cx={cx} cy={cy} r={38} fill="var(--card)" stroke="var(--border-strong)" />
      <LogoMark id="two-logo" x={cx - 13} y={cy - 18} width={26} height={34} overflow="visible" />
      <text x={110} y={34} fill="var(--muted)" style={MONO}>
        UPLOAD
      </text>
      <text x={430} y={34} textAnchor="end" fill="var(--muted)" style={MONO}>
        PROTECT
      </text>
      <text x={110} y={206} fill="var(--muted)" style={MONO}>
        QUEUE
      </text>
      <text x={430} y={206} textAnchor="end" fill="var(--muted)" style={MONO}>
        IMPROVE
      </text>
      {[
        [96, 30],
        [444, 30],
        [96, 202],
        [444, 202],
      ].map(([x, y]) => (
        <circle key={`${x}${y}`} cx={x} cy={y} r={3} fill="#3a3a40" />
      ))}
    </svg>
  );
}

/** Ring dots at the outer edges of the right-hand art, as in the reference. */
const RINGS =
  "bg-[radial-gradient(circle,transparent_2.5px,var(--border-strong)_2.5px,var(--border-strong)_3.5px,transparent_3.5px)] bg-[length:13px_13px]";

type Path = {
  title: string;
  body: string;
  items: { icon: keyof typeof ICONS; text: string }[];
  cta: string;
  primary: boolean;
  art: ReactNode;
};

const PATHS: Path[] = [
  {
    title: "Try it on the sample",
    body: "1.75 million simulated card payments over six months, 0.8% fraud. See the whole loop before you upload anything.",
    items: [
      { icon: "db", text: "Six months of simulated card payments, ready to go" },
      { icon: "queue", text: "A fraud model and today's queue in this sitting" },
      { icon: "gates", text: "Improvement rounds with all five gates" },
      { icon: "forward", text: "Jump forward to watch a new fraud pattern land" },
      { icon: "plug", text: "Nothing to upload, nothing to connect" },
    ],
    cta: "Try with sample data",
    primary: false,
    art: <PendulumArt />,
  },
  {
    title: "Start with your transactions",
    body: "Upload a CSV of payments with a fraud label and answer three questions. Your first model and queue come from your own data.",
    items: [
      { icon: "columns", text: "Columns suggested by name: ID, time, amount, customer, label" },
      { icon: "shield", text: "IDs hashed, card numbers dropped, leaks caught" },
      { icon: "queue", text: "A daily queue sized to your team's capacity" },
      { icon: "pulse", text: "Weekly health and drift checks" },
      { icon: "key", text: "Every promoted version and its code are yours" },
    ],
    cta: "Start with your transactions",
    primary: true,
    art: (
      <div className="relative">
        <div aria-hidden className={`absolute inset-y-4 left-0 w-[80px] ${RINGS} [mask-image:linear-gradient(90deg,#000,transparent)]`} />
        <div aria-hidden className={`absolute inset-y-4 right-0 w-[80px] ${RINGS} [mask-image:linear-gradient(270deg,#000,transparent)]`} />
        <FieldArt />
      </div>
    ),
  },
];

export function TwoWays() {
  return (
    <section aria-labelledby="start-title" id="contact" className="border-t border-border">
      <div className="px-4 pt-[110px] pb-[50px] text-center">
        <p className="inline-flex h-[29px] items-center gap-2.5 rounded-md border border-border-strong bg-card-2 px-3 font-mono text-[12.5px] leading-none tracking-[0.06em] text-subtle">
          <span className="bg-brand size-[7px] rounded-full" aria-hidden />
          TWO WAYS TO START
        </p>
        <h2 id="start-title" className="mt-5 text-[clamp(30px,3.4vw,40px)] leading-[1.15] font-semibold tracking-[-0.035em] text-balance">
          Try it on the sample, or start with your own.
        </h2>
        <p className="mx-auto mt-4 max-w-[580px] text-[16px] leading-[1.5] text-pretty text-subtle">
          Some teams want to see the loop first. Others have transactions ready today. Both run on the same engine.
        </p>
      </div>

      <div className="border-t border-border md:px-[54px]">
        <div className="grid border-border md:grid-cols-2 md:border-x">
          {PATHS.map((p, i) => (
            <div key={p.title} className={`flex flex-col ${i === 1 ? "border-t border-border md:border-t-0 md:border-l" : ""}`}>
              <div className="border-b border-border">{p.art}</div>
              <div className="flex flex-1 flex-col px-5 pt-9 pb-8 md:px-[31px]">
                <h3 className="text-[24px] font-semibold tracking-[-0.025em]">{p.title}</h3>
                <p className="mt-2.5 text-[15.5px] leading-[1.5] text-subtle">{p.body}</p>
                <p className="text-gradient mt-9 w-fit font-mono text-[13px] tracking-[0.08em]">[ INCLUDES ]</p>
                <ul className="mt-3 flex-1">
                  {p.items.map((it) => (
                    <li key={it.text} className="flex items-center gap-3 py-[13px] text-[15.5px]">
                      <Icon name={it.icon} />
                      {it.text}
                    </li>
                  ))}
                </ul>
                <a
                  href="#contact"
                  className={`mt-5 inline-flex h-[46px] w-full items-center justify-center gap-2 rounded-xl text-[15.5px] font-medium transition-[background-color,filter,transform] duration-150 active:scale-[0.98] ${
                    p.primary
                      ? "bg-brand-x font-semibold text-accent-ink hover:brightness-110"
                      : "border border-border-strong bg-card-2 text-foreground hover:bg-card-3"
                  }`}
                >
                  {p.cta}
                  <ArrowRight className="size-4" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="h-[60px] border-t border-border" aria-hidden />
    </section>
  );
}
