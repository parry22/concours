"use client";

import { useRef, useState } from "react";
import { NextStep, useProject } from "@/components/ProjectShell";
import { Alert, Button, Card, DataTable, Empty, Stat } from "@/components/ui";
import { api, errorText, type ScoreOut } from "@/lib/api";
import { fmtInt, fmtPct, solverLabel } from "@/lib/format";

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Use the winner</h1>
        <p className="mt-1 max-w-2xl text-muted">
          Upload a new CSV with the same columns. The winning solver{winner ? `, ${solverLabel(winner)},` : ""} scores every row and
          flags the ones to act on.
        </p>
      </div>

      {!project.finalized ? <Alert kind="warn">Finalize the arena first so there is a winner to use.</Alert> : null}

      <Card>
        <div className="flex flex-wrap items-center gap-3">
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
          <Button busy={busy === "upload"} disabled={busy !== null} onClick={() => inputRef.current?.click()}>
            Upload a CSV to score
          </Button>
          <Button variant="secondary" busy={busy === "sample"} disabled={busy !== null} onClick={() => void scoreSample()}>
            Use sample rows
          </Button>
          <span className="text-xs text-muted">Sample rows are 2,000 recent rows the solvers never trained on, without the outcome column.</span>
        </div>
        {error ? <Alert className="mt-4">{error}</Alert> : null}
        {busy ? <p className="mt-4 text-sm text-muted">Fitting the winner on the training split and scoring the rows. A few seconds.</p> : null}
      </Card>

      {result ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Rows scored" value={fmtInt(result.rows)} />
            <Stat label="Rows flagged" value={fmtInt(result.flagged)} hint={result.rows > 0 ? `${fmtPct(result.flagged / result.rows, 2)} of rows` : undefined} />
            <Stat label="Threshold" value={result.threshold.toFixed(4)} hint={thresholdText} />
          </div>

          <Card
            title="Scored rows"
            subtitle="Two columns added: score, the chance this row is a positive, and flag, 1 when the score is above the threshold."
            actions={
              <a
                href={api.scoreDownloadUrl(project.id)}
                className="inline-flex h-9 items-center rounded-lg bg-foreground px-3 text-sm font-medium text-white hover:bg-stone-700"
                download="scored.csv"
              >
                Download scored CSV
              </a>
            }
          >
            <DataTable columns={orderColumns(result.columns)} rows={result.preview.slice(0, 10)} />
            <p className="mt-2 text-xs text-muted">First 10 of {fmtInt(result.rows)} rows. The download has all of them.</p>
          </Card>
        </>
      ) : !busy ? (
        <Empty>No rows scored yet. Upload a CSV or use the sample rows.</Empty>
      ) : null}

      <NextStep stage="launch" />
    </div>
  );
}

function orderColumns(cols: string[]): string[] {
  const special = ["score", "flag"];
  return [...special.filter((c) => cols.includes(c)), ...cols.filter((c) => !special.includes(c))];
}

function explainThreshold(metric?: string, params?: Record<string, unknown>, template?: string): string {
  if (metric === "recall_at_fpr") {
    const per1000 = Math.round(Number(params?.fpr ?? 0.001) * 1000 * 100) / 100;
    return `Set so that about ${per1000} in 1,000 good ${template === "fraud" ? "transactions" : "rows"} get flagged by mistake.`;
  }
  if (metric === "recall_at_top_k") {
    const k = Math.round(Number(params?.top_k ?? 0.1) * 100);
    return `Set so the riskiest ${k}% of rows get flagged.`;
  }
  return "Chosen to match the scoring rule you confirmed.";
}
