"use client";

import { useState, type ReactNode } from "react";
import { ArrowRight } from "./icons";

// Three steps of the product, each with a small mock of the real screen. Labels, reasons and gate names are the
// product's own strings (frontend/lib/copy.ts, backend/app/fraud/reasons.py, fraud/gates.py); queue amounts are
// example values inside a mock, not results.

type Step = { tab: string; title: string; body: string; note: string; Screen: () => ReactNode };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium text-muted">{label}</div>
      {children}
    </div>
  );
}

function ProtectScreen() {
  return (
    <>
      <div className="text-[14px] font-semibold tracking-[-0.01em]">Your transactions</div>
      <div className="mt-3 space-y-3">
        <Field label="File">
          <div className="flex h-9 items-center justify-between rounded-lg border border-border-strong bg-card-2 px-3 text-[12.5px]">
            <span>transactions.csv</span>
            <span className="font-mono text-[11px] text-muted">1.75M rows</span>
          </div>
        </Field>
        <Field label="Cases reviewed per day">
          <div className="flex justify-between text-[11px] text-muted">
            <span>Fewer</span>
            <span>More</span>
          </div>
          <div className="relative mt-2 h-1.5 rounded-full bg-card-3">
            <div className="bg-brand-x absolute inset-y-0 left-0 w-[40%] rounded-full" />
            <div className="absolute top-1/2 left-[40%] size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground shadow-[0_0_0_3px_rgb(10_10_11/0.6)]" />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[11px] text-subtle">
            <span>0</span>
            <span className="text-foreground">200</span>
            <span>500</span>
          </div>
        </Field>
        <div className="flex h-9 items-center rounded-lg border border-border-strong bg-card-2 px-3 text-[12.5px] whitespace-nowrap text-muted">
          Days until fraud is confirmed: <span className="ml-1 text-foreground">30</span>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <span className="text-[12px] whitespace-nowrap text-muted">Try with sample data</span>
        <span className="inline-flex h-8 items-center rounded-lg bg-foreground px-3 text-[12px] whitespace-nowrap font-medium text-background">
          Protect the data
        </span>
      </div>
    </>
  );
}

const QUEUE = [
  { amount: "$2,140.00", reasons: ["Card-testing burst at this terminal", "Unusual amount"] },
  { amount: "$864.50", reasons: ["First payment at this terminal for this card"] },
  { amount: "$412.99", reasons: ["Terminal had recent fraud"] },
];

function QueueScreen() {
  return (
    <>
      <div className="flex items-center justify-between">
        <div className="text-[14px] font-semibold tracking-[-0.01em]">Today&apos;s queue</div>
        <span className="rounded-md bg-card-3 px-2 py-0.5 text-[11px] font-medium text-subtle">200 cases</span>
      </div>
      <div className="mt-3 space-y-2">
        {QUEUE.map((q, i) => (
          <div key={q.amount} className="rounded-lg border border-border-strong bg-card-2 p-2.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[12.5px] tabular-nums">{q.amount}</span>
              <span className="flex gap-1">
                <span
                  className={`rounded-md px-2 py-0.5 text-[10.5px] font-medium ${i === 0 ? "bg-foreground text-background" : "bg-card-3 text-subtle"}`}
                >
                  Fraud
                </span>
                <span className="rounded-md bg-card-3 px-2 py-0.5 text-[10.5px] font-medium text-subtle">Not fraud</span>
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {q.reasons.map((r) => (
                <span key={r} className="rounded-full border border-border-strong px-2 py-px text-[10.5px] text-muted">
                  {r}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

const GATES = ["Hidden data", "Same rows", "Luck test", "No hidden regressions", "Practical"];

function ImproveScreen() {
  return (
    <>
      <div className="flex items-center justify-between">
        <div className="text-[14px] font-semibold tracking-[-0.01em]">Improvement round</div>
        <span className="bg-brand rounded-md px-2 py-0.5 text-[11px] font-semibold text-accent-ink">Promoted to v3</span>
      </div>
      <div className="mt-3 flex items-end justify-between rounded-lg border border-border-strong bg-card-2 px-3 py-2.5">
        <div>
          <div className="text-[11px] text-muted">Caught per day</div>
          <div className="text-gradient mt-0.5 text-[22px] font-semibold tracking-[-0.03em] tabular-nums">$6,543</div>
        </div>
        <div className="text-right text-[11px] text-muted">
          v2 caught
          <div className="font-mono text-[12.5px] text-subtle tabular-nums">$4,840</div>
        </div>
      </div>
      <ul className="mt-3 space-y-1.5">
        {GATES.map((g) => (
          <li key={g} className="flex items-center gap-2 text-[12px] text-subtle">
            <span className="bg-brand grid size-3.5 place-items-center rounded-full" aria-hidden>
              <svg viewBox="0 0 12 12" className="size-2" fill="none">
                <path d="M2.5 6.2l2.2 2.2 4.8-4.8" stroke="#0a0a0b" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            {g}
          </li>
        ))}
      </ul>
    </>
  );
}

const STEPS: Step[] = [
  {
    tab: "Protect",
    title: "Protect the data",
    body: "Upload a CSV and answer three questions. IDs are hashed, card numbers dropped, and leaks and future information caught before any model sees it.",
    note: "Card numbers never reach disk",
    Screen: ProtectScreen,
  },
  {
    tab: "Review",
    title: "Work today's queue",
    body: "Your first model ranks today's payments by expected loss, cut at your team's capacity, with the top three reasons on every case.",
    note: "Every verdict becomes a new label",
    Screen: QueueScreen,
  },
  {
    tab: "Improve",
    title: "Keep getting better",
    body: "Solvers around the world compete to beat your model on days it never saw. A new version is promoted only when it passes all five gates.",
    note: "Public scores never decide",
    Screen: ImproveScreen,
  },
];

const STATS = [
  { icon: "M4 6h16M4 12h16M4 18h10", value: "200", label: "Cases a day, at your capacity" },
  { icon: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3zM9 12l2 2 4-4", value: "5", label: "Gates before any promotion" },
  { icon: "M5 5h14v15H5zM5 9h14M9 3v4M15 3v4", value: "14", label: "Hidden days per comparison" },
  { icon: "M7 11V8a5 5 0 0110 0v3M6 11h12v10H6z", value: "0", label: "Card numbers stored" },
];

/** Diagonal hatching in the outer gutters of the stats row, as in the reference. */
const HATCH = "bg-[repeating-linear-gradient(135deg,var(--border)_0_1px,transparent_1px_9px)]";

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const step = STEPS[active];

  return (
    <section id="how-it-works" aria-labelledby="how-title" className="border-t border-border">
      <div className="px-4 pt-[60px] text-center">
        <p className="inline-flex h-[30px] items-center rounded-md bg-card-2 px-3 font-mono text-[13px] tracking-[0.06em] text-subtle">
          HOW IT WORKS
        </p>
        <h2
          id="how-title"
          className="mx-auto mt-[30px] max-w-[560px] text-[clamp(28px,3.4vw,38px)] leading-[1.18] font-medium tracking-[-0.03em] text-balance"
        >
          Your analysts review the fraud. We keep the model ahead of it.
        </h2>
        <p className="mx-auto mt-4 max-w-[540px] text-[15.5px] leading-[1.4] text-pretty text-muted">
          Your transactions, protected and scored, then ranked into a daily queue your team works, with a model that
          keeps improving behind it.
        </p>
      </div>

      <div className="mx-auto mt-10 grid max-w-[1080px] items-center gap-8 px-4 md:grid-cols-[1fr_426px_1fr] md:gap-10 lg:gap-16">
        <div role="tablist" aria-label="How it works" aria-orientation="vertical" className="flex gap-2 md:flex-col md:gap-[13px] md:justify-self-end">
          {STEPS.map((s, i) => {
            const on = i === active;
            return (
              <button
                key={s.tab}
                role="tab"
                id={`how-tab-${i}`}
                aria-selected={on}
                aria-controls="how-panel"
                onClick={() => setActive(i)}
                className={`flex h-11 flex-1 items-center justify-between gap-3 rounded-lg px-3 text-left text-[15px] tracking-[-0.01em] transition-colors duration-200 md:w-[258px] md:flex-none md:px-[13px] md:text-[18px] ${
                  on ? "bg-card-2 text-foreground" : "bg-card text-muted hover:text-subtle"
                }`}
              >
                {s.tab}
                <span className={`size-[6px] rounded-full ${on ? "bg-brand" : "bg-card-3"}`} aria-hidden />
              </button>
            );
          })}
        </div>

        <div
          role="tabpanel"
          id="how-panel"
          aria-labelledby={`how-tab-${active}`}
          className="relative mx-auto w-full max-w-[426px] overflow-hidden rounded-sm md:min-h-[449px]"
        >
          {/* Brand-gradient backdrop in place of the reference's photograph. */}
          <div
            aria-hidden
            className="anim-drift absolute inset-0 bg-[radial-gradient(120%_80%_at_15%_0%,#fbb39c_0%,transparent_55%),radial-gradient(90%_70%_at_100%_30%,#f472b6_0%,transparent_60%),radial-gradient(110%_90%_at_30%_100%,#818cf8_0%,transparent_60%),radial-gradient(80%_80%_at_85%_95%,#c084fc_0%,transparent_60%),linear-gradient(#2a1640,#131022)]"
          />
          <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_10_11/0.05),rgb(10_10_11/0.35))]" />
          <div className="relative px-[11.5%] pt-[10%] pb-[9%]">
            <div
              key={active}
              className="animate-[fig-in_420ms_cubic-bezier(0.22,1,0.36,1)_both] rounded-[10px] border border-border-strong bg-card p-4 text-left text-foreground shadow-[0_24px_48px_-16px_rgb(10_10_11/0.7)]"
            >
              <step.Screen />
            </div>
            <div className="mt-4 flex h-7 items-center justify-between rounded-full bg-[rgb(10_10_11/0.45)] px-3 text-[12px] text-foreground backdrop-blur-md">
              <span className="flex items-center gap-2">
                <span className="bg-brand size-[6px] rounded-full" aria-hidden />
                {step.note}
              </span>
              <svg viewBox="0 0 24 24" className="size-3.5 text-subtle" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
                <path d="M9 6l6 6-6 6" />
              </svg>
            </div>
          </div>
        </div>

        <div key={active} className="animate-[fig-in_420ms_cubic-bezier(0.22,1,0.36,1)_both] text-center md:max-w-[260px] md:text-left">
          <div className="font-mono text-[14px] text-muted">{String(active + 1).padStart(2, "0")}</div>
          <h3 className="mt-4 text-[23px] font-medium tracking-[-0.02em]">{step.title}</h3>
          <p className="mt-3 text-[15px] leading-[1.6] text-muted">{step.body}</p>
        </div>
      </div>

      <div className="mt-[41px] flex justify-center px-4">
        <a
          href="#contact"
          className="bg-brand-x inline-flex h-[56px] items-center gap-2.5 rounded-xl px-7 text-[17px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          Book a demo
          <ArrowRight className="size-[18px]" />
        </a>
      </div>

      <div className="mt-[61px] grid border-t border-border md:grid-cols-[minmax(0,77px)_1fr_minmax(0,77px)]">
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
        <dl className="grid grid-cols-2 border-border md:grid-cols-4 md:border-x">
          {STATS.map((s, i) => (
            <div
              key={s.label}
              className={`flex flex-col items-center px-3 py-10 text-center md:py-[50px] ${i > 0 ? "md:border-l md:border-border" : ""} ${i % 2 === 1 ? "border-l border-border" : ""} ${i > 1 ? "border-t border-border md:border-t-0" : ""}`}
            >
              <svg
                viewBox="0 0 24 24"
                className="size-5 text-subtle"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.7}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d={s.icon} />
              </svg>
              <dt className="order-last mt-3 text-[15px] text-muted md:text-[17px]">{s.label}</dt>
              <dd className="mt-4 text-[32px] leading-none font-medium tracking-[-0.03em] tabular-nums">{s.value}</dd>
            </div>
          ))}
        </dl>
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
      </div>
    </section>
  );
}
