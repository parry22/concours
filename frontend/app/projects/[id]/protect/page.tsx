"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NextStep, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, Loading } from "@/components/ui";
import { api, errorText, type Finding, type ProtectReport } from "@/lib/api";
import { fmtInt, fmtPct } from "@/lib/format";

const PART_LABEL: Record<string, { title: string; who: string }> = {
  train: { title: "Public train", who: "Solvers get these rows with labels" },
  leaderboard: { title: "Public leaderboard", who: "Scores shown during the round. Labels stay with the referee" },
  holdout: { title: "Private holdout", who: "Decides the winner. Never leaves the referee" },
};

const ACTION_LABEL: Record<Finding["action"], string> = {
  dropped: "Removed the column",
  masked: "Masked the values",
  removed_rows: "Removed the rows",
  warned: "Kept, with a warning",
  resplit: "Split the data again",
};

const CHECK_LABEL: Record<string, string> = {
  target_leak: "Leaks the outcome",
  id_like: "Identifier",
  post_outcome_name: "Post-outcome name",
  duplicate: "Duplicate rows",
  cross_split_duplicates: "Duplicate rows across splits",
  temporal: "Time order",
  temporal_leak: "Time order",
  constant: "Constant column",
  pii: "Personal data",
};

export default function ProtectPage() {
  const { project, refresh } = useProject();
  const [report, setReport] = useState<ProtectReport | null | undefined>(project.protect ?? undefined);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (project.protect) {
      setReport(project.protect);
      return;
    }
    api.protectReport(project.id).then(setReport).catch(() => setReport(null));
  }, [project.id, project.protect]);

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

  const leak = report?.findings.filter((f) => f.severity === "high") ?? [];
  const others = report?.findings.filter((f) => f.severity !== "high") ?? [];
  const chartData = report?.parts.map((p) => ({ name: PART_LABEL[p.name]?.title || p.name, rows: p.rows, positives: p.positives })) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Protect the data</h1>
          <p className="mt-1 max-w-2xl text-muted">
            Brief splits the data into a public training set, a public leaderboard slice and a private holdout, then checks every
            column for anything that would let a solver cheat or expose a person.
          </p>
        </div>
        <Button busy={running} onClick={() => void run()} disabled={!project.spec}>
          {report ? "Run protection again" : "Run protection"}
        </Button>
      </div>

      {!project.spec ? <Alert kind="warn">Confirm the problem spec first.</Alert> : null}
      {error ? <Alert>{error}</Alert> : null}
      {running ? <Loading label="Splitting the data and running seven checks. This takes a few seconds." /> : null}

      {report === undefined && !running ? <Loading label="Checking for an earlier report" /> : null}
      {report === null && !running ? <Empty>No protection report yet. Run protection to split the data and check for leaks.</Empty> : null}

      {report ? (
        <>
          {leak.length > 0 ? (
            leak.map((f) => (
              <div key={`${f.check}-${f.column}`} className="pop-in rounded-2xl border-2 border-danger/40 bg-danger-soft p-8">
                <div className="flex items-center gap-3">
                  <Badge tone="danger">High severity</Badge>
                  <span className="text-sm text-danger">{CHECK_LABEL[f.check] || f.check}</span>
                </div>
                <div className="mt-4 font-mono text-4xl font-semibold tracking-tight text-danger break-all">{f.column}</div>
                <p className="mt-4 max-w-3xl text-lg text-foreground">
                  This column would let solvers cheat: it is only filled in after the outcome is known.
                </p>
                <p className="mt-2 max-w-3xl text-sm text-muted">{stripLead(f.reason)}</p>
                <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
                  <Badge tone="danger">{ACTION_LABEL[f.action]}</Badge>
                  {f.evidence ? <Evidence evidence={f.evidence} /> : null}
                </div>
              </div>
            ))
          ) : (
            <Alert kind="ok">No column leaks the outcome. Solvers cannot cheat with this data.</Alert>
          )}

          <Card
            title="How the data was split"
            subtitle={
              report.strategy === "time"
                ? `Split by time, oldest rows first, so solvers never see the future. Seed ${report.seed}.`
                : `Random split with the same share of positives in every part. Seed ${report.seed}.`
            }
          >
            <div className="grid gap-6 lg:grid-cols-5">
              <div className="grid gap-3 lg:col-span-3">
                {report.parts.map((p) => (
                  <div key={p.name} className="rounded-xl border border-border px-4 py-3">
                    <div className="flex items-baseline justify-between gap-4">
                      <div className="font-medium">{PART_LABEL[p.name]?.title || p.name}</div>
                      <div className="text-sm tabular-nums">
                        {fmtInt(p.rows)} rows, {fmtPct(p.positive_rate, 2)} positive ({fmtInt(p.positives)})
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-muted">
                      {PART_LABEL[p.name]?.who}
                      {p.time_min && p.time_max ? `. ${p.time_min} to ${p.time_max}` : ""}
                    </div>
                  </div>
                ))}
                {report.rows_removed > 0 ? <p className="text-xs text-muted">{fmtInt(report.rows_removed)} rows removed from train because they also appear in the holdout.</p> : null}
              </div>
              <div className="h-48 lg:col-span-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => fmtInt(v)} width={56} />
                    <Tooltip formatter={(v) => fmtInt(Number(v))} cursor={{ fill: "var(--accent-soft)" }} />
                    <Bar dataKey="rows" name="Rows" fill="var(--accent)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Card>

          <Card title="Other findings" subtitle="Every automatic change, with the reason.">
            {others.length === 0 ? (
              <Empty>No other changes were needed.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {others.map((f, i) => (
                  <li key={i} className="flex flex-wrap items-start gap-4 py-3">
                    <Badge tone={f.severity === "medium" ? "warn" : "neutral"} className="mt-0.5 w-24 justify-center">
                      {f.severity === "medium" ? "Medium" : "Info"}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {f.column ? <span className="font-mono text-sm font-medium">{f.column}</span> : null}
                        <span className="text-xs text-muted">{CHECK_LABEL[f.check] || f.check}</span>
                      </div>
                      <p className="mt-1 text-sm">{f.reason}</p>
                    </div>
                    <Badge tone="neutral">{ACTION_LABEL[f.action]}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="What solvers will see" subtitle="Columns kept in the public training set.">
            <div className="flex flex-wrap gap-2">
              {report.kept_columns.map((c) => (
                <span key={c} className="rounded-lg bg-stone-100 px-2.5 py-1 font-mono text-xs">
                  {c}
                </span>
              ))}
            </div>
            {report.dropped_columns.length > 0 ? (
              <p className="mt-3 text-xs text-muted">Removed: {report.dropped_columns.join(", ")}</p>
            ) : null}
            {report.masked_columns.length > 0 ? <p className="mt-1 text-xs text-muted">Masked: {report.masked_columns.join(", ")}</p> : null}
          </Card>
        </>
      ) : null}

      <NextStep stage="arena" />
    </div>
  );
}

function stripLead(reason: string): string {
  const i = reason.indexOf(": ");
  const lead = reason.toLowerCase().startsWith("this column would let solvers cheat");
  const rest = lead && i > 0 ? reason.slice(i + 2) : reason;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const parts: string[] = [];
  if (typeof evidence.single_feature_auc === "number") parts.push(`on its own it predicts the outcome with ${fmtPct(evidence.single_feature_auc, 1)} accuracy`);
  if (typeof evidence.unique_ratio === "number") parts.push(`${fmtPct(evidence.unique_ratio, 1)} of values are unique`);
  if (typeof evidence.post_outcome_name === "string") parts.push(`the name contains "${evidence.post_outcome_name}"`);
  if (parts.length === 0) return null;
  return <span className="text-muted">Evidence: {parts.join("; ")}.</span>;
}
