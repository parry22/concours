import { DotField } from "./DotField";
import { EmailForm } from "./EmailForm";
import { StackDiagram } from "./StackDiagram";
import { StackOpener } from "./StackOpener";

// Brand-coloured dots that blink inside the halftone field at the edges, out of step with each other.
const TWINKLES = [
  { x: "4%", y: "22%", c: "var(--c-peach)", d: 0 },
  { x: "9%", y: "64%", c: "var(--c-pink)", d: -1.1 },
  { x: "15%", y: "38%", c: "var(--c-indigo)", d: -2.3 },
  { x: "6%", y: "84%", c: "var(--c-orchid)", d: -0.6 },
  { x: "93%", y: "18%", c: "var(--c-pink)", d: -1.7 },
  { x: "88%", y: "52%", c: "var(--c-peach)", d: -0.3 },
  { x: "96%", y: "70%", c: "var(--c-violet)", d: -2.6 },
  { x: "84%", y: "88%", c: "var(--c-indigo)", d: -1.4 },
];

function Twinkles() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {TWINKLES.map((t) => (
        <span
          key={t.x + t.y}
          className="anim-twinkle absolute size-[5px] rounded-[1px]"
          style={{ left: t.x, top: t.y, background: t.c, animationDelay: `${t.d}s` }}
        />
      ))}
    </div>
  );
}

// On phones the diagram is cropped to the stack, so its inputs and outputs are listed here instead.
const FLOW = [
  { tag: "IN", items: [
    { label: "TRANSACTIONS", dot: "var(--muted)" },
    { label: "YOUR STACK", dot: "var(--foreground)" },
    { label: "LABELS", dot: "var(--muted)" },
  ] },
  { tag: "OUT", items: [
    { label: "REVIEW QUEUE", dot: "", brand: true },
    { label: "NEW VERSIONS", dot: "var(--muted)" },
  ] },
] as { tag: string; items: { label: string; dot: string; brand?: boolean }[] }[];

function PhoneFlow() {
  return (
    <div className="relative mt-1 space-y-3 px-4 md:hidden">
      {FLOW.map((row) => (
        <div key={row.tag} className="flex flex-col items-center gap-1.5">
          <span className="font-mono text-[10px] tracking-[0.12em] text-muted">{row.tag}</span>
          <div className="flex flex-wrap justify-center gap-1.5">
          {row.items.map((it) => (
            <span
              key={it.label}
              className={`inline-flex h-8 items-center gap-1.5 rounded-full px-2.5 font-mono text-[10.5px] tracking-[0.04em] whitespace-nowrap ${
                it.brand ? "bg-brand-x text-accent-ink" : "border border-border-strong bg-card-2 text-subtle"
              }`}
            >
              {!it.brand && <span className="size-1.5 rounded-[1px]" style={{ background: it.dot }} aria-hidden />}
              {it.label}
            </span>
          ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Hero() {
  return (
    <section aria-labelledby="hero-title">
      <div className="px-4 pt-10 pb-[45px] text-center">
        <p className="inline-flex h-[29px] items-center gap-2.5 rounded-md border border-border-strong bg-card-2 px-3 font-mono text-[10.5px] leading-none tracking-[0.04em] whitespace-nowrap text-subtle sm:text-[12.5px] sm:tracking-[0.06em]">
          <span className="bg-brand size-[7px] rounded-full" aria-hidden />
          PAYMENT FRAUD MODELS, LIVE ON DAY ONE
        </p>
        <h1
          id="hero-title"
          className="mx-auto mt-[22px] max-w-[880px] text-[clamp(42px,6.3vw,76px)] leading-[0.98] font-semibold tracking-[-0.045em] text-balance text-foreground"
        >
          Fraud models that keep up with fraudsters.
        </h1>
        <p className="mx-auto mt-[28px] max-w-[600px] text-[clamp(16px,1.55vw,19px)] leading-[1.5] tracking-[-0.01em] text-pretty text-subtle">
          Get a working fraud model and a daily review queue today. A global network of solvers keeps improving it as
          fraud changes.
        </p>
        <div className="mt-7">
          <EmailForm />
        </div>
      </div>

      <div className="relative overflow-hidden border-t border-border py-[36px] md:py-[48px]">
        <DotField />
        <Twinkles />
        <StackDiagram className="hidden md:block" />
        <StackDiagram compact className="block md:hidden" />
        <StackOpener />
        <PhoneFlow />
      </div>
    </section>
  );
}
