"use client";

import { useEffect, useRef, useState } from "react";
import { Check, RotateCcw, ShieldAlert, ShieldCheck } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, PageHeader, Spinner, cx } from "@/components/ui";
import { api, errorText, type ProtectReport } from "@/lib/api";
import { openArenaStream } from "@/lib/sse";
import { fmtCompact, fmtInt, fmtPct } from "@/lib/format";
import { protect as copy } from "@/lib/copy";

const PART_COLOR: Record<string, string> = { train: "var(--c-indigo)", leaderboard: "var(--c-violet)", holdout: "var(--c-pink)" };

export default function ProtectPage() {
  const { project, refresh } = useProject();
  const [report, setReport] = useState<ProtectReport | null | undefined>(project.protect ?? undefined);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const autoRan = useRef(false);
  const v1 = project.versions.find((v) => v.version === 1) ?? null;

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await api.protect(project.id);
      setReport(r);
      setBuilding(true);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (project.protect) {
      setReport(project.protect);
      return;
    }
    api
      .protectReport(project.id)
      .then(setReport)
      .catch(() => {
        setReport(null);
        // Nothing to look at until protection runs, so run it once on arrival.
        if (project.spec && !autoRan.current) {
          autoRan.current = true;
          void run();
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, project.protect]);

  // Version 1 is built right after protection. Listen for it, and poll as a fallback.
  useEffect(() => {
    if (!report || v1) return;
    setBuilding(true);
    const close = openArenaStream(api.streamUrl(project.id), (ev) => {
      if (ev.type === "model_version" || (ev.type === "run_complete" && ev.purpose === "baseline")) void refresh();
    });
    const t = setInterval(() => void refresh(), 4000);
    return () => {
      close();
      clearInterval(t);
    };
  }, [report, v1, project.id, refresh]);

  useEffect(() => {
    if (v1) setBuilding(false);
  }, [v1]);

  const leak = report?.findings.filter((f) => f.severity === "high") ?? [];
  const others = report?.findings.filter((f) => f.severity !== "high") ?? [];
  const total = report?.parts.reduce((a, p) => a + p.rows, 0) ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        title={copy.title}
        actions={
          report ? (
            <Button variant="secondary" busy={running} onClick={() => void run()} disabled={!project.spec}>
              <RotateCcw className="h-3.5 w-3.5" />
              {copy.runAgain}
            </Button>
          ) : null
        }
      >
        {copy.sub}
      </PageHeader>

      {!project.spec ? <Alert kind="warn">{copy.confirmFirst}</Alert> : null}
      {error ? <Alert>{error}</Alert> : null}

      {running || (report === undefined && project.spec) ? (
        <Card>
          <div className="flex items-center gap-3">
            <Spinner className="h-4 w-4 text-pink" />
            <span className="text-[14px] font-medium">{running ? copy.running : copy.looking}</span>
          </div>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {copy.checks.map((c, i) => (
              <li key={c} className="fade-in flex items-center gap-3 rounded-xl border border-border bg-card-2 px-3 py-2.5 text-[13px] text-subtle" style={{ animationDelay: `${i * 60}ms` }}>
                <span className="shimmer h-4 w-4 rounded-full" />
                {c}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {report === null && !running && project.spec ? (
        <Empty icon={<ShieldCheck className="icon-brand h-6 w-6" />}>
          {copy.noReport}
          <div className="mt-4">
            <Button onClick={() => void run()}>{copy.run}</Button>
          </div>
        </Empty>
      ) : null}

      {report && !running ? (
        <>
          {leak.length > 0 ? (
            leak.map((f) => (
              <section key={`${f.check}-${f.column}`} className="pop-in relative overflow-hidden rounded-2xl border border-danger/30 bg-[linear-gradient(180deg,rgb(248_113_113/0.10),rgb(248_113_113/0.02))] p-5 sm:p-7">
                <span aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-danger/15 blur-3xl" />
                <div className="relative flex flex-wrap items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-danger" strokeWidth={1.75} aria-hidden />
                  <Badge tone="danger">{copy.highSeverity}</Badge>
                  <span className="text-[13px] text-[#fca5a5]">{copy.checkLabels[f.check] || f.check}</span>
                </div>
                <div className="num relative mt-4 text-[28px] leading-tight font-medium tracking-[-0.02em] break-all text-[#fecaca] sm:text-[40px]">{f.column}</div>
                <p className="relative mt-3 max-w-3xl text-[16px] leading-relaxed sm:text-[18px]">{copy.cheat}</p>
                <p className="relative mt-2 max-w-3xl text-[13px] leading-relaxed text-subtle">{stripLead(f.reason)}</p>
                <div className="relative mt-5 flex flex-wrap items-center gap-2">
                  <Badge tone="danger">
                    <Check className="h-3 w-3" strokeWidth={3} />
                    {copy.actions[f.action]}
                    {f.action === "dropped" || f.action === "masked" ? copy.beforeAnyone : ""}
                  </Badge>
                  <Evidence evidence={f.evidence} />
                </div>
              </section>
            ))
          ) : (
            <Alert kind="ok">{copy.noLeaks}</Alert>
          )}

          {/* The first model: building, then ready. */}
          {v1 ? (
            <section className="pop-in relative overflow-hidden rounded-2xl border border-border-strong bg-card p-5 sm:p-6">
              <span aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full opacity-[0.18] blur-3xl" style={{ background: "var(--brand-gradient)" }} />
              <div className="relative flex flex-wrap items-center gap-2 text-[12px] font-medium text-subtle">
                <span className="bg-brand flex h-5 w-5 items-center justify-center rounded-full text-background">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                {copy.v1ReadySub}
              </div>
              <div className="relative mt-2 text-[24px] font-semibold tracking-[-0.02em] sm:text-[30px]">{copy.v1Ready}</div>
              <p className="num relative mt-2 text-[15px] text-subtle">{v1.business_value}</p>
            </section>
          ) : building ? (
            <Card>
              <div className="flex items-center gap-3">
                <Spinner className="h-4 w-4 text-pink" />
                <span className="text-[14px] font-medium">{copy.buildingV1}</span>
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-muted">{copy.buildingV1Sub}</p>
            </Card>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-12">
            <Card className="lg:col-span-7" title={copy.howSplit} subtitle={report.strategy === "time" ? copy.byTime : copy.random} actions={<Badge>{copy.seed(report.seed)}</Badge>}>
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
                {report.dropped_columns.map((c) => (
                  <span key={c} className="num rounded-lg border border-dashed border-danger/30 px-2.5 py-1 text-[12px] text-danger/80 line-through decoration-danger/50">
                    {c}
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
                <Mini label={copy.removedLabel} value={report.dropped_columns.length} tone="text-danger" />
                <Mini label={copy.rowsLabel} value={fmtCompact(total)} />
              </div>
            </Card>
          </div>

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
      ) : null}

      <ActionBar hint={v1 ? copy.hintReady : report ? copy.hintBuilding : copy.hintRun}>
        <NextLink stage="model" label={copy.next} disabled={!v1 || running} />
      </ActionBar>
    </div>
  );
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
  return (
    <>
      {parts.map((p) => (
        <span key={p} className="inline-flex h-[22px] items-center rounded-md border border-danger/20 px-2 text-[12px] text-[#fca5a5]">
          {p}
        </span>
      ))}
    </>
  );
}
