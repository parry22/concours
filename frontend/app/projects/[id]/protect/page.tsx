"use client";

import { useEffect, useRef, useState } from "react";
import { Check, RotateCcw, ShieldAlert, ShieldCheck } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, PageHeader, Spinner, cx } from "@/components/ui";
import { api, errorText, type Finding, type ProtectReport } from "@/lib/api";
import { fmtCompact, fmtInt, fmtPct } from "@/lib/format";

const PART: Record<string, { title: string; who: string; color: string }> = {
  train: { title: "Public train", who: "Solvers get these rows with labels", color: "var(--c-indigo)" },
  leaderboard: { title: "Public leaderboard", who: "Scored live. Labels stay with the referee", color: "var(--c-violet)" },
  holdout: { title: "Private holdout", who: "Decides the winner. Never leaves the referee", color: "var(--c-pink)" },
};

const ACTION_LABEL: Record<Finding["action"], string> = {
  dropped: "Removed",
  masked: "Masked",
  removed_rows: "Rows removed",
  warned: "Kept, warned",
  resplit: "Split again",
};

const CHECK_LABEL: Record<string, string> = {
  target_leak: "Leaks the outcome",
  id_like: "Identifier",
  post_outcome_name: "Post-outcome name",
  duplicate: "Duplicate rows",
  cross_split_duplicates: "Duplicates across splits",
  temporal: "Time order",
  temporal_leak: "Time order",
  constant: "Constant column",
  pii: "Personal data",
};

const CHECKS = ["Outcome leaks", "Identifiers", "Post-outcome names", "Duplicates across splits", "Time order", "Constant columns", "Personal data"];

export default function ProtectPage() {
  const { project, refresh } = useProject();
  const [report, setReport] = useState<ProtectReport | null | undefined>(project.protect ?? undefined);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await api.protect(project.id);
      setReport(r);
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

  const leak = report?.findings.filter((f) => f.severity === "high") ?? [];
  const others = report?.findings.filter((f) => f.severity !== "high") ?? [];
  const total = report?.parts.reduce((a, p) => a + p.rows, 0) ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Protect the data"
        actions={
          report ? (
            <Button variant="secondary" busy={running} onClick={() => void run()} disabled={!project.spec}>
              <RotateCcw className="h-3.5 w-3.5" />
              Run again
            </Button>
          ) : null
        }
      >
        Split so solvers never see the answers they are judged on, then every column checked for leaks and personal data.
      </PageHeader>

      {!project.spec ? <Alert kind="warn">Confirm the scoring rule first.</Alert> : null}
      {error ? <Alert>{error}</Alert> : null}

      {running || (report === undefined && project.spec) ? (
        <Card>
          <div className="flex items-center gap-3">
            <Spinner className="h-4 w-4 text-pink" />
            <span className="text-[14px] font-medium">{running ? "Splitting the data and running seven checks" : "Looking for an earlier report"}</span>
          </div>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {CHECKS.map((c, i) => (
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
          No protection report yet.
          <div className="mt-4">
            <Button onClick={() => void run()}>Run protection</Button>
          </div>
        </Empty>
      ) : null}

      {report && !running ? (
        <>
          {leak.length > 0 ? (
            leak.map((f) => (
              <section
                key={`${f.check}-${f.column}`}
                className="pop-in relative overflow-hidden rounded-2xl border border-danger/30 bg-[linear-gradient(180deg,rgb(248_113_113/0.10),rgb(248_113_113/0.02))] p-5 sm:p-7"
              >
                <span aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-danger/15 blur-3xl" />
                <div className="relative flex flex-wrap items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-danger/15 text-danger">
                    <ShieldAlert className="h-4 w-4" />
                  </span>
                  <Badge tone="danger">High severity</Badge>
                  <span className="text-[13px] text-[#fca5a5]">{CHECK_LABEL[f.check] || f.check}</span>
                </div>
                <div className="num relative mt-4 text-[28px] leading-tight font-medium tracking-[-0.02em] break-all text-[#fecaca] sm:text-[40px]">{f.column}</div>
                <p className="relative mt-3 max-w-3xl text-[16px] leading-relaxed sm:text-[18px]">
                  This column would let solvers cheat: it is only filled in after the outcome is known.
                </p>
                <p className="relative mt-2 max-w-3xl text-[13px] leading-relaxed text-subtle">{stripLead(f.reason)}</p>
                <div className="relative mt-5 flex flex-wrap items-center gap-2">
                  <Badge tone="danger">
                    <Check className="h-3 w-3" strokeWidth={3} />
                    {ACTION_LABEL[f.action]}
                    {f.action === "dropped" || f.action === "masked" ? " before anyone sees it" : ""}
                  </Badge>
                  <Evidence evidence={f.evidence} />
                </div>
              </section>
            ))
          ) : (
            <Alert kind="ok">No column leaks the outcome. Solvers cannot cheat with this data.</Alert>
          )}

          <div className="grid gap-4 lg:grid-cols-12">
            <Card
              className="lg:col-span-7"
              title="How the data was split"
              subtitle={report.strategy === "time" ? "By time, oldest first, so solvers never see the future." : "Random, with the same outcome share in every part."}
              actions={<Badge>seed {report.seed}</Badge>}
            >
              <div className="flex h-9 w-full gap-1 overflow-hidden rounded-xl">
                {report.parts.map((p) => (
                  <div
                    key={p.name}
                    className="relative h-full min-w-[28px] transition-[flex-grow] duration-700"
                    style={{ flexGrow: p.rows, background: PART[p.name]?.color, opacity: 0.85 }}
                  >
                    <span className="num absolute inset-0 flex items-center justify-center text-[12px] font-medium text-background">{fmtPct(p.rows / total, 0)}</span>
                  </div>
                ))}
              </div>
              <ul className="mt-5 space-y-3">
                {report.parts.map((p) => (
                  <li key={p.name} className="flex items-start gap-3">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: PART[p.name]?.color }} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                        <span className="text-[14px] font-medium">{PART[p.name]?.title || p.name}</span>
                        <span className="num text-[13px]">
                          {fmtInt(p.rows)} <span className="text-muted">rows · {fmtPct(p.positive_rate, 2)} positive</span>
                        </span>
                      </div>
                      <div className="mt-0.5 text-[12px] text-muted">
                        {PART[p.name]?.who}
                        {p.time_min && p.time_max ? (
                          <span className="num block whitespace-nowrap sm:inline">
                            <span className="hidden sm:inline"> · </span>
                            {p.time_min.slice(0, 10)} to {p.time_max.slice(0, 10)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              {report.rows_removed > 0 ? (
                <p className="mt-4 text-[12px] text-muted">{fmtInt(report.rows_removed)} rows removed from train because they also appear in the holdout.</p>
              ) : null}
            </Card>

            <Card className="lg:col-span-5" title="What solvers will see" subtitle={`${report.kept_columns.length} columns kept in the public training set.`}>
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
                    {c} · masked
                  </span>
                ))}
              </div>
              <div className="mt-5 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                <Mini label="Kept" value={report.kept_columns.length} />
                <Mini label="Removed" value={report.dropped_columns.length} tone="text-danger" />
                <Mini label="Rows" value={fmtCompact(total)} />
              </div>
            </Card>
          </div>

          <Card title="Every change, with the reason" subtitle="Automatic fixes beyond the leak above.">
            {others.length === 0 ? (
              <Empty>No other changes were needed.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {others.map((f, i) => (
                  <li key={i} className="flex flex-col gap-2 py-3.5 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:gap-4">
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", f.severity === "medium" ? "bg-warn" : "bg-muted")} />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          {f.column ? <span className="num text-[13px] font-medium">{f.column}</span> : null}
                          <span className="text-[12px] text-muted">{CHECK_LABEL[f.check] || f.check}</span>
                        </div>
                        <p className="mt-1 text-[13px] leading-relaxed text-subtle">{f.reason}</p>
                      </div>
                    </div>
                    <Badge tone={f.severity === "medium" ? "warn" : "neutral"} className="ml-5 self-start sm:ml-0">
                      {ACTION_LABEL[f.action]}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      ) : null}

      <ActionBar hint={report ? "The data is safe to share. Next, local solvers compete on it." : "Protection runs in a few seconds."}>
        <NextLink stage="arena" label="Open the arena" disabled={!report || running} />
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
  if (typeof evidence.single_feature_auc === "number") parts.push(`Alone it predicts the outcome with AUC ${evidence.single_feature_auc.toFixed(2)}`);
  if (typeof evidence.unique_ratio === "number") parts.push(`${fmtPct(evidence.unique_ratio, 1)} unique`);
  if (typeof evidence.post_outcome_name === "string") parts.push(`Name contains “${evidence.post_outcome_name}”`);
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
