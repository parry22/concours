"use client";

import { useState } from "react";

// Results from the sample projects (workspace/concours.db, seeded 2026-10-28): simulated card payments, scored on
// private holdout days the models never saw. Every figure here is a stored version score or gate line; none is
// rounded up or estimated. Change them only from a new run.

type Case = {
  tab: string;
  glyph: "spark" | "tune" | "bolt" | "dice" | "clock";
  figure: string;
  caption: string;
  lead: string;
  rest: string;
  who: string;
  role: string;
  /** Only promoted versions went through the five gates; v1 is built directly from the upload. */
  gated: boolean;
};

const CASES: Case[] = [
  {
    tab: "Day one",
    glyph: "spark",
    figure: "$3,714",
    caption: "of fraud caught per day in a 200-case queue, first model",
    lead: "A working model from the first upload,",
    rest: "with today's 200 payments ranked by expected loss and three plain reasons on each.",
    who: "Card fraud review queue, v1",
    role: "Sample project, simulated card payments",
    gated: false,
  },
  {
    tab: "Tuned",
    glyph: "tune",
    figure: "$3,961",
    caption: "of fraud caught per day, up from $3,714 with the first model",
    lead: "The improvement had to win on hidden days,",
    rest: "compared with v1 on the same 14 holdout days, 134,186 transactions, before it was promoted.",
    who: "Card fraud review queue, v2",
    role: "Promoted after passing all five gates",
    gated: true,
  },
  {
    tab: "Velocity",
    glyph: "bolt",
    figure: "$6,543",
    caption: "of fraud caught per day after a new pattern, up from $4,840",
    lead: "Fraudsters moved to card-testing cash-outs.",
    rest: "The next version learned payment velocity and caught them, checked on 135,941 holdout transactions.",
    who: "Marketplace payments, v3",
    role: "Promoted after passing all five gates",
    gated: true,
  },
  {
    tab: "Luck test",
    glyph: "dice",
    figure: "100%",
    caption: "of 1,000 day-block resamples won by each promoted version",
    lead: "No version is promoted on a lucky week.",
    rest: "Holdout days are resampled a thousand times and the new model has to win in at least 95% of them.",
    who: "Promotion gate: luck test",
    role: "Applied to every version",
    gated: true,
  },
  {
    tab: "Speed",
    glyph: "clock",
    figure: "0.3 s",
    caption: "to score 10,000 payments with the current version",
    lead: "Fast enough for tomorrow's queue,",
    rest: "and checked on every version: a model that cannot score 10,000 payments in five seconds is not promoted.",
    who: "Marketplace payments, v3",
    role: "Promotion gate: practical",
    gated: true,
  },
];

function Glyph({ name, className }: { name: Case["glyph"]; className?: string }) {
  const paths: Record<Case["glyph"], string> = {
    spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6",
    tune: "M4 7h10M18 7h2M4 17h4M12 17h8M16 5v4M10 15v4",
    bolt: "M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z",
    dice: "M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1zM9 9h.01M15 15h.01M15 9h.01M9 15h.01",
    clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
  };
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d={paths[name]} />
    </svg>
  );
}

/** Bracket corners around the selected tab, as in the reference. */
function Corners() {
  const c = "absolute size-[9px] border-foreground/70";
  return (
    <span aria-hidden>
      <span className={`${c} top-0 left-0 border-t border-l`} />
      <span className={`${c} top-0 right-0 border-t border-r`} />
      <span className={`${c} bottom-0 left-0 border-b border-l`} />
      <span className={`${c} right-0 bottom-0 border-r border-b`} />
    </span>
  );
}

function GateDots({ gated }: { gated: boolean }) {
  if (!gated)
    return (
      <div className="flex items-center gap-2.5 text-[13px] text-muted">
        <span className="bg-brand size-[7px] rounded-full" aria-hidden />
        Built from the upload, before any improvement round
      </div>
    );
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-[6px]" aria-hidden>
        {Array.from({ length: 5 }, (_, i) => (
          <span key={i} className="bg-brand grid size-[18px] place-items-center rounded-full">
            <svg viewBox="0 0 12 12" className="size-[10px]" fill="none">
              <path d="M2.5 6.2l2.2 2.2 4.8-4.8" stroke="#0a0a0b" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        ))}
      </div>
      <span className="text-[13px] text-muted">5 of 5 gates passed</span>
    </div>
  );
}

export function Proof() {
  const [active, setActive] = useState(2);
  const item = CASES[active];

  return (
    <section aria-labelledby="proof-title" id="results" className="border-t border-border pt-16 pb-[70px]">
      <h2 id="proof-title" className="px-4 text-center text-[17px] tracking-[-0.01em] text-subtle">
        Measured on 1.75 million simulated card payments, on days the model never saw
      </h2>

      <div
        role="tablist"
        aria-label="Results"
        className="no-scrollbar mx-auto mt-[38px] flex max-w-[900px] items-center justify-between gap-2 overflow-x-auto px-4"
      >
        {CASES.map((c, i) => {
          const on = i === active;
          return (
            <button
              key={c.tab}
              role="tab"
              id={`proof-tab-${i}`}
              aria-selected={on}
              aria-controls="proof-panel"
              onClick={() => setActive(i)}
              className={`relative inline-flex h-[48px] shrink-0 items-center gap-2 px-4 text-[18px] sm:h-[54px] sm:gap-2.5 sm:px-5 sm:text-[22px] font-semibold tracking-[-0.035em] transition-colors duration-200 ${
                on ? "bg-card-2 text-foreground" : "text-muted hover:text-subtle"
              }`}
            >
              {on && <Corners />}
              <Glyph name={c.glyph} className="size-[22px]" />
              {c.tab}
            </button>
          );
        })}
      </div>

      {/* Striped band behind the card, with a second card edge peeking out underneath. */}
      <div className="relative mt-[37px]">
        <div
          aria-hidden
          className="absolute inset-x-0 top-[18px] bottom-[-20px] border-y border-border bg-[repeating-linear-gradient(90deg,var(--border)_0_1px,transparent_1px_20px)]"
        />
        <div className="relative mx-auto max-w-[860px] px-4">
          <div aria-hidden className="absolute inset-x-[36px] -bottom-[10px] h-6 rounded-b-2xl border border-border bg-card" />
          <div
            role="tabpanel"
            id="proof-panel"
            aria-labelledby={`proof-tab-${active}`}
            className="relative grid gap-[10px] rounded-2xl border border-border-strong bg-card p-[10px] md:grid-cols-[269px_1fr]"
          >
            <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl bg-card-2 px-8 py-10 text-center md:min-h-[290px]">
              <div key={item.figure} className="text-gradient animate-[fig-in_420ms_cubic-bezier(0.22,1,0.36,1)_both] text-[42px] leading-none font-semibold tracking-[-0.04em] tabular-nums">
                {item.figure}
              </div>
              <p className="mt-4 max-w-[200px] text-[16px] leading-[1.45] text-subtle">{item.caption}</p>
            </div>
            <div className="flex flex-col justify-center px-4 py-6 md:px-[27px] md:py-8">
              <GateDots gated={item.gated} />
              <blockquote
                key={item.lead}
                className="mt-5 max-w-[470px] animate-[fig-in_420ms_cubic-bezier(0.22,1,0.36,1)_both] text-[22px] leading-[1.3] tracking-[-0.02em] text-pretty md:text-[24px]"
              >
                <span className="text-foreground">{item.lead}</span> <span className="text-muted">{item.rest}</span>
              </blockquote>
              <div className="mt-7 flex items-center gap-3">
                <span className="grid size-[46px] place-items-center rounded-full border border-border-strong bg-card-2 text-subtle">
                  <Glyph name={item.glyph} className="size-5" />
                </span>
                <div>
                  <div className="text-[17px] font-medium tracking-[-0.01em] text-foreground">{item.who}</div>
                  <div className="text-[14px] text-muted">{item.role}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
