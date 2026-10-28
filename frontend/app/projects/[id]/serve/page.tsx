"use client";

import { useRef, useState } from "react";
import { Download, Sparkles, Trophy, Upload } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Card, Empty, LinkButton, Meter, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api, errorText, type ScoreOut } from "@/lib/api";
import { fmtCell, fmtInt, fmtPct, solverLabel } from "@/lib/format";

export default function ServePage() {
  const { project, refresh } = useProject();
  const [result, setResult] = useState<ScoreOut | null>(null);
  const [busy, setBusy] = useState<"upload" | "sample" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function score(file: File, mode: "upload" | "sample") {
    setBusy(mode);
    setError(null);
    try {
      const r = await api.score(project.id, file);
      setResult(r);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function scoreSample() {
    setBusy("sample");
    setError(null);
    try {
      const f = await api.sampleCsv(project.id, 2000);
      await score(f, "sample");
    } catch (e) {
      setError(errorText(e));
      setBusy(null);
    }
  }

  const spec = project.spec;
  const winner = project.winner_solver || result?.solver;
  const thresholdText = explainThreshold(spec?.primary_metric, spec?.metric_params as Record<string, unknown> | undefined, spec?.business_template);
  const otherCols = result ? result.columns.filter((c) => c !== "score" && c !== "flag") : [];

  return (
    <div className="space-y-5">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void score(f, "upload");
          e.target.value = "";
        }}
      />
      <PageHeader
        title="Use the winner"
        actions={
          winner ? (
            <span className="inline-flex h-8 items-center gap-2 rounded-full border border-border-strong bg-card-2 pr-3 pl-1 text-[12px] font-medium">
              <span className="flex h-6 w-6 items-center justify-center rounded-full text-background" style={{ background: "var(--brand-gradient)" }}>
                <Trophy className="h-3 w-3" />
              </span>
              {solverLabel(winner)}
            </span>
          ) : null
        }
      >
        The winning model scores new rows and flags the ones to act on.
      </PageHeader>

      {!project.finalized ? <Alert kind="warn">Finalize the arena first so there is a winner to use.</Alert> : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          onClick={() => void scoreSample()}
          disabled={busy !== null || !project.finalized}
          className="group relative flex items-start gap-4 overflow-hidden rounded-2xl border border-border-strong bg-card p-4 text-left transition-colors hover:bg-[#161618] disabled:cursor-not-allowed disabled:opacity-60 sm:p-5"
        >
          <span aria-hidden className="pointer-events-none absolute -top-20 -right-20 h-44 w-44 rounded-full opacity-[0.12] blur-2xl" style={{ background: "var(--brand-gradient)" }} />
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-foreground text-background">
            {busy === "sample" ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
          </span>
          <span className="relative min-w-0">
            <span className="flex items-center gap-2 text-[14px] font-medium">
              Score sample rows <Badge tone="accent">Quickest</Badge>
            </span>
            <span className="mt-1 block text-[13px] leading-relaxed text-muted">2,000 recent rows the solvers never trained on, without the outcome column.</span>
          </span>
        </button>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy !== null || !project.finalized}
          className="flex items-start gap-4 rounded-2xl border border-dashed border-border-strong bg-card p-4 text-left transition-colors hover:bg-[#161618] disabled:cursor-not-allowed disabled:opacity-60 sm:p-5"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border-strong bg-card-2">
            {busy === "upload" ? <Spinner className="h-4 w-4" /> : <Upload className="h-4 w-4" />}
          </span>
          <span className="min-w-0">
            <span className="block text-[14px] font-medium">Upload a CSV to score</span>
            <span className="mt-1 block text-[13px] leading-relaxed text-muted">Same columns as the training data. The outcome column is not needed.</span>
          </span>
        </button>
      </div>

      {error ? <Alert>{error}</Alert> : null}
      {busy ? (
        <p className="flex items-center gap-2 text-[13px] text-muted">
          <Spinner className="h-3.5 w-3.5" /> Fitting the winner on the training split and scoring the rows. A few seconds.
        </p>
      ) : null}

      {result ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Stat label="Rows scored" value={fmtInt(result.rows)} />
            <Stat
              label="Flagged to act on"
              value={<span className="text-pink">{fmtInt(result.flagged)}</span>}
              hint={
                result.rows > 0 ? (
                  <span className="flex items-center gap-2">
                    <Meter value={Math.max(result.flagged / result.rows, 0.01)} color="var(--c-pink)" className="h-1.5 w-16" />
                    <span className="num">{fmtPct(result.flagged / result.rows, 2)}</span>
                  </span>
                ) : undefined
              }
            />
            <Stat className="col-span-2 lg:col-span-1" label="Threshold" value={result.threshold.toFixed(4)} hint={thresholdText} />
          </div>

          <Card
            pad={false}
            title="Scored rows"
            subtitle="Two columns added: score, the chance a row is positive, and flag, set when the score is above the threshold."
            actions={
              <LinkButton href={api.scoreDownloadUrl(project.id)} download="scored.csv" variant="secondary" size="sm">
                <Download className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Download CSV</span>
              </LinkButton>
            }
          >
            <div className="scroll-thin overflow-x-auto border-t border-border">
              <table className="min-w-full border-separate border-spacing-0 text-left text-[12px]">
                <thead>
                  <tr className="text-muted">
                    <th className="sticky left-0 z-10 bg-card px-4 py-2.5 font-medium sm:px-5">Flag</th>
                    <th className="px-3 py-2.5 font-medium">Score</th>
                    {otherCols.map((c) => (
                      <th key={c} className="px-3 py-2.5 font-medium whitespace-nowrap">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview.slice(0, 10).map((r, i) => {
                    const flagged = Number(r.flag) === 1;
                    const s = Number(r.score);
                    return (
                      <tr key={i}>
                        <td className="sticky left-0 z-10 border-t border-border bg-card px-4 py-2.5 sm:px-5">
                          <span className={cx("inline-flex h-[22px] items-center rounded-md px-2 text-[12px] font-medium", flagged ? "bg-pink/15 text-pink" : "bg-card-3 text-muted")}>
                            {flagged ? "Flag" : "Clear"}
                          </span>
                        </td>
                        <td className="border-t border-border px-3 py-2.5">
                          <span className="flex items-center gap-2">
                            <Meter value={s} color={flagged ? "var(--c-pink)" : "#5a5a60"} className="h-1.5 w-14" />
                            <span className={cx("num", flagged ? "text-foreground" : "text-subtle")}>{s.toFixed(4)}</span>
                          </span>
                        </td>
                        {otherCols.map((c) => (
                          <td key={c} className="num border-t border-border px-3 py-2.5 whitespace-nowrap text-subtle">
                            {fmtCell(r[c])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="border-t border-border px-4 py-3 text-[12px] text-muted sm:px-5">
              First 10 of <span className="num">{fmtInt(result.rows)}</span> rows. The download has all of them.
            </p>
          </Card>
        </>
      ) : !busy ? (
        <Empty>No rows scored yet. Pick one of the two options above.</Empty>
      ) : null}

      <ActionBar
        hint={result ? "Happy with it? Package the competition for Apex next." : "Try the winner on fresh rows, or go straight to the launch package."}
        secondary={
          result ? (
            <LinkButton href={api.scoreDownloadUrl(project.id)} download="scored.csv" variant="secondary" size="lg" className="sm:hidden">
              <Download className="h-4 w-4" />
              CSV
            </LinkButton>
          ) : null
        }
      >
        <NextLink stage="launch" label="Prepare launch" />
      </ActionBar>
    </div>
  );
}

function explainThreshold(metric?: string, params?: Record<string, unknown>, template?: string): string {
  if (metric === "recall_at_fpr") {
    const per1000 = Math.round(Number(params?.fpr ?? 0.001) * 1000 * 100) / 100;
    return `About ${per1000} in 1,000 good ${template === "fraud" ? "transactions" : "rows"} get flagged by mistake.`;
  }
  if (metric === "recall_at_top_k") {
    const k = Math.round(Number(params?.top_k ?? 0.1) * 100);
    return `The riskiest ${k}% of rows get flagged.`;
  }
  return "Chosen to match the scoring rule you confirmed.";
}
