"use client";

import { useState } from "react";

// Every answer restates the product as documented in CONCOURS.md and frontend/lib/copy.ts. Keep it that way:
// if the product changes, change the answer, and never promise a result the product does not measure.

const FAQ: { q: string; a: string }[] = [
  {
    q: "What does Concours actually do?",
    a: "It turns your payment history into a working fraud model and a daily review queue, then keeps improving that model through a private competition among a global network of solvers.",
  },
  {
    q: "What data do we need?",
    a: "A CSV of payments with a transaction ID, time, amount, customer ID and a fraud label. Merchant or terminal, currency and the date fraud was confirmed are optional. Columns are suggested by name.",
  },
  {
    q: "How soon do we see something?",
    a: "In the same sitting. Once the data is protected, your first model builds and today's review queue is ready, before any competition starts.",
  },
  {
    q: "What happens to our data?",
    a: "IDs are hashed with a salt unique to your project, card numbers are dropped and never reach disk, uploads are encrypted at rest, and the raw upload is deleted once the columns are confirmed.",
  },
  {
    q: "Who sees our data in the competition?",
    a: "Only invited solvers, and only protected training rows: scrambled IDs, no card numbers. The private test days and their labels are left out.",
  },
  {
    q: "How is a new version approved?",
    a: "It has to pass five gates on the private holdout: scored on hidden data, compared on the same rows, a luck test over 1,000 resamples, no segment dropping more than 5%, and fast enough to score 10,000 payments in under five seconds.",
  },
  {
    q: "Can you guarantee how much fraud we'll catch?",
    a: "No. Every figure is measured on recent days the model never saw, inside your team's review capacity. A new version is only promoted when it beats the current one there.",
  },
  {
    q: "Is this real-time scoring?",
    a: "No. Concours delivers a daily review queue sized to your team's capacity. Real-time scoring is out of scope.",
  },
  {
    q: "Do we own the models?",
    a: "Yes. Every promoted version and its code are yours.",
  },
  {
    q: "Does it replace our analysts?",
    a: "No. It decides which payments they look at first and shows why. Their verdicts become the labels the next version learns from.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" aria-labelledby="faq-title" className="border-t border-border px-4 pt-[60px] pb-[42px]">
      <h2 id="faq-title" className="text-center text-[clamp(30px,3.4vw,40px)] font-medium tracking-[-0.03em]">
        Frequently asked questions
      </h2>
      <ul className="mx-auto mt-10 max-w-[715px] space-y-[14px]">
        {FAQ.map((f, i) => {
          const on = open === i;
          return (
            <li key={f.q} className={`rounded-xl border transition-colors duration-200 ${on ? "border-border-strong bg-card-2" : "border-border bg-card"}`}>
              <button
                type="button"
                aria-expanded={on}
                aria-controls={`faq-a-${i}`}
                id={`faq-q-${i}`}
                onClick={() => setOpen(on ? null : i)}
                className="flex min-h-[66px] w-full items-center justify-between gap-6 px-5 py-4 text-left text-[17px] font-medium tracking-[-0.015em] text-foreground"
              >
                {f.q}
                <svg
                  viewBox="0 0 24 24"
                  className={`size-5 shrink-0 text-subtle transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${on ? "rotate-45" : ""}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  strokeLinecap="round"
                  aria-hidden
                >
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
              <div
                id={`faq-a-${i}`}
                role="region"
                aria-labelledby={`faq-q-${i}`}
                className={`grid transition-[grid-template-rows] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${on ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
              >
                <div className="overflow-hidden">
                  <p className="px-5 pb-5 text-[15.5px] leading-[1.6] text-subtle md:pr-14">{f.a}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
