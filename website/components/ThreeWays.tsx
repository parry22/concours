import type { ReactNode } from "react";
import { ArrowRight } from "./icons";
import { LogoMark } from "./Logo";

// "One model, three ways it stays ahead": the review queue, the improvement network and drift health, laid out as
// in the reference (two blocks, a figure row, a wide dashboard block). Reasons, statuses, gate and drift terms are
// the product's own (backend/app/fraud/reasons.py, CONCOURS.md). Figures are the Marketplace payments sample
// project (workspace/concours.db): v1 $4,685, v2 $4,840, v3 $6,543 caught per day. Queue amounts and weekly bars
// are example values inside mocks.

const ICONS = {
  check: "M20 6L9 17l-5-5",
  card: "M3 6h18v12H3zM3 10h18",
  terminal: "M5 3h14v18H5zM9 7h6M9 11h6M9 15h2",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  globe: "M12 21a9 9 0 100-18 9 9 0 000 18zM3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18",
  cpu: "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4",
  lock: "M7 11V8a5 5 0 0110 0v3M6 11h12v10H6z",
  branch: "M6 3v12M6 15a3 3 0 100 6 3 3 0 000-6zM18 9a3 3 0 100-6 3 3 0 000 6zM18 9c0 6-12 3-12 6",
  scale: "M12 3v18M5 7h14M5 7l-3 7a3 3 0 006 0L5 7zM19 7l-3 7a3 3 0 006 0l-3-7z",
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
  calendar: "M5 5h14v15H5zM5 9h14M9 3v4M15 3v4",
  radar: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 12l6-6M12 16a4 4 0 100-8",
} as const;

function Icon({ name, className = "size-4" }: { name: keyof typeof ICONS; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

function BlockHead({ tag, title, children }: { tag: string; title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-[430px] text-center">
      <p className="font-mono text-[13px] tracking-[0.08em] text-muted">[ {tag} ]</p>
      <h3 className="mt-3 text-[24px] font-semibold tracking-[-0.025em] text-balance">{title}</h3>
      <p className="mt-3 text-[15.5px] leading-[1.55] text-pretty text-muted">{children}</p>
    </div>
  );
}

function Chip({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "brand" }) {
  return (
    <span
      className={`inline-flex h-6 shrink-0 items-center gap-1 rounded-full px-2 text-[11.5px] font-medium whitespace-nowrap ${
        tone === "brand" ? "bg-brand text-accent-ink" : "border border-border-strong text-subtle"
      }`}
    >
      {tone === "plain" && <Icon name="check" className="size-3" />}
      {children}
    </span>
  );
}

/* --- Block 1: the queue ------------------------------------------------------------------------------------ */

const CASES = [
  { amount: "$2,140.00", reason: "Card-testing burst at this terminal", icon: "terminal", chip: "case #1" },
  { amount: "$864.50", reason: "First payment at this terminal for this card", icon: "card", chip: "in queue" },
  { amount: "$412.99", reason: "Customer had recent fraud", icon: "user", chip: "in queue" },
] as const;

/** Ring dots at the sides of the queue stack, as in the reference. */
const RINGS =
  "bg-[radial-gradient(circle,transparent_2px,var(--border-strong)_2px,var(--border-strong)_3px,transparent_3px)] bg-[length:12px_12px]";

function QueueStack() {
  return (
    <div className="relative mx-auto mt-8 w-full max-w-[400px]">
      <div
        aria-hidden
        className={`absolute inset-y-10 -inset-x-20 ${RINGS} [mask-image:linear-gradient(90deg,#000_0%,transparent_25%,transparent_75%,#000_100%)]`}
      />
      <div className="relative mx-1 flex h-10 items-center justify-between rounded-t-xl border border-b-0 border-border bg-card px-4 font-mono text-[12.5px] tracking-[0.06em] text-muted">
        PAYMENT → CASE
        <Chip tone="brand">TODAY</Chip>
      </div>
      <ul className="relative space-y-2.5">
        {CASES.map((c, i) => (
          <li
            key={c.amount}
            className="flex items-center gap-3 rounded-xl border border-border-strong bg-card-2 p-3 shadow-[0_8px_20px_-12px_rgb(0_0_0/0.8)]"
          >
            <span
              className={`grid size-10 shrink-0 place-items-center rounded-lg ${i === 0 ? "bg-brand text-accent-ink" : "border border-border-strong bg-card-3 text-subtle"}`}
            >
              <Icon name={c.icon} className="size-[18px]" />
            </span>
            <span className="min-w-0 flex-1 text-left">
              <span className="block font-mono text-[14px] tabular-nums">{c.amount}</span>
              <span className="block text-[12.5px] leading-snug text-muted">{c.reason}</span>
            </span>
            <Chip>{c.chip}</Chip>
          </li>
        ))}
      </ul>
      <div className="relative mx-1 flex h-10 items-center justify-between rounded-b-xl border border-t-0 border-border bg-card px-4 font-mono text-[12.5px] tracking-[0.06em] text-muted">
        <span>CAPACITY</span>
        <span>200 CASES / DAY</span>
      </div>
    </div>
  );
}

/* --- Block 2: the network honeycomb -------------------------------------------------------------------- */

const HEX_R = 52; // pointy-top hexagon, centre to corner
const HEX_W = Math.sqrt(3) * HEX_R;

function hexPath(cx: number, cy: number, r: number, round = 9) {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  });
  let d = "";
  pts.forEach((p, i) => {
    const prev = pts[(i + 5) % 6];
    const next = pts[(i + 1) % 6];
    const f = round / r;
    const a = [p[0] + (prev[0] - p[0]) * f, p[1] + (prev[1] - p[1]) * f];
    const b = [p[0] + (next[0] - p[0]) * f, p[1] + (next[1] - p[1]) * f];
    d += `${i === 0 ? "M" : "L"}${a[0]} ${a[1]}Q${p[0]} ${p[1]} ${b[0]} ${b[1]}`;
  });
  return d + "Z";
}

// Neighbours of the centre: the solvers, the sealed holdout and the gates. Outer cells are faded filler.
const RING: { dx: number; dy: number; icon: keyof typeof ICONS; label: string }[] = [
  { dx: -0.5, dy: -1, icon: "user", label: "Solvers" },
  { dx: 0.5, dy: -1, icon: "globe", label: "Global network" },
  { dx: -1, dy: 0, icon: "lock", label: "Sealed holdout" },
  { dx: 1, dy: 0, icon: "scale", label: "Five gates" },
  { dx: -0.5, dy: 1, icon: "cpu", label: "Scored runs" },
  { dx: 0.5, dy: 1, icon: "branch", label: "New versions" },
];
const OUTER = [
  [-1.5, -1], [1.5, -1], [-2, 0], [2, 0], [-1.5, 1], [1.5, 1],
];

function Honeycomb() {
  const W = 480;
  const H = 330;
  const cx = W / 2;
  const cy = H / 2;
  const dy = HEX_R * 1.5 + 4;
  const dx = HEX_W + 4;
  return (
    <div className="relative mt-6">
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(var(--border-strong)_1px,transparent_1px)] bg-[length:10px_10px] [mask-image:radial-gradient(closest-side,transparent_40%,#000_100%)]"
      />
      <svg viewBox={`0 0 ${W} ${H}`} className="relative mx-auto block h-auto w-full max-w-[480px]" role="img" aria-label="Concours at the centre of a network of solvers, a sealed holdout and five gates">
        <defs>
          <linearGradient id="hex-brand" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fbb39c" />
            <stop offset="0.34" stopColor="#f472b6" />
            <stop offset="0.66" stopColor="#c084fc" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
          <radialGradient id="hex-glow">
            <stop offset="0" stopColor="#f472b6" stopOpacity="0.35" />
            <stop offset="1" stopColor="#818cf8" stopOpacity="0" />
          </radialGradient>
        </defs>
        {OUTER.map(([x, y]) => (
          <path key={`${x}${y}`} d={hexPath(cx + x * dx, cy + y * dy, HEX_R)} fill="var(--card)" opacity="0.55" />
        ))}
        {RING.map((n) => (
          <g key={n.label}>
            <title>{n.label}</title>
            <path
              d={hexPath(cx + n.dx * dx, cy + n.dy * dy, HEX_R)}
              fill="var(--card-2)"
              stroke="var(--border-strong)"
            />
            <g transform={`translate(${cx + n.dx * dx - 13} ${cy + n.dy * dy - 13}) scale(1.08)`} className="text-subtle">
              <path
                d={ICONS[n.icon]}
                fill="none"
                stroke="currentColor"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
          </g>
        ))}
        <circle cx={cx} cy={cy} r={HEX_R * 1.6} fill="url(#hex-glow)" className="anim-breathe" />
        <path d={hexPath(cx, cy, HEX_R + 2)} fill="var(--card)" stroke="url(#hex-brand)" strokeWidth={1.6} />
        <LogoMark id="hex-logo" x={cx - 17} y={cy - 22} width={34} height={44} overflow="visible" />
      </svg>
    </div>
  );
}

/* --- Block 3: the health dashboard --------------------------------------------------------------------- */

// Example weekly shape: steady, a dip when a new pattern lands, recovery after the next version.
const WEEKS = [
  { label: "W1", h: 62 },
  { label: "W2", h: 66 },
  { label: "W3", h: 64 },
  { label: "W4", h: 44 },
  { label: "W5", h: 70 },
  { label: "W6", h: 92 },
];

const DRIFT = [
  { name: "Amount", state: "stable" },
  { name: "Hour of day", state: "stable" },
  { name: "Payments per terminal", state: "PSI over 0.2" },
];

function HealthDashboard() {
  return (
    <div className="mx-auto mt-10 w-full max-w-[888px] rounded-2xl border border-border bg-card/60 p-[7px] pt-0">
      <div className="flex h-9 items-center gap-1.5 px-3" aria-hidden>
        <span className="size-2 rounded-full bg-card-3" />
        <span className="size-2 rounded-full bg-card-3" />
        <span className="size-2 rounded-full bg-card-3" />
      </div>
      <div className="overflow-hidden rounded-xl border border-border-strong bg-card text-left">
        <div className="flex h-[58px] items-center justify-between border-b border-border px-5">
          <span className="flex items-center gap-2.5 text-[15px] font-semibold tracking-[-0.01em]">
            <LogoMark id="dash-logo" className="h-[20px] w-[16px] overflow-visible" />
            Model health
          </span>
          <span className="inline-flex h-[22px] items-center gap-1.5 rounded-md bg-[rgb(167_139_250/0.14)] px-2 text-[12px] font-medium text-[#c4b5fd]">
            <span className="bg-brand size-1.5 rounded-full" />
            Improving
          </span>
        </div>
        <div className="grid md:grid-cols-3">
          <div className="border-border p-5 md:border-r">
            <div className="flex items-center gap-2 text-[13px] text-subtle">
              <Icon name="trend" className="size-4" />
              Caught per day
            </div>
            <div className="text-gradient mt-4 text-[40px] leading-none font-semibold tracking-[-0.04em] tabular-nums">
              $6,543
            </div>
            <div className="mt-3 flex items-center gap-2 text-[12.5px] text-muted">
              <span className="inline-flex h-6 items-center rounded-md border border-border-strong px-2 font-medium text-foreground">
                ↑ v3
              </span>
              up from $4,840
            </div>
            <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-[13px]">
              <span className="text-muted">First model</span>
              <span className="font-mono tabular-nums">$4,685</span>
            </div>
          </div>
          <div className="border-t border-border p-5 md:border-t-0 md:border-r">
            <div className="flex items-center gap-2 text-[13px] text-subtle">
              <Icon name="calendar" className="size-4" />
              Caught by week
            </div>
            <div className="mt-5 flex h-[120px] items-end justify-between gap-2" aria-hidden>
              {WEEKS.map((w, i) => (
                <div key={w.label} className="flex h-full flex-1 flex-col justify-end">
                  <div
                    className={`anim-grow w-full rounded-t-[4px] ${
                      i === WEEKS.length - 1
                        ? "bg-brand"
                        : "bg-[linear-gradient(180deg,var(--card-3),transparent)]"
                    }`}
                    style={{ height: `${w.h}%`, animationDelay: `${i * 70}ms` }}
                  />
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between font-mono text-[11px] text-muted">
              {WEEKS.map((w) => (
                <span key={w.label} className="flex-1 text-center">
                  {w.label}
                </span>
              ))}
            </div>
          </div>
          <div className="border-t border-border p-5 md:border-t-0">
            <div className="flex items-center gap-2 text-[13px] text-subtle">
              <Icon name="radar" className="size-4" />
              Drift checks
            </div>
            <ul className="mt-4 space-y-2">
              {DRIFT.map((d) => {
                const shifted = d.state !== "stable";
                return (
                  <li
                    key={d.name}
                    className="flex h-10 items-center justify-between gap-2 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px]"
                  >
                    <span className="truncate">{d.name}</span>
                    <span className={`shrink-0 text-[11.5px] ${shifted ? "font-medium text-warn" : "text-muted"}`}>
                      {d.state}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- Section ------------------------------------------------------------------------------------------- */

export function ThreeWays() {
  return (
    <section aria-labelledby="ways-title" id="review-queue" className="border-t border-border">
      <div className="px-4 pt-[50px] pb-[50px] text-center">
        <p className="inline-flex h-[29px] items-center gap-2.5 rounded-md border border-border-strong bg-card-2 px-3 font-mono text-[11px] leading-none tracking-[0.05em] whitespace-nowrap text-subtle sm:text-[12.5px] sm:tracking-[0.06em]">
          <span className="bg-brand size-[7px] rounded-full" aria-hidden />
          ONE MODEL, ONE MONEY METRIC
        </p>
        <h2 id="ways-title" className="mt-5 text-[clamp(28px,3.3vw,38px)] leading-[1.15] font-semibold tracking-[-0.035em] text-balance">
          One model, three ways it stays ahead
        </h2>
        <p className="mx-auto mt-4 max-w-[600px] text-[16px] leading-[1.5] text-pretty text-subtle">
          The queue, the improvement network and the drift checks all run on the same protected data, the same labels
          and the same measure: fraud money caught per day.
        </p>
      </div>

      {/* Inner frame, inset from the column rules as in the reference. */}
      <div className="border-t border-border md:px-[54px]">
        <div className="border-border md:border-x">
          <div className="grid md:grid-cols-2">
            <div className="px-5 pt-12 pb-14 md:border-r md:border-border md:px-10">
              <BlockHead tag="REVIEW QUEUE" title="A queue your analysts can finish">
                Today&apos;s payments ranked by expected loss and cut at your team&apos;s capacity, each with the three
                reasons behind it. Every verdict becomes a label the next version learns from.
              </BlockHead>
              <QueueStack />
            </div>
            <div className="border-t border-border px-5 pt-12 pb-10 md:border-t-0 md:px-10">
              <BlockHead tag="IMPROVEMENT" title="A model that keeps getting better">
                A private competition puts your model in front of a global network of solvers. The holdout stays
                sealed, and only versions that pass all five gates come back.
              </BlockHead>
              <Honeycomb />
            </div>
          </div>

          <div className="grid border-t border-border md:grid-cols-[270px_1fr_270px]">
            <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
              <div className="text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">$4,685</div>
              <div className="mt-3 text-[16px] text-subtle">First model, caught per day</div>
            </div>
            <figure className="flex flex-col items-center justify-center border-y border-border px-6 py-10 text-center md:border-x md:border-y-0">
              <blockquote className="max-w-[460px] text-[18px] leading-[1.45] tracking-[-0.01em] text-balance">
                <span className="text-muted">&ldquo;Every number comes from code.</span>{" "}
                <span className="text-foreground">No language model writes a number the user sees.&rdquo;</span>
              </blockquote>
              <figcaption className="mt-5 flex items-center gap-2 text-[15px]">
                <LogoMark id="quote-logo" className="h-[20px] w-[16px] overflow-visible" />
                <span className="text-foreground">Concours</span>
                <span className="text-muted">• How we measure</span>
              </figcaption>
            </figure>
            <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
              <div className="text-gradient text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">
                $6,543
              </div>
              <div className="mt-3 text-[16px] text-subtle">Version 3, caught per day</div>
            </div>
          </div>

          <div className="relative border-t border-border px-5 pt-12 pb-14 md:px-10">
            {/* Chamfered outline around the block heading, as in the reference. */}
            <svg aria-hidden className="pointer-events-none absolute inset-x-0 top-0 hidden h-[290px] w-full md:block" preserveAspectRatio="none" viewBox="0 0 1000 290">
              <path
                d="M60 0V205L0 290M940 0V205L1000 290M190 0V222H810V0"
                fill="none"
                stroke="var(--border)"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
            <div className="relative">
              <BlockHead tag="HEALTH" title="Know the day fraud changes">
                Weekly health on mature labels and drift checks on amount, hour and terminal activity. When a new
                pattern lands, an improvement round starts on its own.
              </BlockHead>
            </div>
            <HealthDashboard />
          </div>
        </div>
      </div>

      <div className="flex justify-center border-t border-border px-4 py-[50px]">
        <a
          href="/app/login"
          className="bg-brand-x inline-flex h-[56px] items-center gap-2.5 rounded-xl px-7 text-[17px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          Sign in
          <ArrowRight className="size-[18px]" />
        </a>
      </div>
    </section>
  );
}
