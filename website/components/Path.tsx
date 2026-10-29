import { LogoMark } from "./Logo";

// The reference's "90-day build" timeline, told as the product's real steps (CONCOURS.md: setup, protect, v1,
// improvement rounds, promotion). No day counts: only "the same sitting" for v1 is documented, so later steps
// carry no dates. The curve is illustrative and carries no values.

const STEPS = [
  { tag: "STEP 1", label: "Upload and map" },
  { tag: "STEP 2", label: "Data protected" },
  { tag: "STEP 3", label: "Model v1 and queue" },
  { tag: "STEP 4", label: "Improvement rounds" },
  { tag: "STEP 5", label: "New versions, yours" },
];

const W = 1000;
const H = 433;
const BASE = 80; // curve height above the bottom at the start

function curveY(x: number) {
  return H - (BASE + (H - BASE) * Math.pow(x / W, 1.7));
}

function curvePath(from: number, to: number) {
  const pts: string[] = [];
  for (let x = from; x <= to; x += 10) pts.push(`${x} ${curveY(x).toFixed(1)}`);
  return `M${pts.join("L")}`;
}

const HATCH = "bg-[repeating-linear-gradient(135deg,var(--border)_0_1px,transparent_1px_9px)]";

function Chart() {
  const first = W / STEPS.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="path-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c084fc" stopOpacity="0.1" />
          <stop offset="1" stopColor="#c084fc" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="path-first" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f472b6" stopOpacity="0.75" />
          <stop offset="1" stopColor="#fbb39c" stopOpacity="0.08" />
        </linearGradient>
        <linearGradient id="path-stroke" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      <path d={`${curvePath(0, W)}L${W} ${H}L0 ${H}Z`} fill="url(#path-area)" />
      <path d={curvePath(0, W)} pathLength={1} className="anim-draw" fill="none" stroke="var(--border-strong)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <path d={`${curvePath(0, first)}L${first} ${H}L0 ${H}Z`} fill="url(#path-first)" />
      <path d={curvePath(0, first)} fill="none" stroke="url(#path-stroke)" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Rendered twice (phone and desktop placement), so each copy needs its own gradient ids. */
function Intro({ id }: { id: string }) {
  return (
    <div>
      <LogoMark id={id} className="h-[42px] w-[32px] overflow-visible" />
      <h3 className="mt-5 text-[23px] font-semibold tracking-[-0.025em]">Start with your transactions</h3>
      <ul className="mt-5 space-y-3 text-[15.5px] text-subtle">
        {["You upload payments with a fraud label", "We protect the data and build your first model"].map((b) => (
          <li key={b} className="flex items-center gap-3">
            <span className="bg-brand size-2 shrink-0 rounded-[2px]" aria-hidden />
            {b}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Path() {
  return (
    <section aria-labelledby="path-title" className="border-t border-border">
      <div className="px-4 pt-[60px] pb-[52px] text-center">
        <p className="inline-flex h-[29px] items-center gap-2.5 rounded-md border border-border-strong bg-card-2 px-3 font-mono text-[12.5px] leading-none tracking-[0.06em] text-subtle">
          <span className="bg-brand size-[7px] rounded-full" aria-hidden />
          THE PATH
        </p>
        <h2
          id="path-title"
          className="mx-auto mt-5 max-w-[440px] text-[clamp(30px,3.4vw,40px)] leading-[1.15] font-medium tracking-[-0.03em] text-balance"
        >
          From a CSV to a model that keeps improving
        </h2>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] border-t border-border md:grid-cols-[54px_minmax(0,1fr)_54px]">
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
        <div className="md:border-x md:border-border">
          {/* On phones the intro sits above the chart; from md it overlays the first columns as in the reference. */}
          <div className="border-b border-border px-5 py-8 md:hidden">
            <Intro id="path-logo-sm" />
          </div>
          <div className="no-scrollbar overflow-x-auto">
            <div className="relative h-[433px] min-w-[720px]">
              <Chart />
              <div className="absolute inset-0 grid grid-cols-5">
                {STEPS.map((s, i) => (
                  <div key={s.tag} className={`flex flex-col justify-end px-5 pb-[18px] ${i > 0 ? "border-l border-border" : ""}`}>
                    <span className={`font-mono text-[12px] tracking-[0.1em] ${i === 0 ? "text-foreground/70" : "text-muted"}`}>{s.tag}</span>
                    <span className={`mt-1 text-[15.5px] font-medium ${i === 0 ? "text-foreground" : "text-subtle"}`}>{s.label}</span>
                  </div>
                ))}
              </div>
              <div className="absolute top-[42px] left-[41px] hidden md:block">
                <Intro id="path-logo-md" />
              </div>
            </div>
          </div>
        </div>
        <div aria-hidden className={`hidden md:block ${HATCH}`} />
      </div>
      <div className="h-[60px] border-t border-border" aria-hidden />
    </section>
  );
}
