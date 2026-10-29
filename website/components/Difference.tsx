import type { ReactNode } from "react";
import { LogoMark } from "./Logo";

// "The Concours difference": the four safeguards that make a version trustworthy, from CONCOURS.md (late
// labels, protection, gates). Figures are the Card fraud review queue sample (workspace/concours.db): v1 and v2
// were compared on 134,186 holdout transactions; the regression gate allows no segment to drop more than 5%.

const ICONS = {
  lock: "M7 11V8a5 5 0 0110 0v3M6 11h12v10H6zM12 15v2",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
  filter: "M3 5h18l-7 8v6l-4 2v-8L3 5z",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5",
} as const;

function Icon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="url(#diff-icon)"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-9"
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

function Feature({ icon, title, children, className = "" }: { icon: keyof typeof ICONS; title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col items-center px-6 py-12 text-center ${className}`}>
      <Icon name={icon} />
      <h3 className="mt-6 text-[19px] font-semibold tracking-[-0.015em]">{title}</h3>
      <p className="mt-3 max-w-[340px] text-[15.5px] leading-[1.55] text-muted">{children}</p>
    </div>
  );
}

/** A small Concours slab projecting onto a gridded tile: the model scored against the sealed holdout. */
function BeamArt() {
  const cx = 143;
  const hw = 44;
  const hh = 24;
  const t = 12;
  const top = 34;
  const tile = 168;
  const face = (y: number) => `M${cx} ${y}L${cx + hw} ${y + hh}L${cx} ${y + 2 * hh}L${cx - hw} ${y + hh}Z`;
  return (
    <svg viewBox="0 0 286 240" className="h-[220px] w-auto" aria-hidden>
      <defs>
        <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f472b6" stopOpacity="0.55" />
          <stop offset="1" stopColor="#818cf8" stopOpacity="0.04" />
        </linearGradient>
        <linearGradient id="slab-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.5" stopColor="#f472b6" />
          <stop offset="1" stopColor="#c084fc" />
        </linearGradient>
        <linearGradient id="slab-edge" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.5" stopColor="#f472b6" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <pattern id="tile-grid" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="matrix(1 0.55 -1 0.55 0 0)">
          <path d="M8 0H0V8" fill="none" stroke="#c084fc" strokeOpacity="0.55" strokeWidth="0.8" />
        </pattern>
      </defs>
      {/* Beam from the slab's front edges down to the tile. */}
      <path
        d={`M${cx - hw} ${top + hh + t}L${cx} ${top + 2 * hh + t}L${cx + hw} ${top + hh + t}L${cx + hw} ${tile + hh}L${cx} ${tile + 2 * hh}L${cx - hw} ${tile + hh}Z`}
        fill="url(#beam)"
        className="anim-breathe"
      />
      {/* Holdout tile. */}
      <path d={face(tile)} fill="var(--card)" stroke="#c084fc" strokeOpacity="0.7" />
      <path d={face(tile)} fill="url(#tile-grid)" />
      <path
        d={`M${cx - hw} ${tile + hh}V${tile + hh + 6}L${cx} ${tile + 2 * hh + 6}L${cx + hw} ${tile + hh + 6}V${tile + hh}`}
        fill="none"
        stroke="#c084fc"
        strokeOpacity="0.5"
      />
      {/* Concours slab. */}
      <path
        d={`M${cx - hw} ${top + hh}V${top + hh + t}L${cx} ${top + 2 * hh + t}L${cx + hw} ${top + hh + t}V${top + hh}Z`}
        fill="url(#slab-side)"
        stroke="url(#slab-edge)"
      />
      <path d={face(top)} fill="var(--card)" stroke="url(#slab-edge)" strokeWidth={1.2} />
      <LogoMark id="diff-logo" x={cx - 10} y={top + 6} width={20} height={26} overflow="visible" />
    </svg>
  );
}

const HATCH = "bg-[repeating-linear-gradient(135deg,var(--border)_0_1px,transparent_1px_9px)]";
const DOTS = "bg-[radial-gradient(var(--border-strong)_1px,transparent_1px)] bg-[length:10px_10px]";

export function Difference() {
  return (
    <section id="results" aria-labelledby="diff-title" className="border-t border-border">
      <svg width="0" height="0" className="absolute" aria-hidden>
        <defs>
          <linearGradient id="diff-icon" gradientUnits="userSpaceOnUse" x1="4" y1="2" x2="20" y2="22">
            <stop offset="0" stopColor="#fbb39c" />
            <stop offset="0.34" stopColor="#f472b6" />
            <stop offset="0.66" stopColor="#c084fc" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
        </defs>
      </svg>

      <div className="px-4 pt-[50px] pb-[42px] text-center">
        <p className="inline-flex h-[29px] items-center gap-2.5 rounded-md border border-border-strong bg-card-2 px-3 font-mono text-[12.5px] leading-none tracking-[0.06em] text-subtle">
          <span className="bg-brand size-[7px] rounded-full" aria-hidden />
          THE CONCOURS DIFFERENCE
        </p>
        <h2
          id="diff-title"
          className="mx-auto mt-5 max-w-[560px] text-[clamp(30px,3.4vw,40px)] leading-[1.15] font-medium tracking-[-0.03em] text-balance"
        >
          Judgment a public leaderboard can&apos;t give you
        </h2>
        <p className="mx-auto mt-5 max-w-[520px] text-[16px] leading-[1.45] text-pretty text-subtle">
          A leaderboard rewards whoever fits the public test best. Concours checks every version against the things
          that break fraud models in production.
        </p>
      </div>

      <div className="grid border-t border-border md:grid-cols-[54px_1fr_54px]">
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
        <div className="md:border-x md:border-border">
          <div className="grid md:grid-cols-[1fr_286px_1fr]">
            <Feature icon="lock" title="A sealed holdout">
              Every version is scored on private days that nobody in the competition can see or tune to.
            </Feature>
            <div className="relative flex items-center justify-center border-y border-border md:border-x md:border-y-0">
              <div aria-hidden className={`absolute inset-0 ${DOTS} [mask-image:radial-gradient(closest-side,#000,transparent)]`} />
              <BeamArt />
            </div>
            <Feature icon="clock" title="Labels as they were known">
              Fraud is confirmed weeks later. Training and scoring use labels as they were known at the time, never
              from the future.
            </Feature>
          </div>
          <div className="grid border-t border-border md:grid-cols-2">
            <Feature icon="filter" title="Leaks caught before training" className="md:border-r md:border-border">
              Future information, clock counters and columns that give the answer away are removed before any
              model sees the data.
            </Feature>
            <Feature icon="layers" title="No hidden regressions" className="border-t border-border md:border-t-0">
              A version cannot win overall by getting worse for small payments, large ones or new customers. No
              segment may drop more than 5%.
            </Feature>
          </div>
        </div>
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
      </div>

      <div className="border-t border-border md:px-[54px]">
        <div className="grid border-border md:grid-cols-[270px_1fr_270px] md:border-x">
          <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <div className="text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">134,186</div>
            <div className="mt-3 text-[16px] text-subtle">Holdout payments, v1 vs v2</div>
          </div>
          <figure className="flex flex-col items-center justify-center border-y border-border px-6 py-12 text-center md:border-x md:border-y-0">
            <blockquote className="max-w-[460px] text-[18px] leading-[1.45] tracking-[-0.01em] text-balance">
              <span className="text-muted">&ldquo;Measured on recent days the model never saw,</span>{" "}
              <span className="text-foreground">with labels as they were known then.&rdquo;</span>
            </blockquote>
            <figcaption className="mt-5 flex items-center gap-2 text-[15px]">
              <LogoMark id="diff-quote-logo" className="h-[20px] w-[16px] overflow-visible" />
              <span className="text-foreground">Concours</span>
              <span className="text-muted">• Money inside capacity</span>
            </figcaption>
          </figure>
          <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <div className="text-gradient text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">5%</div>
            <div className="mt-3 text-[16px] text-subtle">Most any segment may drop</div>
          </div>
        </div>
      </div>
    </section>
  );
}
