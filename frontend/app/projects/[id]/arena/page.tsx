"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Lock, Play, RotateCcw, Sparkles, Terminal, Trophy } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Spinner, cx } from "@/components/ui";
import { api, errorText, type DockerStatus, type LeaderboardOut, type SolverOut, type SubmissionOut } from "@/lib/api";
import { openArenaStream } from "@/lib/sse";
import { fmtPct, fmtScore, metricLabel, solverLabel, solverShort } from "@/lib/format";

type Row = SubmissionOut & { placeholder?: boolean };

export default function ArenaPage() {
  const { project, refresh } = useProject();
  const [board, setBoard] = useState<LeaderboardOut | null>(null);
  const [pending, setPending] = useState<Row[]>([]);
  const [solvers, setSolvers] = useState<SolverOut[] | null>(null);
  const [docker, setDocker] = useState<DockerStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [logOpen, setLogOpen] = useState(false);
  const [connected, setConnected] = useState(false);
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
    // The default run uses the non-agent solvers only.
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
          setPending((p) =>
            p.some((r) => r.id === ev.id)
              ? p
              : [...p, { id: ev.id, solver: ev.solver, status: "running", logs_path: "", is_leader: false, placeholder: true }],
          );
          setLogs((l) => [...l.slice(-499), `${ev.solver}: started${ev.cached ? " (cached result available)" : ""}`]);
          break;
        case "submission_scored":
          setPending((p) => p.filter((r) => r.id !== ev.submission.id));
          break;
        case "leaderboard_updated":
          setBoard(ev.board);
          setPending((p) => p.filter((r) => !ev.board.submissions.some((s) => s.id === r.id && s.status !== "queued")));
          break;
        case "run_complete":
          setRunning(false);
          setPending([]);
          void loadBoard();
          void refresh();
          break;
        case "finalized":
          setBoard(ev.board);
          setRunning(false);
          void refresh();
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
    try {
      await api.arenaRun(project.id, { replay: true });
      setRunning(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setStarting(false);
    }
  }

  async function finalize() {
    setFinalizing(true);
    setError(null);
    try {
      const b = await api.finalize(project.id);
      setBoard(b);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setFinalizing(false);
    }
  }

  const scored = board?.submissions ?? [];
  const rows: Row[] = [...scored, ...pending.filter((p) => !scored.some((s) => s.id === p.id))];
  const sorted = rows.slice().sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  const finalized = Boolean(board?.finalized);
  const hasScores = scored.some((s) => s.status === "scored");
  const spec = project.spec;
  const params = (spec?.metric_params ?? {}) as Record<string, unknown>;
  const headline = board?.business_card?.includes(":") ? board.business_card.slice(0, board.business_card.lastIndexOf(":")) : spec ? metricLabel(spec.primary_metric, params) : "Score";
  const pick = (s?: SubmissionOut | null) => (s ? (finalized ? s.private_score : s.public_score) : null);
  const leaderScore = pick(board?.leader);
  const baseScore = pick(board?.baseline);
  const delta = leaderScore != null && baseScore != null ? (leaderScore - baseScore) * 100 : null;
  const doneRuns = rows.filter((r) => r.status === "scored" || r.status === "failed").length;

  let primary: React.ReactNode;
  let hint: string;
  if (finalized) {
    primary = <NextLink stage="serve" label="Use the winner" />;
    hint = `Winner chosen on the private holdout, which no solver ever saw.`;
  } else if (hasScores && !running) {
    primary = (
      <Button size="lg" busy={finalizing} onClick={() => void finalize()}>
        <Lock className="h-4 w-4" />
        Finalize and reveal
      </Button>
    );
    hint = "Finalizing unseals the private holdout scores and picks the winner.";
  } else {
    primary = (
      <Button size="lg" busy={starting || running} disabled={running || !project.protect} onClick={() => void run()}>
        {running ? null : <Play className="h-4 w-4" />}
        {running ? `Solvers running ${doneRuns}/${Math.max(rows.length, solvers?.length ?? 0)}` : "Run local solvers"}
      </Button>
    );
    hint = "Each solver trains on the public split; the referee scores it in a sandbox.";
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] sm:text-[26px]">Arena</h1>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-subtle">
          Local solvers compete on the public split. Private scores stay sealed until you finalize.
        </p>
      </div>

      {!project.protect ? <Alert kind="warn">Run data protection first.</Alert> : null}
      {docker && !docker.available ? (
        <Alert kind="warn">Docker is not available: {docker.info || "unknown reason"}. Cached results still replay; new runs need Docker Desktop.</Alert>
      ) : null}
      {error ? <Alert>{error}</Alert> : null}

      {/* Hero, after the reference: label, big figure, comparison, cylinder chart. */}
      <section className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <span className="inline-flex h-8 max-w-full items-center gap-2 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] font-medium">
              <span className="truncate">{headline}</span>
            </span>
            <div className="mt-4 flex items-baseline gap-3">
              {leaderScore != null ? (
                <span key={`${finalized}`} className="num pop-in text-[44px] leading-none font-medium tracking-[-0.03em] sm:text-[56px]">
                  {(leaderScore * 100).toFixed(1)}
                  <span className="ml-0.5 align-top text-[22px] text-subtle sm:text-[26px]">%</span>
                </span>
              ) : (
                <span className="num text-[44px] leading-none font-medium tracking-[-0.03em] text-[#3a3a40] sm:text-[56px]">--.-%</span>
              )}
              {delta != null && board?.leader?.id !== board?.baseline?.id ? (
                <Badge tone={delta >= 0 ? "ok" : "danger"} className="num">
                  {delta >= 0 ? "+" : ""}
                  {delta.toFixed(1)} pts
                </Badge>
              ) : null}
            </div>
            <p className="mt-2 text-[13px] text-muted">
              {baseScore != null ? (
                <>
                  vs <span className="num font-medium text-foreground">{fmtPct(baseScore, 1)}</span> baseline ·{" "}
                  {finalized ? "private holdout" : "public leaderboard"}
                </>
              ) : (
                "Run the solvers to fill the board"
              )}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-subtle sm:flex-col sm:items-end">
            <span className={cx("inline-flex h-7 items-center gap-2 rounded-full border border-border-strong bg-card-2 px-2.5 font-medium", connected ? "text-pink" : "text-muted")}>
              <span className={cx("h-1.5 w-1.5 rounded-full", connected ? "pulse-dot bg-brand" : "bg-muted")} />
              {connected ? "Live" : "Reconnecting"}
            </span>
            <span className="flex items-center gap-4">
              <span className="flex items-center gap-2">
                <span className="bg-brand h-2 w-2 rounded-full" />
                Private holdout
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#5a5a60]" />
                Public leaderboard
              </span>
            </span>
          </div>
        </div>
        <SolverChart rows={sorted} finalized={finalized} solvers={solvers} />
      </section>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card
          pad={false}
          className="lg:col-span-8"
          title="Leaderboard"
          subtitle={
            finalized
              ? `Winner: ${board?.leader ? solverLabel(board.leader.solver) : "none"}.`
              : `A new leader must beat the top score by at least ${Math.round((board?.takeover_margin ?? 0.01) * 100)}%.`
          }
        >
          {sorted.length === 0 ? (
            <div className="px-4 pb-5 text-[13px] text-muted sm:px-5">
              {solvers && solvers.length > 0 ? `${solvers.length} local solvers ready: ${solvers.map((s) => solverShort(s.name)).join(", ")}.` : "No submissions yet."}
            </div>
          ) : (
            <ul className="divide-y divide-border border-t border-border">
              {sorted.map((r) => {
                const fresh = !seen.current.has(r.id);
                if (fresh) seen.current.add(r.id);
                const win = r.is_leader && finalized;
                return (
                  <li key={r.id} className={cx("flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5", fresh && "row-in", win && "bg-[linear-gradient(90deg,rgb(167_139_250/0.08),transparent_60%)]")}>
                    <span
                      className={cx(
                        "num flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border text-[13px]",
                        win ? "bg-brand border-transparent text-background" : "border-border-strong bg-card-2 text-subtle",
                      )}
                    >
                      {win ? <Trophy className="h-4 w-4" /> : (r.rank ?? "–")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="truncate text-[14px] font-medium">
                          <span className="sm:hidden">{solverShort(r.solver)}</span>
                          <span className="hidden sm:inline">{solverLabel(r.solver)}</span>
                        </span>
                        {win ? <Badge tone="accent">Winner</Badge> : r.is_leader ? <Badge>Leading</Badge> : null}
                        {r.solver === "baseline_logreg" ? <Badge>baseline</Badge> : null}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-muted sm:truncate">
                        {r.error ? <span className="text-danger">{r.error}</span> : r.business_value || <StatusText status={r.status} />}
                      </div>
                    </div>
                    <div className="grid shrink-0 grid-cols-2 gap-4 text-right sm:gap-6">
                      <div>
                        <div className="text-[11px] text-muted">Public</div>
                        <div className="num text-[13px]">{r.public_score != null ? fmtScore(r.public_score) : r.status === "running" ? <Spinner className="ml-auto h-3.5 w-3.5" /> : "–"}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted">Private</div>
                        <div className="num text-[13px]">
                          {finalized && r.private_score != null ? (
                            <span className={cx(win && "text-gradient font-medium")}>{fmtScore(r.private_score)}</span>
                          ) : (
                            <Lock className="ml-auto h-3.5 w-3.5 text-muted" />
                          )}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="min-w-0 space-y-4 lg:col-span-4">
          <Card title="What it is worth" actions={<Sparkles className="icon-brand h-4 w-4" />}>
            {board?.savings_line ? (
              <>
                <SavingsFigure line={board.savings_line} />
                {board.savings_formula ? (
                  <details className="group mt-3">
                    <summary className="flex cursor-pointer list-none items-center gap-1 text-[12px] text-muted [&::-webkit-details-marker]:hidden">
                      How this is worked out
                      <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                    </summary>
                    <p className="num mt-2 rounded-lg bg-card-2 p-3 text-[11px] leading-relaxed text-subtle">{board.savings_formula}</p>
                  </details>
                ) : null}
              </>
            ) : (
              <p className="text-[13px] leading-relaxed text-muted">
                {hasScores ? "Add costs in the scoring rule to see an estimate." : "Appears once solvers are scored, using the costs from the scoring rule."}
              </p>
            )}
            {board?.raw_metric_line ? <p className="mt-3 border-t border-border pt-3 text-[11px] leading-relaxed text-muted">{board.raw_metric_line}</p> : null}
          </Card>

          <Card
            pad={false}
            title={
              <span className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-muted" />
                Run log
              </span>
            }
            actions={
              <Button size="sm" variant="ghost" onClick={() => setLogOpen((o) => !o)}>
                {logOpen ? "Hide" : <span className="num">{logs.length} lines</span>}
              </Button>
            }
          >
            {logOpen ? (
              <pre className="scroll-thin mx-4 mb-4 max-h-64 overflow-auto rounded-xl border border-border bg-background p-3 font-mono text-[11px] leading-relaxed text-subtle sm:mx-5 sm:mb-5">
                {logs.length === 0 ? "No log lines yet." : logs.join("\n")}
                <div ref={logEnd} />
              </pre>
            ) : (
              <p className="px-4 pb-4 text-[12px] text-muted sm:px-5 sm:pb-5">What the arena is doing, line by line.</p>
            )}
          </Card>
        </div>
      </div>

      <ActionBar
        hint={hint}
        secondary={
          hasScores && !finalized && !running ? (
            <Button size="lg" variant="secondary" busy={starting} onClick={() => void run()}>
              <RotateCcw className="h-4 w-4" />
              <span className="hidden sm:inline">Run again</span>
              <span className="sm:hidden">Rerun</span>
            </Button>
          ) : null
        }
      >
        {primary}
      </ActionBar>
    </div>
  );
}

function StatusText({ status }: { status: SubmissionOut["status"] }) {
  if (status === "running") return <>Training and scoring</>;
  if (status === "queued") return <>Queued</>;
  if (status === "failed") return <span className="text-danger">Failed</span>;
  return <>Scored</>;
}

function SavingsFigure({ line }: { line: string }) {
  const m = line.match(/^(.*?):\s*(.+)$/);
  return (
    <div>
      <div className="text-[12px] text-muted">{m ? m[1] : "Estimate"}</div>
      <div className="num mt-1.5 text-[30px] leading-none font-medium tracking-[-0.02em]">{m ? m[2] : line}</div>
    </div>
  );
}

const TICKS = [1, 0.75, 0.5, 0.25, 0];

function SolverChart({ rows, finalized, solvers }: { rows: Row[]; finalized: boolean; solvers: SolverOut[] | null }) {
  const groups: { key: string; solver: string; pub: number | null; priv: number | null; running: boolean; leader: boolean }[] =
    rows.length > 0
      ? rows.map((r) => ({
          key: r.id,
          solver: r.solver,
          pub: r.public_score ?? null,
          priv: r.private_score ?? null,
          running: r.status === "running" || r.status === "queued",
          leader: r.is_leader,
        }))
      : (solvers ?? []).map((s) => ({ key: s.name, solver: s.name, pub: null, priv: null, running: false, leader: false }));

  const top = Math.max(0.0001, ...groups.flatMap((g) => [g.pub ?? 0, finalized ? (g.priv ?? 0) : 0]));
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
            {groups.map((g) => (
              <div key={g.key} className="flex h-full items-end gap-1.5 sm:gap-2.5">
                <Cyl value={g.pub} height={g.pub == null ? 28 : h(g.pub)} kind={g.pub == null ? (g.running ? "loading" : "ghost") : "grey"} />
                <Cyl
                  value={finalized ? g.priv : null}
                  height={finalized ? h(g.priv) : g.pub != null ? h(g.pub) : 40}
                  kind={finalized && g.priv != null ? "brand" : g.pub != null ? "sealed" : g.running ? "loading" : "ghost"}
                />
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3 flex justify-around px-2">
          {groups.map((g) => (
            <span key={g.key} className={cx("max-w-[33%] truncate text-center text-[12px]", g.leader && finalized ? "font-medium text-foreground" : "text-muted")}>
              {solverShort(g.solver)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Cyl({ value, height, kind }: { value: number | null; height: number; kind: "grey" | "brand" | "sealed" | "loading" | "ghost" }) {
  return (
    <div className="relative flex h-full w-6 flex-col justify-end sm:w-9">
      {value != null && (kind === "grey" || kind === "brand") ? (
        <span className={cx("num absolute inset-x-[-12px] text-center text-[10px] leading-none transition-[bottom] duration-700 sm:text-[11px]", kind === "brand" ? "text-foreground" : "text-muted")} style={{ bottom: `calc(${height}% + 8px)` }}>
          {Math.round(value * 100)}
        </span>
      ) : null}
      {kind === "sealed" ? (
        <span className="absolute inset-x-0 flex justify-center text-muted" style={{ bottom: `calc(${height}% + 6px)` }}>
          <Lock className="h-3 w-3" />
        </span>
      ) : null}
      <div
        className={cx(
          "cyl w-full",
          kind === "grey" && "cyl-grey",
          kind === "brand" && "cyl-brand",
          (kind === "sealed" || kind === "ghost") && "cyl-sealed",
          kind === "ghost" && "opacity-50",
          kind === "loading" && "shimmer cyl-sealed",
        )}
        style={{ height: `${height}%` }}
      />
    </div>
  );
}
