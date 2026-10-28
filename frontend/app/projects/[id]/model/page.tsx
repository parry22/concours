"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Activity, ChevronDown, ListOrdered, Upload } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Card, PageHeader, ResultFigure, Spinner, StatusPill, cx } from "@/components/ui";
import { api, errorText, type HealthOut, type ModelVersionOut } from "@/lib/api";
import { listsHref, stepHref } from "@/lib/stages";
import { fmtAgo, fmtDateTime, fmtInt, fmtPct, fmtScore, figureOf } from "@/lib/format";
import { approachLabel } from "@/lib/technical";
import { model as copy, tooltips } from "@/lib/copy";

export default function ModelPage() {
  const { project, refresh } = useProject();
  const active = project.active_model;
  const versions = project.versions.slice().sort((a, b) => b.version - a.version);
  const v1 = project.versions.find((v) => v.version === 1);
  const [health, setHealth] = useState<HealthOut | null>(project.health_check ?? null);
  const [busy, setBusy] = useState<"sample" | "upload" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setHealth(project.health_check ?? null);
  }, [project.health_check]);

  // Version 1 may still be building when the page opens right after Protect.
  useEffect(() => {
    if (active) return;
    const t = setInterval(() => void refresh(), 4000);
    return () => clearInterval(t);
  }, [active, refresh]);

  async function check(file?: File) {
    setBusy(file ? "upload" : "sample");
    setError(null);
    try {
      const h = await api.health(project.id, file, { sample: !file });
      setHealth(h);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const fig = figureOf(active?.business_value);
  const slipping = project.health === "slipping";

  return (
    <div className="space-y-5">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void check(f);
          e.target.value = "";
        }}
      />
      <PageHeader title={active ? copy.title(active.version) : copy.titleNone} actions={active ? <StatusPill status={project.model_status} /> : null}>
        {copy.sub}
      </PageHeader>

      {error ? <Alert>{error}</Alert> : null}

      {slipping ? (
        <Alert kind="warn">
          <span className="font-medium">{copy.slipped}</span> {health?.line}{" "}
          <Link href={stepHref(project.id, "improve")} className="font-medium underline underline-offset-2">
            {copy.runRound}
          </Link>
        </Alert>
      ) : null}

      {!active ? (
        <Card>
          <div className="flex items-center gap-3">
            <Spinner className="h-4 w-4 text-pink" />
            <span className="text-[14px] font-medium">{project.protect ? copy.building : copy.none}</span>
          </div>
        </Card>
      ) : (
        <section className="relative overflow-hidden rounded-2xl border border-border bg-card p-5 sm:p-7">
          <span aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full opacity-[0.14] blur-3xl" style={{ background: "var(--brand-gradient)" }} />
          <ResultFigure
            className="relative"
            label={fig?.label ?? active.metric_name}
            value={fig?.value ?? fmtScore(active.private_score)}
            line={active.improvement_line && active.improvement_line !== copy.firstModel ? active.improvement_line : copy.firstModel}
            delta={
              v1 && active.version > 1 ? (
                <Badge tone="accent" className="num">
                  {fmtPct(active.private_score - v1.private_score, 0).replace("%", " pts")}
                </Badge>
              ) : null
            }
          />
          <div className="relative mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-4 text-[12px] text-muted">
            <span title={tooltips.privateHoldout}>{copy.source[active.source]}</span>
            <span aria-hidden>·</span>
            <span>{fmtAgo(active.created_at)}</span>
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7" title={copy.timeline} subtitle={copy.timelineSub}>
          {versions.length === 0 ? (
            <p className="text-[13px] text-muted">{copy.none}</p>
          ) : (
            <ol className="relative space-y-0 border-l border-border pl-5">
              {versions.map((v) => (
                <VersionRow key={v.id} v={v} first={v.version === 1} />
              ))}
            </ol>
          )}
        </Card>

        <div className="min-w-0 space-y-4 lg:col-span-5">
          <Card title={copy.listsTitle} subtitle={copy.listsSub(project.list_name)}>
            <Link
              href={listsHref(project.id)}
              className={cx(
                "flex items-center justify-between gap-3 rounded-xl border border-border-strong bg-card-2 px-4 py-3 text-[14px] font-medium transition-colors hover:bg-card-3",
                !active && "pointer-events-none opacity-50",
              )}
            >
              <span className="flex items-center gap-2.5">
                <ListOrdered className="icon-brand h-4 w-4" />
                {project.list_name}
              </span>
              <span className="text-[12px] text-pink">{copy.openLists}</span>
            </Link>
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted" />
                {copy.watch}
              </span>
            }
            subtitle={copy.watchSub}
          >
            <div className="grid gap-2">
              <button
                onClick={() => void check()}
                disabled={busy !== null || !active}
                className="flex items-start gap-3 rounded-xl border border-border-strong bg-card-2 p-3 text-left transition-colors hover:bg-card-3 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === "sample" ? <Spinner className="mt-0.5 h-4 w-4 text-pink" /> : <Activity className="icon-brand mt-0.5 h-4 w-4" />}
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium">{copy.checkSample}</span>
                  <span className="block text-[12px] text-muted">{copy.checkSampleSub}</span>
                </span>
              </button>
              <button
                onClick={() => inputRef.current?.click()}
                disabled={busy !== null || !active}
                className="flex items-start gap-3 rounded-xl border border-dashed border-border-strong p-3 text-left transition-colors hover:bg-card-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === "upload" ? <Spinner className="mt-0.5 h-4 w-4 text-pink" /> : <Upload className="icon-brand mt-0.5 h-4 w-4" />}
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium">{copy.checkUpload}</span>
                  <span className="block text-[12px] text-muted">{copy.checkUploadSub}</span>
                </span>
              </button>
            </div>
            {busy ? <p className="mt-3 text-[12px] text-muted">{copy.checking}</p> : null}
            <div className="mt-4 border-t border-border pt-3 text-[12px] leading-relaxed">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-subtle">{copy.lastCheck}</span>
                {health ? <StatusPill status={health.health === "slipping" ? "slipping" : "healthy"} /> : null}
              </div>
              <p className={cx("mt-1", health ? "text-foreground" : "text-muted")}>{health ? health.line : copy.noCheck}</p>
              {health ? (
                <p className="num mt-1 text-muted">
                  {fmtInt(health.rows)} rows · {fmtInt(health.positives)} positives · {fmtDateTime(health.checked_at)}
                </p>
              ) : null}
              <p className="mt-1 text-muted">{copy.threshold(Math.round(project.drift_threshold * 100))}</p>
            </div>
          </Card>
        </div>
      </div>

      {active ? (
        <details className="group rounded-2xl border border-border bg-card">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 sm:px-5 [&::-webkit-details-marker]:hidden">
            <span className="text-[14px] font-medium">{copy.technical}</span>
            <span className="flex items-center gap-2 text-[12px] text-muted">
              {copy.technicalSub}
              <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
            </span>
          </summary>
          <div className="border-t border-border px-4 py-4 sm:px-5">
            <table className="w-full text-[13px]">
              <tbody>
                {project.versions
                  .slice()
                  .sort((a, b) => b.version - a.version)
                  .map((v) => (
                    <tr key={v.id} className="border-b border-border last:border-b-0">
                      <td className="num py-2 pr-3 align-top font-medium">v{v.version}</td>
                      <td className="py-2 pr-3 align-top text-subtle">{approachLabel(v.solver_name)}</td>
                      <td className="num py-2 pr-3 align-top text-right text-muted">
                        {fmtScore(v.private_score)}
                        {v.public_score != null ? <span className="block text-[11px]">{copy.tech.publicScore}: {fmtScore(v.public_score)}</span> : null}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <dl className="mt-3 grid gap-x-6 gap-y-1 text-[12px] text-muted sm:grid-cols-3">
              <div>
                <dt className="inline">{copy.tech.metric}: </dt>
                <dd className="inline">{active.metric_name}</dd>
              </div>
              <div>
                <dt className="inline">{copy.tech.margin}: </dt>
                <dd className="num inline">{fmtPct(project.min_improvement, 1)}</dd>
              </div>
              <div>
                <dt className="inline">{copy.tech.drift}: </dt>
                <dd className="num inline">{fmtPct(project.drift_threshold, 0)}</dd>
              </div>
            </dl>
          </div>
        </details>
      ) : null}

      <ActionBar hint={copy.hintImprove}>
        <NextLink stage="improve" label={copy.next} disabled={!active} />
      </ActionBar>
    </div>
  );
}

function VersionRow({ v, first }: { v: ModelVersionOut; first: boolean }) {
  const fig = figureOf(v.business_value);
  const activeV = v.status === "active";
  return (
    <li className="relative pb-5 last:pb-0">
      <span className={cx("absolute top-1.5 -left-[25px] h-2.5 w-2.5 rounded-full border-2 border-card", activeV ? "bg-brand" : "bg-border-strong")} />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="num text-[14px] font-semibold">v{v.version}</span>
        <span className="text-[12px] text-muted">{copy.source[v.source]}</span>
        {activeV ? <Badge tone="accent">{copy.active}</Badge> : <Badge>{copy.retired}</Badge>}
        <span className="num ml-auto text-[12px] text-muted">{first ? `${fmtAgo(v.created_at)}` : fmtAgo(v.created_at)}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
        <span className={cx("num text-[24px] leading-none font-medium tracking-[-0.02em]", activeV ? "text-gradient" : "text-foreground")}>{fig?.value ?? fmtScore(v.private_score)}</span>
        <span className="text-[13px] text-subtle">{fig?.label ?? v.metric_name}</span>
      </div>
    </li>
  );
}
