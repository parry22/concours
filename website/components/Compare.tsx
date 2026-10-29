import { ArrowRight } from "./icons";
import { LogoMark } from "./Logo";

// How Concours compares with the two usual alternatives. The Concours column only states what the product does
// (CONCOURS.md, frontend/lib/copy.ts); the other columns stay general and avoid figures we cannot source.

const ICONS = {
  box: "M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
  users: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21a7 7 0 0114 0M16 3.5a4 4 0 010 7.5M18 14a6 6 0 014 7",
  scale: "M12 3v18M5 7h14M5 7l-3 7a3 3 0 006 0L5 7zM19 7l-3 7a3 3 0 006 0l-3-7z",
  key: "M15 7a4 4 0 11-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0115 7zM16.5 8.5h.01",
  ruler: "M3 17L17 3l4 4L7 21l-4-4zM7 13l2 2M10 10l2 2M13 7l2 2",
} as const;

const ROWS: { icon: keyof typeof ICONS; label: string; us: string; team: string; rules: string }[] = [
  {
    icon: "box",
    label: "What you get",
    us: "A working fraud model and today's review queue.",
    team: "A model, once the team, data access and pipeline exist.",
    rules: "Rules your analysts write and tune by hand.",
  },
  {
    icon: "clock",
    label: "Time to first model",
    us: "The same sitting as your upload.",
    team: "After hiring, data access and a first project.",
    rules: "No model. Each rule works from the day it is written.",
  },
  {
    icon: "users",
    label: "Who improves it",
    us: "A global network of solvers, in a private competition.",
    team: "Your own team, as its backlog allows.",
    rules: "An analyst, once a new pattern is noticed.",
  },
  {
    icon: "scale",
    label: "How a change is approved",
    us: "Five gates on hidden days. Public scores never decide.",
    team: "Whatever review your team sets up.",
    rules: "Usually by judgement, rule by rule.",
  },
  {
    icon: "key",
    label: "What you keep",
    us: "Every promoted version and its code.",
    team: "The model, and the team to maintain it.",
    rules: "A growing list of rules to maintain.",
  },
  {
    icon: "ruler",
    label: "How results are measured",
    us: "Fraud money caught per day, inside your review capacity.",
    team: "Whatever metric the team picks.",
    rules: "Hits per rule.",
  },
];

const PRINCIPLES = [
  {
    tag: "PRINCIPLE 01",
    quote: "Every project produces a working model and today's review queue before any contest.",
    name: "Day-one value",
  },
  {
    tag: "PRINCIPLE 02",
    quote: "Every result is fraud money caught per day inside the team's review capacity, on days the model never saw.",
    name: "Money inside capacity",
  },
];

const HATCH = "bg-[repeating-linear-gradient(135deg,var(--border)_0_1px,transparent_1px_9px)]";

function Icon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="url(#cmp-icon)"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-5 shrink-0"
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

export function Compare() {
  return (
    <section aria-labelledby="compare-title" className="border-t border-border">
      {/* Gradient for the row icons, the product's .icon-brand stroke. */}
      <svg width="0" height="0" className="absolute" aria-hidden>
        <defs>
          <linearGradient id="cmp-icon" gradientUnits="userSpaceOnUse" x1="4" y1="2" x2="20" y2="22">
            <stop offset="0" stopColor="#fbb39c" />
            <stop offset="0.34" stopColor="#f472b6" />
            <stop offset="0.66" stopColor="#c084fc" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
        </defs>
      </svg>

      <div className="px-4 pt-[70px] text-center">
        <p className="inline-flex h-[29px] items-center rounded-md bg-card-2 px-3 font-mono text-[12.5px] tracking-[0.06em] text-subtle">
          HOW WE COMPARE
        </p>
        <h2
          id="compare-title"
          className="mx-auto mt-5 max-w-[640px] text-[clamp(28px,3.3vw,38px)] leading-[1.18] font-semibold tracking-[-0.035em] text-balance"
        >
          Don&apos;t wait for an ML team. Start with a model that improves.
        </h2>
        <p className="mx-auto mt-4 max-w-[560px] text-[15.5px] leading-[1.5] text-pretty text-subtle">
          Hiring a team takes time, and rules only catch what someone has already seen. Concours gives you a working
          model now, and a network that keeps improving it.
        </p>
      </div>

      <div className="mt-[72px] md:px-[54px]">
        <div className="no-scrollbar overflow-x-auto px-4 pt-[20px] md:px-0">
          <div className="min-w-[680px] md:min-w-[860px]">
            <div className="relative rounded-2xl border border-border-strong bg-card p-[10px] shadow-[0_24px_48px_-24px_rgb(0_0_0/0.9)]">
              {/* One continuous gradient behind the Concours column; its cells are transparent. */}
              <div aria-hidden className="bg-brand absolute top-[-16px] bottom-[10px] left-[150px] w-[calc((100%-180px)/3)] rounded-xl md:left-[290px] md:w-[calc((100%-320px)/3)]" />
              <div className="relative grid grid-cols-[130px_1fr_1fr_1fr] gap-x-[10px] md:grid-cols-[270px_1fr_1fr_1fr]">
                {/* Header row. The Concours column rises just above the card, as in the reference. */}
                <div />
                <div className="relative flex h-[56px] items-center justify-center gap-2 text-[16px] font-semibold text-accent-ink">
                  <LogoMark id="cmp-logo" className="h-[22px] w-[17px] overflow-visible drop-shadow-[0_1px_1px_rgb(0_0_0/0.25)]" />
                  Concours
                </div>
                <div className="flex h-[56px] items-center justify-center text-[15px] font-semibold text-foreground">
                  In-house ML team
                </div>
                <div className="flex h-[56px] items-center justify-center text-[15px] font-semibold text-foreground">
                  Rules only
                </div>

                {ROWS.map((r, i) => {
                  const last = i === ROWS.length - 1;
                  return (
                    <div key={r.label} className="contents">
                      <div className={`flex min-h-[80px] items-center gap-3 px-2 py-3 text-[13.5px] font-medium md:px-4 md:text-[15.5px] ${last ? "" : "border-b border-border"}`}>
                        <Icon name={r.icon} />
                        {r.label}
                      </div>
                      <div
                        className={`flex min-h-[80px] items-center px-5 py-3 text-[14.5px] leading-[1.4] font-medium text-accent-ink ${last ? "" : "border-b border-[rgb(10_10_11/0.12)]"}`}
                      >
                        {r.us}
                      </div>
                      <div
                        className={`flex min-h-[80px] items-center border-x border-border bg-card-2 px-4 py-3 text-[14.5px] leading-[1.4] text-subtle ${i === 0 ? "rounded-t-xl border-t" : ""} ${last ? "rounded-b-xl border-b" : "border-b"}`}
                      >
                        {r.team}
                      </div>
                      <div
                        className={`flex min-h-[80px] items-center border-x border-border bg-card-2 px-4 py-3 text-[14.5px] leading-[1.4] text-subtle ${i === 0 ? "rounded-t-xl border-t" : ""} ${last ? "rounded-b-xl border-b" : "border-b"}`}
                      >
                        {r.rules}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <p className="-mt-3 rounded-b-2xl bg-card-2 px-6 pt-[26px] pb-[18px] text-center text-[14.5px] text-subtle">
              Day-one value: every project gets a working model and today&apos;s review queue before any competition
              starts.
            </p>
          </div>
        </div>
      </div>

      <div className="flex justify-center px-4 pt-10 pb-10">
        <a
          href="#contact"
          className="bg-brand-x inline-flex h-[56px] items-center gap-2.5 rounded-xl px-7 text-[17px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          Book a demo
          <ArrowRight className="size-[18px]" />
        </a>
      </div>

      <div className="grid border-t border-border md:grid-cols-[54px_1fr_1fr_54px]">
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
        {PRINCIPLES.map((p, i) => (
          <figure
            key={p.tag}
            className={`flex flex-col items-center px-6 py-9 text-center md:border-l md:border-border ${i === 1 ? "border-t border-border md:border-t-0 md:border-r" : ""}`}
          >
            <span className="font-mono text-[12px] tracking-[0.08em] text-muted">{p.tag}</span>
            <blockquote className="mt-4 max-w-[420px] text-[17.5px] leading-[1.45] tracking-[-0.01em] text-balance">
              &ldquo;{p.quote}&rdquo;
            </blockquote>
            <figcaption className="mt-4 flex items-center gap-2 text-[14.5px]">
              <LogoMark id={`principle-logo-${i}`} className="h-[20px] w-[16px] overflow-visible" />
              <span className="text-foreground">Concours</span>
              <span className="text-muted">• {p.name}</span>
            </figcaption>
          </figure>
        ))}
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
      </div>
    </section>
  );
}
