"use client";

import { Check } from "lucide-react";
import { FairnessCard } from "@/components/FairnessCard";
import { Alert, Badge, Card, Empty, cx } from "@/components/ui";
import type { MaturitySummary, ProtectReport } from "@/lib/api";
import { fmtCompact, fmtInt, fmtPct } from "@/lib/format";
import { data as dataCopy, protect as copy } from "@/lib/copy";

const PART_COLOR: Record<string, string> = { train: "var(--muted)", leaderboard: "var(--subtle)", holdout: "var(--accent)" };

/** High-severity findings: the leaks that would let a model cheat. Shown big, first. */
export function LeakCards({ report }: { report: ProtectReport }) {
  const leak = report.findings.filter((f) => f.severity === "high");
  return (
    <>
      {leak.length > 0 ? (
        leak.map((f) => (
          <section key={`${f.check}-${f.column}`} className="pop-in rounded-2xl border border-border bg-card p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="danger" dot>
                {copy.highSeverity}
              </Badge>
              <span className="text-[13px] text-subtle">{copy.checkLabels[f.check] || f.check}</span>
            </div>
            <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="num text-[26px] leading-tight font-medium tracking-[-0.02em] break-all sm:text-[34px]">{f.column}</div>
                <p className="mt-2 max-w-3xl text-[15px] leading-relaxed">{copy.cheatByCheck[f.check] ?? copy.cheat}</p>
                <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-muted">{stripLead(f.reason)}</p>
              </div>
              <span className="inline-flex h-7 shrink-0 items-center gap-1.5 self-start rounded-lg bg-card-3 px-2.5 text-[12px] font-medium">
                <Check className="icon-brand h-3.5 w-3.5" strokeWidth={2.5} />
                {copy.actions[f.action]}
                {f.action === "dropped" || f.action === "masked" ? copy.beforeAnyone : ""}
              </span>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-1.5">
              <Evidence evidence={f.evidence} />
            </div>
          </section>
        ))
      ) : (
        <Alert kind="ok">{copy.noLeaks}</Alert>
      )}
    </>
  );
}

/** The split, what the model sees, the fairness check when sensitive columns were set aside, every change. */
export function ProtectionDetails({ report, projectId, version }: { report: ProtectReport; projectId: string; version: number | null }) {
  const others = report.findings.filter((f) => f.severity !== "high");
  const total = report.parts.reduce((a, p) => a + p.rows, 0);
  const aside = new Set(report.set_aside_columns ?? []);
  const v1 = version !== null ? { version } : null;
  const project = { id: projectId, active_model: version !== null ? { version } : null };
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7" title={copy.howSplit} subtitle={report.strategy === "time_embargo" ? copy.byTimeEmbargo(report.maturity?.label_delay_days ?? 30) : report.strategy === "time" ? copy.byTime : report.strategy === "group" && report.group_column ? copy.byGroup(report.group_column) : copy.random} actions={<Badge>{copy.seed(report.seed)}</Badge>}>
          <div className="flex h-9 w-full gap-1 overflow-hidden rounded-xl">
            {report.parts.map((p) => (
              <div key={p.name} className="relative h-full min-w-[28px] transition-[flex-grow] duration-700" style={{ flexGrow: p.rows, background: PART_COLOR[p.name], opacity: 0.85 }}>
                <span className="num absolute inset-0 flex items-center justify-center text-[12px] font-medium text-background">{fmtPct(p.rows / total, 0)}</span>
              </div>
            ))}
          </div>
          <ul className="mt-5 space-y-3">
            {report.parts.map((p) => {
              const part = copy.parts[p.name as keyof typeof copy.parts];
              return (
                <li key={p.name} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: PART_COLOR[p.name] }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                      <span className="text-[14px] font-medium">{part?.title || p.name}</span>
                      <span className="num text-[13px]">
                        {fmtInt(p.rows)} <span className="text-muted">rows · {fmtPct(p.positive_rate, 2)} positive</span>
                      </span>
                    </div>
                    <div className="mt-0.5 text-[12px] text-muted">
                      {part?.who}
                      {p.time_min && p.time_max ? (
                        <span className="num block whitespace-nowrap sm:inline">
                          <span className="hidden sm:inline"> · </span>
                          {p.time_min.slice(0, 10)} to {p.time_max.slice(0, 10)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          {report.rows_removed > 0 ? <p className="mt-4 text-[12px] text-muted">{copy.removedRows(fmtInt(report.rows_removed))}</p> : null}
        </Card>

        <Card className="lg:col-span-5" title={copy.whatSees} subtitle={copy.kept(report.kept_columns.length)}>
          <div className="flex flex-wrap gap-1.5">
            {report.kept_columns.map((c) => (
              <span key={c} className="num rounded-lg border border-border-strong bg-card-2 px-2.5 py-1 text-[12px]">
                {c}
              </span>
            ))}
            {report.dropped_columns.filter((c) => !aside.has(c)).map((c) => (
              <span key={c} className="num rounded-lg border border-dashed border-border-strong px-2.5 py-1 text-[12px] text-muted line-through decoration-muted/60">
                {c}
              </span>
            ))}
            {[...aside].map((c) => (
              <span key={c} title={copy.setAsideTitle} className="num rounded-md border border-dashed border-border-strong px-2.5 py-1 text-[12px] text-subtle">
                {c} · {copy.setAside}
              </span>
            ))}
            {report.masked_columns.map((c) => (
              <span key={c} className="num rounded-lg border border-warn/30 bg-warn-soft px-2.5 py-1 text-[12px] text-warn">
                {c} · {copy.masked}
              </span>
            ))}
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
            <Mini label={copy.keptLabel} value={report.kept_columns.length} />
            <Mini label={copy.removedLabel} value={report.dropped_columns.length - aside.size} tone="text-danger" />
            <Mini label={copy.rowsLabel} value={fmtCompact(total)} />
          </div>
        </Card>
      </div>

      {aside.size > 0 ? <FairnessCard projectId={project.id} columns={[...aside]} version={v1 ? (project.active_model?.version ?? v1.version) : null} /> : null}

      <Card title={copy.everyChange} subtitle={copy.everyChangeSub}>
        {others.length === 0 ? (
          <Empty>{copy.noOther}</Empty>
        ) : (
          <ul className="divide-y divide-border">
            {others.map((f, i) => (
              <li key={i} className="flex flex-col gap-2 py-3.5 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:gap-4">
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", f.severity === "medium" ? "bg-warn" : "bg-muted")} />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {f.column ? <span className="num text-[13px] font-medium">{f.column}</span> : null}
                      <span className="text-[12px] text-muted">{copy.checkLabels[f.check] || f.check}</span>
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-subtle">{f.reason}</p>
                  </div>
                </div>
                <Badge tone={f.severity === "medium" ? "warn" : "neutral"} className="ml-5 self-start sm:ml-0">
                  {copy.actions[f.action]}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

/** Late labels: the windows as one bar (widths are days), a legend with dates, and what was knowable when. */
export function MaturityCard({ m, trainStart }: { m: MaturitySummary; trainStart?: string | null }) {
  const days = (a: string, b: string) => Math.max(1, Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86_400_000) + 1);
  const start = trainStart ? trainStart.slice(0, 10) : null;
  const parts: { key: keyof typeof dataCopy.timeline; from: string | null; to: string; color: string; hatch?: boolean }[] = [
    { key: "train", from: start, to: m.train_end, color: "#55555c" },
    { key: "embargo", from: m.embargo_start, to: m.embargo_end, color: "transparent", hatch: true },
    { key: "leaderboard", from: m.leaderboard_start, to: dayBefore(m.holdout_start), color: "#8a8a92" },
    { key: "holdout", from: m.holdout_start, to: m.holdout_end, color: "brand" },
    { key: "immature", from: m.immature_start, to: m.as_of, color: "#2a2a2f" },
  ];
  const len = parts.map((p) => (p.from ? days(p.from, p.to) : m.label_delay_days * 2));
  const total = len.reduce((a, b) => a + b, 0);
  const short = (d: string) => new Date(d + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return (
    <Card title={dataCopy.maturity} subtitle={dataCopy.maturitySub(m.label_delay_days)}>
      <div className="flex h-3 w-full gap-[3px] overflow-hidden rounded-full" aria-hidden>
        {parts.map((p, i) => (
          <span
            key={p.key}
            className={cx("h-full rounded-[3px]", p.color === "brand" && "bg-brand-x")}
            style={{
              width: `${(len[i] / total) * 100}%`,
              background: p.color === "brand" ? undefined : p.hatch ? "repeating-linear-gradient(135deg, #3a3a40 0 3px, transparent 3px 6px)" : p.color,
            }}
          />
        ))}
      </div>
      <ul className="mt-4 grid gap-x-6 gap-y-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {parts.map((p, i) => (
          <li key={p.key} className="flex items-center gap-2.5">
            <span
              className={cx("h-2 w-2 shrink-0 rounded-full", p.color === "brand" && "bg-brand")}
              style={{ background: p.color === "brand" ? undefined : p.hatch ? "repeating-linear-gradient(135deg, #6e6e74 0 1.5px, transparent 1.5px 3px)" : p.color === "#2a2a2f" ? "#3a3a40" : p.color }}
            />
            <span className="min-w-0 text-[13px]">
              {dataCopy.timeline[p.key]}
              <span className="num ml-1.5 text-[12px] text-muted">
                {p.from ? `${short(p.from)} – ${short(p.to)} · ${len[i]}d` : `${dataCopy.until} ${short(p.to)}`}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <ul className="mt-5 divide-y divide-border border-t border-border">
        <Fact label={dataCopy.factUnconfirmedTrain} value={fmtInt(m.frauds_unconfirmed_in_train)} hint={dataCopy.unconfirmedHint} />
        <Fact label={dataCopy.factUnconfirmedEval} value={fmtInt(m.frauds_unconfirmed_at_eval)} hint={dataCopy.unconfirmedEvalHint} />
        <Fact label={dataCopy.factEmbargo} value={fmtInt(m.embargo_rows)} hint={dataCopy.embargoHint(m.label_delay_days)} />
        {m.analyst_labels ? <Fact label={dataCopy.factAnalyst} value={fmtInt(m.analyst_labels)} hint={dataCopy.analystHint} /> : null}
      </ul>
      <p className="mt-3 text-[12px] leading-relaxed text-muted">{m.label_time_simulated ? dataCopy.simulated : dataCopy.given}</p>
    </Card>
  );
}

function Fact({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <li className="flex items-baseline justify-between gap-4 py-2.5">
      <span className="min-w-0">
        <span className="block text-[13px]">{label}</span>
        <span className="block text-[11px] text-muted">{hint}</span>
      </span>
      <span className="num shrink-0 text-[15px] font-medium">{value}</span>
    </li>
  );
}

function dayBefore(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

function Mini({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div>
      <div className={cx("num text-[20px] leading-none font-medium", tone)}>{value}</div>
      <div className="mt-1.5 text-[11px] text-muted">{label}</div>
    </div>
  );
}

function stripLead(reason: string): string {
  const i = reason.indexOf(": ");
  const lead = reason.toLowerCase().startsWith("this column would let solvers cheat");
  const rest = lead && i > 0 ? reason.slice(i + 2) : reason;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

function Evidence({ evidence }: { evidence?: Record<string, unknown> | null }) {
  if (!evidence) return null;
  const parts: string[] = [];
  if (typeof evidence.single_feature_auc === "number") parts.push(copy.evidence.auc(evidence.single_feature_auc.toFixed(2)));
  if (typeof evidence.unique_ratio === "number") parts.push(copy.evidence.unique(fmtPct(evidence.unique_ratio, 1)));
  if (typeof evidence.post_outcome_name === "string") parts.push(copy.evidence.name(evidence.post_outcome_name));
  if (typeof evidence.entities === "number" && typeof evidence.rows_in_repeats === "number")
    parts.push(copy.evidence.entities(fmtInt(evidence.entities), fmtPct(evidence.rows_in_repeats, 0)));
  return (
    <>
      {parts.map((p) => (
        <span key={p} className="num inline-flex h-[22px] items-center rounded-md bg-card-2 px-2 text-[12px] text-subtle">
          {p}
        </span>
      ))}
    </>
  );
}

