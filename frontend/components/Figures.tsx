"use client";

import { cx } from "./ui";

const fmt = (x: number) => Math.round(x).toLocaleString("en-US");

/** The lead money figure, as in the reference: a small raised currency sign, the amount, a comparison line under it. */
export function MoneyFigure({ value, suffix, compare, className }: { value: number | null | undefined; suffix?: string; compare?: React.ReactNode; className?: string }) {
  return (
    <div className={cx("min-w-0", className)}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="num pop-in inline-flex items-start text-[44px] leading-none font-medium tracking-[-0.03em] sm:text-[52px]">
          <span className="mt-[0.12em] mr-0.5 text-[0.45em] text-subtle">$</span>
          {value == null ? "–" : fmt(value)}
        </span>
        {suffix ? <span className="text-[14px] text-muted">{suffix}</span> : null}
      </div>
      {compare ? <div className="mt-2 text-[13px] text-muted">{compare}</div> : null}
    </div>
  );
}

type Day = { day: string; caught: number };

/**
 * Fraud caught per day as cylinder bars, as in the reference's revenue chart. With `compare`, each day shows the
 * earlier model in grey next to the current one (only days both were scored on).
 */
export function DailyBars({ days, compare, legend }: { days: Day[]; compare?: Day[] | null; legend?: { current: string; compare?: string } }) {
  if (!days.length) return null;
  const prior = compare ? new Map(compare.map((d) => [d.day, d.caught])) : null;
  const paired = Boolean(prior && days.every((d) => prior.has(d.day)));
  const top = Math.max(1, ...days.map((d) => d.caught), ...(paired ? days.map((d) => prior!.get(d.day) ?? 0) : []));
  const step = top > 8000 ? 2000 : top > 4000 ? 1000 : top > 1500 ? 500 : 250;
  const max = Math.ceil((top * 1.1) / step) * step;
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => max - i * step).filter((t, i, a) => a.length <= 6 || i % 2 === 0 || t === 0);
  const h = (v: number) => Math.max(3, (v / max) * 100);
  const label = (d: string) => new Date(d + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return (
    <div>
      {legend ? (
        <div className="mb-3 flex justify-end gap-4 text-[12px] text-subtle">
          <span className="flex items-center gap-1.5">
            <span className="bg-brand h-2 w-2 rounded-full" />
            {legend.current}
          </span>
          {paired && legend.compare ? (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#55555c]" />
              {legend.compare}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="flex gap-3">
        <div className="relative h-[200px] w-10 shrink-0 text-right">
          {ticks.map((t) => (
            <span key={t} className="num absolute right-0 -translate-y-1/2 text-[11px] leading-none text-muted" style={{ top: `${(1 - t / max) * 100}%` }}>
              {t >= 1000 ? `${(t / 1000).toFixed(t % 1000 ? 1 : 0)}K` : t}
            </span>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div className="relative h-[200px]">
            {ticks.map((t) => (
              <div key={t} className="grid-dash absolute inset-x-0" style={{ top: `${(1 - t / max) * 100}%` }} />
            ))}
            <div className="absolute inset-0 flex items-end justify-around gap-1 px-1">
              {days.map((d) => (
                <div key={d.day} className="flex h-full min-w-0 flex-1 items-end justify-center gap-[3px]" title={`${label(d.day)}: $${fmt(d.caught)}${paired ? ` (was $${fmt(prior!.get(d.day) ?? 0)})` : ""}`}>
                  {paired ? <div className="cyl cyl-grey w-full max-w-[14px]" style={{ height: `${h(prior!.get(d.day) ?? 0)}%` }} /> : null}
                  <div className="cyl cyl-brand w-full max-w-[14px]" style={{ height: `${h(d.caught)}%` }} />
                </div>
              ))}
            </div>
          </div>
          <div className="mt-2.5 flex justify-around gap-1 px-1">
            {days.map((d, i) => (
              <span key={d.day} className={cx("num min-w-0 flex-1 truncate text-center text-[11px] text-muted", i % 2 === 1 && "max-sm:invisible")}>
                <span className="sm:hidden">{Number(d.day.slice(8, 10))}</span>
                <span className="max-sm:hidden">{label(d.day)}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
