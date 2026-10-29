"use client";

import { useState, type ReactNode } from "react";
import { LogoMark } from "./Logo";

// What you keep and what solvers see. Every line is the product's own wording from the Launch screen
// (frontend/lib/copy.ts: termList, zipNote, howApexSub, leavesPackage) and CONCOURS.md. Pricing is left out on
// purpose: the product marks its plan as illustrative.

const ICONS = {
  key: "M15 7a4 4 0 11-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0115 7zM16.5 8.5h.01",
  users: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21a7 7 0 0114 0M16 3.5a4 4 0 010 7.5M18 14a6 6 0 014 7",
  eyeOff: "M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.1A9.7 9.7 0 0112 5c5 0 9 4.5 10 7a13 13 0 01-2.6 3.6M6.6 6.6A13 13 0 002 12c1 2.5 5 7 10 7a9.7 9.7 0 004.4-1",
  share: "M18 8a3 3 0 100-6 3 3 0 000 6zM6 15a3 3 0 100-6 3 3 0 000 6zM18 22a3 3 0 100-6 3 3 0 000 6zM8.6 13.5l6.8 4M15.4 6.5l-6.8 4",
  lock: "M7 11V8a5 5 0 0110 0v3M6 11h12v10H6z",
  shield: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3z",
  file: "M6 3h8l4 4v14H6zM14 3v4h4M9 13h6M9 17h4",
  scale: "M12 3v18M5 7h14M5 7l-3 7a3 3 0 006 0L5 7zM19 7l-3 7a3 3 0 006 0l-3-7z",
  check: "M20 6L9 17l-5-5",
} as const;

function Icon({ name, className = "size-5" }: { name: keyof typeof ICONS; className?: string }) {
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

/** Tick ruler with a highlighted centre stop, as in the reference's month picker. */
function Ruler({ unit, stops }: { unit: string; stops: [string, string, string] }) {
  const ticks = Array.from({ length: 41 }, (_, i) => i);
  return (
    <div className="relative mt-6 h-[120px]">
      <div className="absolute inset-x-0 top-[34px] flex h-[52px] items-center justify-between" aria-hidden>
        {ticks.map((i) => {
          const major = i % 10 === 0 && i !== 0 && i !== 40;
          const faded = i < 3 || i > 37;
          return (
            <span
              key={i}
              className={`w-px rounded-full ${major ? "h-8 bg-subtle" : "h-4 bg-border-strong"} ${faded ? "opacity-40" : ""}`}
            />
          );
        })}
      </div>
      <div className="absolute inset-0 grid grid-cols-3 text-center font-mono text-[10.5px] tracking-[0.06em] text-muted">
        {stops.map((s, i) =>
          i === 1 ? (
            <div
              key={s}
              className="relative mx-auto flex w-[60px] flex-col items-center justify-between rounded-lg border border-border-strong bg-card-2 py-2 shadow-[0_8px_18px_-10px_rgb(0_0_0/0.9)]"
            >
              <span>{unit}</span>
              <span className="bg-brand anim-breathe h-[52px] w-[2px] rounded-full" aria-hidden />
              <span className="text-foreground">{s}</span>
            </div>
          ) : (
            <div key={s} className="flex flex-col items-center justify-between py-2">
              <span>{unit}</span>
              <span className="text-subtle">{s}</span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function SolverDots() {
  // Invited seats lit, the rest of the network dark: the problem never reaches them.
  const lit = new Set([2, 5, 9, 14, 16, 21]);
  return (
    <div className="mt-6">
      <div className="grid grid-cols-12 gap-2.5" aria-hidden>
        {Array.from({ length: 24 }, (_, i) => (
          <span
            key={i}
            className={`aspect-square rounded-full ${lit.has(i) ? "bg-brand" : "border border-dashed border-border-strong"}`}
          />
        ))}
      </div>
      <div className="mt-4 flex justify-between font-mono text-[10.5px] tracking-[0.06em] text-muted">
        <span className="text-subtle">INVITED</span>
        <span>NOT LISTED PUBLICLY</span>
      </div>
    </div>
  );
}

function SealedBoard() {
  return (
    <ul className="mt-5 space-y-2" aria-hidden>
      {["Attempt A", "Attempt B", "Attempt C"].map((a) => (
        <li key={a} className="flex h-9 items-center justify-between rounded-lg border border-border-strong bg-card-2 px-3 text-[12.5px]">
          <span className="text-subtle">{a}</span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-16 rounded-full bg-[repeating-linear-gradient(90deg,var(--border-strong)_0_6px,transparent_6px_9px)]" />
            <span className="font-mono text-[10.5px] tracking-[0.06em] text-muted">SEALED</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

type Term = {
  icon: keyof typeof ICONS;
  title: string;
  body: string;
  card: { title: string; sub: string; badge: string; badgeIcon: keyof typeof ICONS; visual: ReactNode };
  note: { icon: keyof typeof ICONS; title: string; body: string };
};

const TERMS: Term[] = [
  {
    icon: "key",
    title: "You own the result",
    body: "Every promoted version and its code are yours.",
    card: {
      title: "Every version is yours",
      sub: "Promoted versions and their code",
      badge: "Yours",
      badgeIcon: "key",
      visual: <Ruler unit="VERSION" stops={["02", "03", "NEXT"]} />,
    },
    note: {
      icon: "shield",
      title: "Your data stays protected",
      body: "IDs are scrambled, and card numbers never reach disk.",
    },
  },
  {
    icon: "users",
    title: "Private competition",
    body: "Only invited solvers take part. The problem is not listed publicly.",
    card: {
      title: "Invited solvers only",
      sub: "The problem is not listed publicly",
      badge: "Private",
      badgeIcon: "lock",
      visual: <SolverDots />,
    },
    note: {
      icon: "file",
      title: "Private test days stay out",
      body: "The handoff leaves out the private holdout and its labels; only their checksums go with it.",
    },
  },
  {
    icon: "eyeOff",
    title: "Results hidden during the round",
    body: "Private scores stay sealed until the round closes, so nobody can tune to the holdout.",
    card: {
      title: "Scores sealed",
      sub: "Until the round closes",
      badge: "Sealed",
      badgeIcon: "lock",
      visual: <SealedBoard />,
    },
    note: {
      icon: "scale",
      title: "One referee for every attempt",
      body: "Every attempt is measured by the same referee on the private holdout.",
    },
  },
  {
    icon: "share",
    title: "Solutions shared after 7 days",
    body: "After the round, attempts are shared among the solvers who took part, which keeps the network improving.",
    card: {
      title: "Shared after the round",
      sub: "Among the solvers who took part",
      badge: "Day 7",
      badgeIcon: "share",
      visual: <Ruler unit="DAY" stops={["06", "07", "08"]} />,
    },
    note: {
      icon: "check",
      title: "Promotion is still earned",
      body: "An attempt becomes a version here only when it beats the active one by the margin on the private holdout.",
    },
  },
];

export function Terms() {
  const [open, setOpen] = useState(0);
  const term = TERMS[open];

  return (
    <section id="security" aria-labelledby="terms-title" className="border-t border-border">
      {/* Empty band above the split, as in the reference. */}
      <div className="h-[60px] border-b border-border md:h-[82px]" aria-hidden />

      <div className="grid md:grid-cols-[minmax(0,600px)_1fr]">
        <div className="md:pl-[54px]">
          <div className="border-border md:h-full md:border-l">
            <h2
              id="terms-title"
              className="px-5 pt-10 pb-12 text-[clamp(30px,3.4vw,40px)] leading-[1.25] font-medium tracking-[-0.03em] text-balance md:px-[31px]"
            >
              Clear about what you keep, and what solvers see
            </h2>
            <ul className="border-t border-border">
              {TERMS.map((t, i) => {
                const on = i === open;
                return (
                  <li key={t.title} className="relative border-b border-border last:border-b-0">
                    {on && <span className="bg-brand absolute top-[26px] -left-px h-6 w-[2px]" aria-hidden />}
                    <button
                      type="button"
                      aria-expanded={on}
                      aria-controls={`term-body-${i}`}
                      onClick={() => setOpen(i)}
                      className={`flex w-full items-center gap-3 px-5 pt-[22px] text-left text-[18px] tracking-[-0.015em] transition-colors duration-200 md:px-[31px] ${
                        on ? "pb-2 font-medium text-foreground" : "pb-[22px] text-subtle hover:text-foreground"
                      }`}
                    >
                      <Icon name={t.icon} className={`size-5 ${on ? "text-foreground" : "text-muted"}`} />
                      {t.title}
                    </button>
                    <div
                      id={`term-body-${i}`}
                      className={`grid transition-[grid-template-rows] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${on ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
                    >
                      <p className="overflow-hidden px-5 text-[15.5px] leading-[1.6] text-subtle md:pr-16 md:pl-[63px]">
                        <span className="block pb-6">{t.body}</span>
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        <div className="relative min-h-[520px] overflow-hidden border-t border-border md:border-t-0">
          {/* Brand-gradient backdrop in place of the reference's photograph. */}
          <div
            aria-hidden
            className="anim-drift absolute inset-0 bg-[radial-gradient(90%_70%_at_85%_0%,#fbb39c_0%,transparent_55%),radial-gradient(80%_70%_at_0%_45%,#c084fc_0%,transparent_60%),radial-gradient(100%_80%_at_70%_100%,#818cf8_0%,transparent_60%),radial-gradient(60%_50%_at_40%_70%,#f472b6_0%,transparent_60%),linear-gradient(#2a1640,#131022)] opacity-90"
          />
          <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_10_11/0.1),rgb(10_10_11/0.45))]" />

          <div key={open} className="relative mx-auto max-w-[540px] animate-[fig-in_420ms_cubic-bezier(0.22,1,0.36,1)_both] px-5 py-12 md:px-12 md:py-[60px]">
            <div className="rounded-2xl border border-border-strong bg-card p-6 shadow-[0_24px_48px_-16px_rgb(10_10_11/0.7)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[18px] font-semibold tracking-[-0.015em]">{term.card.title}</div>
                  <div className="mt-1 text-[14px] text-muted">{term.card.sub}</div>
                </div>
                <span className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg bg-foreground px-3 text-[14px] font-medium text-background">
                  <Icon name={term.card.badgeIcon} className="size-4" />
                  {term.card.badge}
                </span>
              </div>
              {term.card.visual}
            </div>

            <div className="mt-[18px] flex items-center gap-4 rounded-2xl border border-border-strong bg-card p-3 pr-6">
              <span className="bg-brand grid size-16 shrink-0 place-items-center rounded-xl text-accent-ink">
                <Icon name={term.note.icon} className="size-6" />
              </span>
              <div>
                <div className="text-[15.5px] font-semibold tracking-[-0.01em]">{term.note.title}</div>
                <p className="mt-0.5 text-[13px] leading-[1.45] text-muted">{term.note.body}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid border-t border-border md:grid-cols-[324px_1fr_324px]">
        <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
          <div className="text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">1,000</div>
          <div className="mt-3 text-[16px] text-subtle">Resamples in every luck test</div>
        </div>
        <figure className="flex flex-col items-center justify-center border-y border-border px-6 py-12 text-center md:border-x md:border-y-0">
          <blockquote className="max-w-[440px] text-[18px] leading-[1.45] tracking-[-0.01em] text-balance">
            <span className="text-muted">&ldquo;Promotion is earned.</span>{" "}
            <span className="text-foreground">
              A new version must pass five gates on the private holdout. Public scores never decide.&rdquo;
            </span>
          </blockquote>
          <figcaption className="mt-5 flex items-center gap-2 text-[15px]">
            <LogoMark id="terms-quote-logo" className="h-[20px] w-[16px] overflow-visible" />
            <span className="text-foreground">Concours</span>
            <span className="text-muted">• How we promote</span>
          </figcaption>
        </figure>
        <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
          <div className="text-gradient text-[32px] leading-none font-semibold tracking-[-0.035em] tabular-nums">95%</div>
          <div className="mt-3 text-[16px] text-subtle">Of them a new version must win</div>
        </div>
      </div>
    </section>
  );
}
