"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";
import { DailyBars, MoneyFigure } from "@/components/Figures";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Meter, StatusPill, cx } from "@/components/ui";
import { api, errorText, type ModelVersionOut, type RatioOut } from "@/lib/api";
import { fmtPct } from "@/lib/format";
import { alerts, overview as copy } from "@/lib/copy";
import { stepHref } from "@/lib/stages";

type Daily = { day: string; caught: number };
const money = (x: number | null | undefined) => (x == null ? "n/a" : `${x < 0 ? "-" : ""}$${Math.abs(Math.round(x)).toLocaleString("en-US")}`);
const short = (d: string) => new Date(d + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

export default function OverviewPage() {
  const { project, refresh } = useProject();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ratio, setRatio] = useState<RatioOut | null>(null);
  useEffect(() => {
    api.ratio(project.id).then(setRatio).catch(() => setRatio(null));
  }, [project.id, project.as_of]);
  const active = project.active_model;
  const v1 = project.versions.find((v) => v.version === 1) ?? null;
  const drift = project.drift;
  const st = project.fraud_settings;
  const stats = (active?.stats ?? {}) as Record<string, unknown>;
  const num = (k: string) => (typeof stats[k] === "number" ? (stats[k] as number) : null);
  const daily = (active?.stats?.daily ?? []) as Daily[];
  const v1Daily = v1 && v1.id !== active?.id ? ((v1.stats?.daily ?? []) as Daily[]) : null;
  const slipping = project.health === "slipping" && drift?.slipping;
  const range = daily.length ? `${short(daily[0].day)} – ${short(daily[daily.length - 1].day)}` : null;

  async function jump() {
    setBusy(true);
    setError(null);
    try {
      await api.jump(project.id, 28, true);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!active) return <Alert kind="warn">{copy.titleNone}</Alert>;

  return (
    <div className="space-y-5">
      {error ? <Alert>{error}</Alert> : null}

      {slipping ? (
        <Card>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <Badge tone="danger" dot className="mt-0.5 shrink-0">
                {alerts.slipping}
              </Badge>
              <p className="text-[14px] leading-relaxed">
                {drift.line} <span className="text-subtle">{drift.round_started || project.model_status === "improving" ? alerts.roundStarted : alerts.roundReady}</span>
              </p>
            </div>
            <Link href={stepHref(project.id, "improve")} className="inline-flex h-8 shrink-0 items-center rounded-lg bg-card-3 px-3 text-[13px] font-medium hover:bg-[#2a2a2f]">
              {alerts.runRound}
            </Link>
          </div>
        </Card>
      ) : null}

      <section className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex h-8 items-center gap-2 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] font-medium">
            <span className="num">v{active.version}</span>
            <span className="text-subtle">{copy.caught}</span>
          </span>
          <span className="flex items-center gap-2">
            {range ? <span className="num inline-flex h-8 items-center rounded-lg border border-border-strong bg-card-2 px-3 text-[12px] text-subtle">{copy.testDays(range)}</span> : null}
            <StatusPill status={project.model_status} />
          </span>
        </div>
        <div className="mt-5 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <MoneyFigure
            value={project.money_per_day}
            suffix={copy.queueSize(st?.daily_capacity ?? 200)}
            compare={
              <>
                {v1 && v1.id !== active.id ? (
                  <>
                    {copy.vs} <span className="num font-medium text-foreground">{money(v1.private_score)}</span> {copy.withFirst}
                  </>
                ) : (
                  copy.source.baseline
                )}
                {project.current_tool_per_day != null ? (
                  <span className="block" title={copy.vsToolHint}>
                    {copy.vs} <span className="num font-medium text-foreground">{money(project.current_tool_per_day)}</span> {copy.vsTool}
                  </span>
                ) : null}
              </>
            }
          />
        </div>
        <div className="mt-6">
          <DailyBars days={daily} compare={v1Daily} legend={{ current: copy.legendCurrent(active.version), compare: copy.legendFirst }} />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title={copy.queueCard}>
          <ul className="space-y-3.5">
            <Row label={copy.net} hint={copy.netSub} value={money(project.net_per_day)} />
            <Row label={copy.precision} hint={copy.precisionSub} value={num("precision") != null ? fmtPct(num("precision")!, 1) : "n/a"} />
            <Row label={copy.perDayCount} hint={copy.perDayCountSub} value={num("count_per_day") != null ? num("count_per_day")!.toFixed(1) : "n/a"} />
            <Row label={copy.falseAlarms} hint={copy.falseAlarmsSub} value={num("false_alarms_per_1000") != null ? num("false_alarms_per_1000")!.toFixed(1) : "n/a"} />
          </ul>
        </Card>

        <Card
          title={copy.health}
          actions={
            project.source === "sample" ? (
              <Button size="sm" variant="secondary" busy={busy} disabled={!project.can_jump} onClick={() => void jump()} title={copy.jumpSub}>
                {project.can_jump ? copy.jumpShort : copy.noJump}
              </Button>
            ) : null
          }
        >
          {drift && drift.weeks.length ? (
            <ul className="space-y-3">
              {drift.weeks.map((w) => {
                const bad = w.drop > 0.15;
                return (
                  <li key={w.week_start} className="flex items-center gap-3">
                    <span className={cx("h-2 w-2 shrink-0 rounded-full", bad ? "bg-danger" : "bg-brand")} />
                    <span className="num min-w-0 flex-1 truncate text-[13px] text-subtle">
                      {copy.week(short(w.week_start), short(w.week_end))}: <span className="font-medium text-foreground">{fmtPct(w.share, 0)}</span>
                    </span>
                    <Meter value={w.share} color={bad ? "var(--danger)" : "brand"} className="h-1.5 w-[38%]" />
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-[13px] leading-relaxed text-muted">{project.source === "sample" ? copy.noWeeks : copy.noWeeksReal(st?.label_delay_days ?? 30)}</p>
          )}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-[12px] text-muted">
            <span className="flex items-center gap-1.5">
              <CalendarClock className="h-3.5 w-3.5" />
              {project.as_of ? copy.today(project.as_of) : null}
            </span>
            {drift?.baseline_share != null ? <span className="num">{copy.baseline(fmtPct(drift.baseline_share, 0))}</span> : null}
          </div>
          {drift?.psi?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5" title={copy.driftSub}>
              {drift.psi.map((f) => (
                <Badge key={f.name} tone={f.flagged ? "warn" : "neutral"}>
                  {f.name} <span className="num">{f.psi.toFixed(2)}</span>
                </Badge>
              ))}
            </div>
          ) : null}
        </Card>

        <Card title={copy.timeline}>
          <ul className="divide-y divide-border">
            {[...project.versions].reverse().map((v) => (
              <VersionRow key={v.id} v={v} first={v.version === v1?.version} />
            ))}
          </ul>
          <p className="mt-3 text-[12px] leading-relaxed text-muted">{copy.timelineSub}</p>
        </Card>
      </div>

      {ratio && ratio.months.length ? <RatioCard r={ratio} /> : null}

      <ActionBar hint={copy.openQueue}>
        <NextLink stage="queue" label={copy.next} />
      </ActionBar>
    </div>
  );
}

function Row({ label, hint, value }: { label: string; hint: string; value: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3">
      <span className="min-w-0">
        <span className="block text-[13px]">{label}</span>
        <span className="block text-[11px] text-muted">{hint}</span>
      </span>
      <span className="num shrink-0 text-[15px] font-medium">{value}</span>
    </li>
  );
}

const pct = (x: number) => `${(x * 100).toFixed(x * 100 >= 10 ? 0 : 2)}%`;

/** Monthly fraud-and-dispute ratio with Visa's line drawn on it. */
function RatioCard({ r }: { r: RatioOut }) {
  const max = Math.max(r.threshold * 1.6, ...r.months.map((m) => m.ratio));
  const latest = r.months[r.months.length - 1];
  const tone = latest.over ? "danger" : latest.ratio >= r.threshold ? "warn" : "ok";
  return (
    <Card
      title={copy.ratio}
      actions={
        <Badge tone={tone} dot>
          {latest.over ? copy.ratioOver : latest.ratio >= r.threshold ? copy.ratioBelowFloor : copy.ratioUnder}
        </Badge>
      }
    >
      <p className="text-[12px] leading-relaxed text-muted">{copy.ratioSub(pct(r.threshold))}</p>
      <div className="relative mt-4 flex h-28 items-end gap-1.5">
        <div className="pointer-events-none absolute right-0 left-0 border-t border-dashed border-danger/70" style={{ bottom: `${(r.threshold / max) * 100}%` }}>
          <span className="num absolute right-0 -top-4 text-[10px] text-danger">{copy.ratioLine(pct(r.threshold))}</span>
        </div>
        {r.months.map((m) => (
          <div key={m.month} className="flex min-w-0 flex-1 flex-col items-center gap-1" title={`${m.month}: ${pct(m.ratio)} (${m.events.toLocaleString("en-US")} of ${m.payments.toLocaleString("en-US")})`}>
            <div className={cx("w-full rounded-t-md", m.ratio >= r.threshold ? "bg-danger/80" : "bg-brand")} style={{ height: `${Math.max(2, (m.ratio / max) * 100)}%` }} />
            <span className="num truncate text-[10px] text-muted">{m.month.slice(2).replace("-", "/")}</span>
          </div>
        ))}
      </div>
      <p className="num mt-3 text-[13px]">
        {copy.ratioLatest(latest.month, pct(latest.ratio))} <span className="text-muted">· {copy.ratioNote}</span>
      </p>
    </Card>
  );
}

function VersionRow({ v, first }: { v: ModelVersionOut; first: boolean }) {
  const on = v.status === "active";
  return (
    <li className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
      <span className={cx("inline-flex h-[22px] w-[60px] shrink-0 items-center justify-center rounded-md text-[12px] font-medium", on ? "bg-accent-soft text-[#c4b5fd]" : "bg-card-3 text-subtle")}>
        {on ? copy.active : copy.retired}
      </span>
      <span className="min-w-0 flex-1">
        <span className="num block text-[13px] font-medium">v{v.version}</span>
        <span className="block truncate text-[11px] text-muted" title={v.changes?.length ? `${copy.changes}: ${v.changes.join(" ")}` : undefined}>
          {v.changes?.length && !first ? v.changes.slice(1, 2)[0] ?? v.changes[0] : first ? copy.source.baseline : copy.source[v.source as keyof typeof copy.source]}
        </span>
      </span>
      <span className="num shrink-0 text-[13px] font-medium">{money(v.private_score)}</span>
    </li>
  );
}
