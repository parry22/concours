import { ArrowRight } from "./icons";
import { LogoMark } from "./Logo";

// "Today's queue from your own payments": what a case looks like, how cases are ranked and why each was picked.
// Reason chips are strings from backend/app/fraud/reasons.py; ranking and wording follow CONCOURS.md and
// frontend/lib/copy.ts (queue.sub). The case card amount and score are example values inside a mock.

const ICONS = {
  amount: "M12 3v18M17 7.5C17 5.6 14.8 4 12 4S7 5.6 7 7.5 9.2 11 12 11.5s5 2 5 4-2.2 3.5-5 3.5-5-1.6-5-3.5",
  moon: "M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z",
  terminal: "M5 3h14v18H5zM9 7h6M9 11h6M9 15h2",
  burst: "M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z",
  card: "M3 6h18v12H3zM3 10h18",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  target: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 17a5 5 0 100-10 5 5 0 000 10zM12 13a1 1 0 100-2 1 1 0 000 2z",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
} as const;

function Icon({ name, className = "size-[18px]", stroke = "currentColor" }: { name: keyof typeof ICONS; className?: string; stroke?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

const CHIP_ROWS: { icon: keyof typeof ICONS; text: string }[][] = [
  [
    { icon: "amount", text: "Unusual amount" },
    { icon: "moon", text: "Night-time payment" },
  ],
  [
    { icon: "burst", text: "Card-testing burst at this terminal" },
    { icon: "terminal", text: "Terminal had recent fraud" },
  ],
  [
    { icon: "card", text: "Many payments on this card today" },
    { icon: "user", text: "Customer had recent fraud" },
  ],
];

/** Faint tile grid behind the chips, as in the reference. */
const TILES =
  "bg-[linear-gradient(90deg,var(--background)_8px,transparent_8px),linear-gradient(var(--background)_8px,transparent_8px)] bg-[length:96px_56px] bg-card/70";

function Chips() {
  return (
    <div className="relative px-4 py-10 md:px-2 md:py-[66px]">
      <div aria-hidden className={`absolute inset-0 ${TILES} [mask-image:radial-gradient(closest-side,#000,transparent)]`} />
      <div className="relative flex flex-col items-center gap-4">
        {CHIP_ROWS.map((row, r) => (
          <div key={r} className={`flex flex-wrap justify-center gap-3 lg:flex-nowrap ${r === 1 ? "lg:-translate-x-5" : ""}`}>
            {row.map((c) => (
              <span
                key={c.text}
                className="inline-flex h-[46px] items-center gap-2.5 rounded-lg border border-border-strong bg-card-2 px-3.5 text-[14px] font-medium whitespace-nowrap shadow-[0_8px_18px_-12px_rgb(0_0_0/0.9)]"
              >
                <Icon name={c.icon} stroke="url(#queue-icon)" />
                {c.text}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// Icon grid around the centre tile. Positions are columns and rows on a 5 x 3 grid; empty slots stay faint.
const ORBIT: { col: number; row: number; icon?: keyof typeof ICONS }[] = [
  { col: 1, row: 0, icon: "amount" },
  { col: 2, row: 0 },
  { col: 3, row: 0, icon: "clock" },
  { col: 0, row: 1, icon: "card" },
  { col: 1, row: 1 },
  { col: 3, row: 1 },
  { col: 4, row: 1, icon: "user" },
  { col: 1, row: 2 },
  { col: 2, row: 2, icon: "layers" },
  { col: 3, row: 2 },
];

function RankArt() {
  // Grid spacing shrinks on narrow screens so the outer icons stay inside the cell.
  return (
    <div className="relative mx-auto h-[240px] w-full max-w-[400px] [--step:min(88px,20vw)]" aria-hidden>
      <div className="absolute inset-x-6 top-1/2 h-px -translate-y-1/2 bg-[linear-gradient(90deg,transparent,var(--border),transparent)]" />
      <div className="absolute inset-y-4 left-1/2 w-px -translate-x-1/2 bg-[linear-gradient(transparent,var(--border),transparent)]" />
      {ORBIT.map((o) => (
        <span
          key={`${o.col}${o.row}`}
          className={`absolute grid size-[46px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full ${o.icon ? "border border-border-strong bg-card-2 text-subtle shadow-[0_6px_14px_-8px_rgb(0_0_0/0.9)]" : "bg-card/70"}`}
          style={{ left: `calc(50% + ${o.col - 2} * var(--step))`, top: `calc(50% + ${o.row - 1} * var(--step))` }}
        >
          {o.icon && (
            <span className="anim-float block" style={{ animationDelay: `${(o.col + o.row) * -0.8}s` }}>
              <Icon name={o.icon} className="size-5" />
            </span>
          )}
        </span>
      ))}
      <span className="anim-glow absolute top-1/2 left-1/2 grid size-[64px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-2xl border border-border-strong bg-card shadow-[0_0_0_1px_rgb(244_114_182/0.35),0_0_34px_-4px_rgb(244_114_182/0.55)]">
        <LogoMark id="queue-logo" className="h-[34px] w-[26px] overflow-visible" />
      </span>
    </div>
  );
}

function CaseArt() {
  return (
    <div className="relative mx-auto w-[340px] max-w-full pt-5" aria-hidden>
      <div className="absolute inset-x-6 top-0 h-6 rounded-t-xl border border-b-0 border-border bg-card/60" />
      <div className="absolute inset-x-3 top-2.5 h-6 rounded-t-xl border border-b-0 border-border bg-card/80" />
      <div className="relative rounded-xl border border-border-strong bg-card p-[18px] shadow-[0_20px_40px_-20px_rgb(0_0_0/0.9)]">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-lg border border-border-strong bg-card-2 text-foreground">
            <Icon name="target" className="size-5" />
          </span>
          <div className="text-left">
            <div className="font-mono text-[14.5px] tabular-nums">$2,140.00</div>
            <div className="text-[13px] text-muted">Risk score 91% from the model</div>
          </div>
        </div>
        <div className="bg-brand-x mt-4 flex h-10 items-center justify-center rounded-lg text-[14px] font-semibold text-accent-ink">
          See the three reasons
        </div>
      </div>
    </div>
  );
}

export function Queue() {
  return (
    <section aria-labelledby="queue-title" className="border-t border-border">
      {/* Gradient for the chip icons, the product's .icon-brand stroke. */}
      <svg width="0" height="0" className="absolute" aria-hidden>
        <defs>
          <linearGradient id="queue-icon" gradientUnits="userSpaceOnUse" x1="4" y1="2" x2="20" y2="22">
            <stop offset="0" stopColor="#fbb39c" />
            <stop offset="0.34" stopColor="#f472b6" />
            <stop offset="0.66" stopColor="#c084fc" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
        </defs>
      </svg>

      <div className="px-4 pt-[60px] pb-[50px] text-center">
        <p className="inline-flex h-[30px] items-center rounded-md bg-card-2 px-3 font-mono text-[13px] tracking-[0.06em] text-subtle">
          THE REVIEW QUEUE
        </p>
        <h2
          id="queue-title"
          className="mx-auto mt-6 max-w-[520px] text-[clamp(30px,3.6vw,42px)] leading-[1.22] font-medium tracking-[-0.03em] text-balance"
        >
          Today&apos;s queue, from your own payments.
        </h2>
        <p className="mx-auto mt-5 max-w-[500px] text-[15.5px] leading-[1.45] text-pretty text-muted">
          Upload payments with a fraud label. In the same sitting you get the cases to review first, why each one was
          picked, and how the model was checked.
        </p>
      </div>

      <div className="border-t border-border md:px-[54px]">
        <div className="border-border md:border-x">
          <div className="grid items-center md:grid-cols-[1fr_1.15fr]">
            <div className="px-5 pt-10 md:px-[51px] md:pt-0">
              <h3 className="text-[24px] font-medium tracking-[-0.02em]">What each case looks like</h3>
              <p className="mt-3 max-w-[340px] text-[15.5px] leading-[1.5] text-muted">
                A payment, its chance of fraud times the money at stake, and the reasons behind its score. Your queue
                holds as many as your team can review.
              </p>
            </div>
            <Chips />
          </div>

          <div className="grid border-t border-border md:grid-cols-2">
            <div className="flex min-w-0 flex-col items-center px-5 pt-10 pb-10 text-center md:border-r md:border-border">
              <RankArt />
              <h3 className="mt-8 text-[24px] font-medium tracking-[-0.02em]">Ranked by expected loss</h3>
              <p className="mt-2 max-w-[420px] text-[15px] leading-[1.55] text-muted">
                Chance of fraud times the money at stake, so the cases worth the most are reviewed first and the queue
                stops at your capacity.
              </p>
            </div>
            <div className="flex min-w-0 flex-col items-center border-t border-border px-5 pt-10 pb-10 text-center md:border-t-0">
              <div className="flex h-[240px] items-center">
                <CaseArt />
              </div>
              <h3 className="mt-8 text-[24px] font-medium tracking-[-0.02em]">The reasons, not a black box</h3>
              <p className="mt-2 max-w-[420px] text-[15px] leading-[1.55] text-muted">
                Every case shows the top three reasons behind its score in plain English, so your analysts can judge
                it. Each verdict becomes a new label.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-center border-t border-border px-4 py-[50px]">
        <a
          href="/app/signup"
          className="bg-brand-x inline-flex h-[56px] items-center gap-2.5 rounded-xl px-7 text-[17px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          Get started
          <ArrowRight className="size-[18px]" />
        </a>
      </div>
    </section>
  );
}
