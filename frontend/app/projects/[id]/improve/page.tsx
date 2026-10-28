"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Lock, Play, RotateCcw, Sparkles, Terminal, Trophy } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, ResultFigure, Spinner, cx } from "@/components/ui";
import { api, errorText, type DockerStatus, type LeaderboardOut, type ModelVersionOut, type SolverOut, type SubmissionOut } from "@/lib/api";
import { openArenaStream } from "@/lib/sse";
import { ValuePanel } from "@/components/ValuePanel";
import { attemptLabel, figureOf, fmtPct, fmtScore } from "@/lib/format";
import { improve as copy } from "@/lib/copy";

type Row = SubmissionOut & { placeholder?: boolean };

export default function ImprovePage() {
  const { project, refresh } = useProject();
  const [board, setBoard] = useState<LeaderboardOut | null>(null);
  const [boardVersion, setBoardVersion] = useState(0);
  const [pending, setPending] = useState<Row[]>([]);
  const [solvers, setSolvers] = useState<SolverOut[] | null>(null);
  const [docker, setDocker] = useState<DockerStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [logOpen, setLogOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const [promoted, setPromoted] = useState<ModelVersionOut | null>(null);
  const seen = useRef<Set<string>>(new Set());
  const logEnd = useRef<HTMLDivElement>(null);

  const loadBoard = useCallback(async () => {
    try {
      const b = await api.leaderboard(project.id);
      setBoard(b);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [project.id]);

  useEffect(() => {
    void loadBoard();
    api.solvers().then((list) => setSolvers(list.filter((x) => !x.agent))).catch(() => setSolvers([]));
    api.docker().then(setDocker).catch(() => setDocker({ available: false, info: "Could not check Docker." }));
    api.arenaStatus(project.id).then((s) => setRunning(s.running)).catch(() => undefined);
  }, [project.id, loadBoard]);

  useEffect(() => {
    const close = openArenaStream(api.streamUrl(project.id), (ev) => {
      switch (ev.type) {
        case "connected":
          setConnected(true);
          break;
        case "error":
          setConnected(false);
          break;
        case "log":
          setLogs((l) => [...l.slice(-499), ev.line]);
          break;
        case "submission_started":
          setRunning(true);
          setPending((p) => (p.some((r) => r.id === ev.id) ? p : [...p, { id: ev.id, solver: ev.solver, status: "running", logs_path: "", is_leader: false, placeholder: true }]));
          break;
        case "submission_scored":
          setPending((p) => p.filter((r) => r.id !== ev.submission.id));
          break;
        case "leaderboard_updated":
          setBoard(ev.board);
          setPending((p) => p.filter((r) => !ev.board.submissions.some((s) => s.id === r.id && s.status !== "queued")));
          break;
        case "model_promoted":
          setPromoted(ev.version);
          void refresh();
          setBoardVersion((v) => v + 1);
          break;
        case "model_version":
          void refresh();
          break;
        case "run_complete":
          setRunning(false);
          setPending([]);
          void loadBoard();
          void refresh();
          setBoardVersion((v) => v + 1);
          break;
        case "finalized":
          setBoard(ev.board);
          setRunning(false);
          void refresh();
          setBoardVersion((v) => v + 1);
          break;
        default:
          break;
      }
    });
    return close;
  }, [project.id, loadBoard, refresh]);

  useEffect(() => {
    if (logOpen) logEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [logs, logOpen]);

  async function run() {
    setStarting(true);
    setError(null);
    setPromoted(null);
    try {
      // The contest solvers: everything except the two that built version 1.
      const contest = (solvers ?? []).map((s) => s.name).filter((n) => n !== "baseline_logreg" && n !== "lgbm_default");
      await api.arenaRun(project.id, { replay: true, solvers: contest.length ? contest : undefined });
      setRunning(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setStarting(false);
    }
  }

  const active = project.active_model;
  const v1 = project.versions.find((v) => v.version === 1);
  const versionBySub = new Map(project.versions.map((v) => [v.submission_id, v]));
  const scored = board?.submissions ?? [];
  const rows: Row[] = [...scored, ...pending.filter((p) => !scored.some((s) => s.id === p.id))];
  // Attempts: version 1's submission first, then the rest by business value; placeholders last.
  const ordered = rows.slice().sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  const hasScores = scored.some((s) => s.status === "scored");
  const doneRuns = rows.filter((r) => r.status === "scored" || r.status === "failed").length;
  const fig = figureOf(active?.business_value);
  const marginPct = Math.round(project.min_improvement * 1000) / 10;
  const contestCount = (solvers ?? []).filter((s) => s.name !== "baseline_logreg" && s.name !== "lgbm_default").length;
  let attemptIndex = 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] sm:text-[26px]">{copy.title}</h1>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-subtle">{copy.sub}</p>
      </div>

      {!project.protect ? <Alert kind="warn">{copy.protectFirst}</Alert> : null}
      {docker && !docker.available ? <Alert kind="warn">{copy.noDocker(docker.info || "unknown reason")}</Alert> : null}
      {error ? <Alert>{error}</Alert> : null}

      {promoted ? (
        <section className="pop-in relative overflow-hidden rounded-2xl border border-border-strong bg-card p-5 sm:p-6">
          <span aria-hidden className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full opacity-[0.2] blur-3xl" style={{ background: "var(--brand-gradient)" }} />
          <div className="relative flex items-center gap-2 text-[12px] font-medium text-subtle">
            <span className="bg-brand flex h-5 w-5 items-center justify-center rounded-full text-background">
              <Trophy className="h-3 w-3" />
            </span>
            {copy.active}
          </div>
          <div className="relative mt-2 text-[24px] font-semibold tracking-[-0.02em] sm:text-[30px]">{copy.promoted(promoted.version)}</div>
          <p className="num relative mt-2 text-[15px] text-subtle">{promoted.business_value}</p>
          {promoted.improvement_line ? <p className="num relative mt-0.5 text-[13px] text-muted">{promoted.improvement_line}</p> : null}
        </section>
      ) : null}

      <section className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          {active ? (
            <ResultFigure
              label={
                <span className="flex items-center gap-2">
                  <span className="num">v{active.version}</span>
                  <span>{fig?.label ?? active.metric_name}</span>
                </span>
              }
              value={fig?.value ?? fmtScore(active.private_score)}
              line={active.improvement_line}
              delta={v1 && active.version > 1 ? <Badge tone="accent" className="num">{fmtPct(active.private_score - v1.private_score, 0).replace("%", " pts")}</Badge> : null}
            />
          ) : (
            <div className="text-[13px] text-muted">{copy.protectFirst}</div>
          )}
          <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-subtle sm:flex-col sm:items-end">
            <span className={cx("inline-flex h-7 items-center gap-2 rounded-full border border-border-strong bg-card-2 px-2.5 font-medium", connected ? "text-pink" : "text-muted")}>
              <span className={cx("h-1.5 w-1.5 rounded-full", connected ? "pulse-dot bg-brand" : "bg-muted")} />
              {connected ? copy.live : copy.reconnecting}
            </span>
            <span className="flex items-center gap-4">
              <span className="flex items-center gap-2">
                <span className="bg-brand h-2 w-2 rounded-full" />
                {copy.privateHoldout}
              </span>
            </span>
          </div>
        </div>
        <AttemptChart rows={ordered} versionBySub={versionBySub} />
      </section>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card pad={false} className="lg:col-span-8" title={copy.attempts} subtitle={copy.attemptsSub(marginPct)} actions={<Badge>{copy.localSolvers}</Badge>}>
          {ordered.length === 0 ? (
            <div className="px-4 pb-5 text-[13px] text-muted sm:px-5">{copy.noAttempts(contestCount)}</div>
          ) : (
            <ul className="divide-y divide-border border-t border-border">
              {ordered.map((r) => {
                const fresh = !seen.current.has(r.id);
                if (fresh) seen.current.add(r.id);
                const ver = versionBySub.get(r.id);
                const isActive = ver?.status === "active";
                const isV1 = ver?.version === 1;
                if (!ver && !r.solver.startsWith("agent_solver")) attemptIndex += 1;
                const bv = figureOf(r.business_value);
                return (
                  <li key={r.id} className={cx("flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5", fresh && "row-in", isActive && "bg-[linear-gradient(90deg,rgb(167_139_250/0.08),transparent_60%)]")}>
                    <span className={cx("num flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border text-[12px]", isActive ? "bg-brand border-transparent text-background" : "border-border-strong bg-card-2 text-subtle")}>
                      {ver ? `v${ver.version}` : (r.rank ?? "–")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="truncate text-[14px] font-medium">{isV1 ? copy.v1 : ver ? `Version ${ver.version}` : attemptLabel(r.solver, attemptIndex)}</span>
                        {isActive ? <Badge tone="accent">{copy.active}</Badge> : ver ? <Badge>v{ver.version}</Badge> : r.is_leader ? <Badge>{copy.leading}</Badge> : null}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-muted sm:truncate">{r.error ? <span className="text-danger">{r.error}</span> : bv ? bv.label : <StatusText status={r.status} />}</div>
                    </div>
                    <div className="grid shrink-0 grid-cols-2 items-end gap-4 text-right sm:gap-6">
                      <div>
                        <div className="text-[11px] text-muted">{copy.businessValue}</div>
                        <div className={cx("num text-[18px] leading-none font-medium", isActive ? "text-gradient" : "text-foreground")}>
                          {bv ? bv.value : r.status === "running" ? <Spinner className="ml-auto h-3.5 w-3.5" /> : "–"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted">{copy.rawMetric}</div>
                        <div className="num text-[11px] text-muted">{r.public_score != null ? fmtScore(r.public_score) : "–"}</div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="min-w-0 space-y-4 lg:col-span-4">
          <Card title={copy.worth} actions={<Sparkles className="icon-brand h-4 w-4" />}>
            {board?.savings_line ? (
              <>
                <SavingsFigure line={board.savings_line} />
                {board.savings_formula ? (
                  <details className="group mt-3">
                    <summary className="flex cursor-pointer list-none items-center gap-1 text-[12px] text-muted [&::-webkit-details-marker]:hidden">
                      {copy.howWorked}
                      <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                    </summary>
                    <p className="num mt-2 rounded-lg bg-card-2 p-3 text-[11px] leading-relaxed text-subtle">{board.savings_formula}</p>
                  </details>
                ) : null}
              </>
            ) : (
              <p className="text-[13px] leading-relaxed text-muted">{copy.worthWaiting}</p>
            )}
            {board?.raw_metric_line ? <p className="mt-3 border-t border-border pt-3 text-[11px] leading-relaxed text-muted">{board.raw_metric_line}</p> : null}
          </Card>

          <Card
            pad={false}
            title={
              <span className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-muted" />
                {copy.log}
              </span>
            }
            actions={
              <Button size="sm" variant="ghost" onClick={() => setLogOpen((o) => !o)}>
                {logOpen ? "Hide" : <span className="num">{copy.logLines(logs.length)}</span>}
              </Button>
            }
          >
            {logOpen ? (
              <pre className="scroll-thin mx-4 mb-4 max-h-64 overflow-auto rounded-xl border border-border bg-background p-3 font-mono text-[11px] leading-relaxed text-subtle sm:mx-5 sm:mb-5">
                {logs.length === 0 ? copy.logEmpty : logs.join("\n")}
                <div ref={logEnd} />
              </pre>
            ) : (
              <p className="px-4 pb-4 text-[12px] text-muted sm:px-5 sm:pb-5">{copy.logHint}</p>
            )}
          </Card>
        </div>
      </div>

      {hasScores ? (
        <Card title={copy.worth} subtitle={copy.worthSub}>
          <ValuePanel projectId={project.id} version={boardVersion} activeVersion={active?.version ?? null} onChange={() => void loadBoard()} />
        </Card>
      ) : null}

      <ActionBar
        hint={project.versions.length > 1 ? copy.hintDone : copy.hintIdle}
        secondary={
          <Button size="lg" variant={project.versions.length > 1 ? "secondary" : "primary"} busy={starting || running} disabled={running || !project.active_model} onClick={() => void run()}>
            {running ? null : project.versions.length > 1 ? <RotateCcw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {running ? copy.running(doneRuns, Math.max(rows.length, contestCount)) : project.versions.length > 1 ? copy.runAgain : copy.run}
          </Button>
        }
      >
        {project.versions.length > 1 || hasScores ? <NextLink stage="launch" label={copy.next} /> : <span />}
      </ActionBar>
    </div>
  );
}

function StatusText({ status }: { status: SubmissionOut["status"] }) {
  if (status === "running") return <>{copy.statusRunning}</>;
  if (status === "queued") return <>{copy.queued}</>;
  if (status === "failed") return <span className="text-danger">{copy.failed}</span>;
  return <>{copy.scored}</>;
}

function SavingsFigure({ line }: { line: string }) {
  const m = line.match(/^(.*?):\s*(.+)$/);
  return (
    <div>
      <div className="text-[12px] text-muted">{m ? m[1] : "Estimate"}</div>
      <div className="num text-gradient mt-1.5 text-[30px] leading-none font-medium tracking-[-0.02em]">{m ? m[2] : line}</div>
    </div>
  );
}

const TICKS = [1, 0.75, 0.5, 0.25, 0];

/** Cylinder bars: business value per attempt (the private holdout score). The active version glows; versions are labelled. */
function AttemptChart({ rows, versionBySub }: { rows: Row[]; versionBySub: Map<string | null | undefined, ModelVersionOut> }) {
  let n = 0;
  const groups = rows.map((r) => {
    const ver = versionBySub.get(r.id);
    const v = figureOf(r.business_value);
    const value = v ? parseFloat(v.value) / 100 : null;
    if (!ver && !r.solver.startsWith("agent_solver")) n += 1;
    return { key: r.id, value: Number.isFinite(value as number) ? value : null, running: r.status === "running" || r.status === "queued", ver, label: ver ? `v${ver.version}` : r.solver.startsWith("agent_solver") ? attemptLabel(r.solver) : `Attempt ${n}` };
  });
  if (groups.length === 0) return null;
  const top = Math.max(0.0001, ...groups.map((g) => g.value ?? 0));
  const max = Math.min(1, Math.max(0.2, Math.ceil((top * 1.15) / 0.1) * 0.1));
  const ticks = TICKS.map((t) => t * max);
  const h = (v: number | null) => (v == null ? 0 : Math.max(4, (v / max) * 100));
  return (
    <div className="mt-6 flex gap-3">
      <div className="flex h-[200px] shrink-0 flex-col justify-between pb-0 text-right sm:h-[240px]">
        {ticks.map((t) => (
          <span key={t} className="num -translate-y-1/2 text-[11px] leading-none text-muted first:translate-y-0 last:translate-y-0">
            {Math.round(t * 100)}%
          </span>
        ))}
      </div>
      <div className="min-w-0 flex-1">
        <div className="relative h-[200px] sm:h-[240px]">
          {ticks.map((t, i) => (
            <div key={t} className="grid-dash absolute inset-x-0" style={{ top: `${(i / (ticks.length - 1)) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end justify-around px-2">
            {groups.map((g) => {
              const isActive = g.ver?.status === "active";
              const kind = g.value == null ? (g.running ? "loading" : "ghost") : isActive ? "brand" : "grey";
              return (
                <div key={g.key} className="relative flex h-full w-7 flex-col justify-end sm:w-10">
                  {g.value != null ? (
                    <span className={cx("num absolute inset-x-[-12px] text-center text-[10px] leading-none transition-[bottom] duration-700 sm:text-[11px]", isActive ? "text-foreground" : "text-muted")} style={{ bottom: `calc(${h(g.value)}% + 8px)` }}>
                      {Math.round(g.value * 100)}
                    </span>
                  ) : null}
                  {kind === "ghost" ? (
                    <span className="absolute inset-x-0 flex justify-center text-muted" style={{ bottom: `calc(28% + 6px)` }}>
                      <Lock className="h-3 w-3" />
                    </span>
                  ) : null}
                  <div
                    className={cx("cyl w-full", kind === "grey" && "cyl-grey", kind === "brand" && "cyl-brand", kind === "ghost" && "cyl-sealed opacity-50", kind === "loading" && "shimmer cyl-sealed")}
                    style={{ height: `${g.value == null ? 28 : h(g.value)}%` }}
                  />
                </div>
              );
            })}
          </div>
        </div>
        <div className="mt-3 flex justify-around px-2">
          {groups.map((g) => (
            <span key={g.key} className={cx("max-w-[20%] truncate text-center text-[12px]", g.ver?.status === "active" ? "font-medium text-foreground" : "text-muted")}>
              {g.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
