import { DotField } from "./DotField";
import { ArrowRight } from "./icons";
import { LogoMark } from "./Logo";

// Closing call to action, then a strip in place of the reference's star rating. Concours has no ratings or
// customer count to show, so the strip states how results are measured (CONCOURS.md principles).

const HATCH = "bg-[repeating-linear-gradient(135deg,var(--border)_0_1px,transparent_1px_9px)]";

/** Laurel sprig drawn as leaf pairs along a curve; mirrored for the right side. */
function Laurel({ flip = false }: { flip?: boolean }) {
  const leaves = [0, 1, 2, 3, 4];
  return (
    <svg viewBox="0 0 24 52" className={`h-12 w-6 text-border-strong ${flip ? "-scale-x-100" : ""}`} fill="currentColor" aria-hidden>
      <path d="M14 50C8 40 7 22 14 4" fill="none" stroke="currentColor" strokeWidth="1.4" />
      {leaves.map((i) => {
        const y = 44 - i * 9;
        return (
          <g key={i}>
            <ellipse cx={8.5 + i * 0.6} cy={y} rx="2.4" ry="5" transform={`rotate(-35 ${8.5 + i * 0.6} ${y})`} />
            <ellipse cx={17 - i * 0.2} cy={y - 3} rx="2.2" ry="4.6" transform={`rotate(35 ${17 - i * 0.2} ${y - 3})`} />
          </g>
        );
      })}
    </svg>
  );
}

export function FinalCta() {
  return (
    <section aria-labelledby="final-title" className="border-t border-border">
      <div className="grid md:grid-cols-[146px_minmax(0,1fr)_146px]">
        <div className="relative hidden overflow-hidden md:block">
          <DotField />
        </div>
        <div className="relative overflow-hidden border-border px-5 pt-[86px] pb-[60px] text-center md:border-x">
          <div aria-hidden className="anim-breathe absolute top-[40px] left-1/2 h-[260px] w-[420px] -translate-x-1/2 bg-[radial-gradient(closest-side,rgb(244_114_182/0.22),transparent)]" />
          <div className="anim-float-slow relative mx-auto grid size-[108px] place-items-center rounded-[28px] border border-border-strong bg-card shadow-[0_0_0_6px_rgb(244_114_182/0.06),0_18px_50px_-10px_rgb(244_114_182/0.45)]">
            <div
              aria-hidden
              className="absolute inset-[10px] rounded-[20px] bg-[linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] bg-[length:11px_11px] opacity-70"
            />
            <LogoMark id="final-logo" className="relative h-[52px] w-[40px] overflow-visible" />
          </div>
          <h2
            id="final-title"
            className="relative mx-auto mt-[52px] max-w-[460px] text-[clamp(30px,3.4vw,40px)] leading-[1.13] font-medium tracking-[-0.03em] text-balance"
          >
            Start today&apos;s queue from your own payments.
          </h2>
          <p className="relative mx-auto mt-5 max-w-[400px] text-[16px] leading-[1.4] text-pretty text-subtle">
            You get a working model and today&apos;s review queue in the same sitting, and a network that keeps
            improving it.
          </p>
          <a
            href="/app/signup"
            className="bg-brand-x relative mt-9 inline-flex h-[56px] items-center gap-2.5 rounded-xl px-7 text-[17px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
          >
            Get started
            <ArrowRight className="size-[18px]" />
          </a>
        </div>
        <div className="relative hidden overflow-hidden md:block">
          <DotField />
        </div>
      </div>

      <div className="grid border-t border-border md:grid-cols-[146px_minmax(0,1fr)_146px]">
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
        <div className="flex items-center justify-center gap-4 border-border px-5 py-8 md:border-x">
          <Laurel />
          <div className="flex items-center gap-4 text-left">
            <span className="text-gradient text-[30px] leading-none font-semibold tracking-[-0.03em] tabular-nums">5</span>
            <span className="text-[15.5px] leading-[1.35] text-subtle">
              gates on hidden days
              <br />
              <span className="text-foreground">before any version is promoted</span>
            </span>
          </div>
          <Laurel flip />
        </div>
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
      </div>
    </section>
  );
}
