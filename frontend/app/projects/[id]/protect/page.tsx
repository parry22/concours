"use client";

import { useEffect, useRef, useState } from "react";
import { Check, RotateCcw, ShieldAlert, ShieldCheck } from "lucide-react";
import { LeakCards, ProtectionDetails } from "@/components/ProtectionReport";
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
  const aside = new Set(report?.set_aside_columns ?? []);

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
          <LeakCards report={report} />


          {/* The first model: building, then ready. */}
          {v1 ? (
            <section className="pop-in relative overflow-hidden rounded-2xl border border-border-strong bg-card p-5 sm:p-6">
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

          <ProtectionDetails report={report} projectId={project.id} version={v1 ? (project.active_model?.version ?? v1.version) : null} />
        </>
      ) : null}

      <ActionBar hint={v1 ? copy.hintReady : report ? copy.hintBuilding : copy.hintRun}>
        <NextLink stage="overview" label={copy.next} disabled={!v1 || running} />
      </ActionBar>
    </div>
  );
}

