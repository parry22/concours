"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { NextStep, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, Spinner, cx } from "@/components/ui";
import { api, errorText, type DockerStatus, type LeaderboardOut, type PackageOut, type SolverOut, type SubmissionOut } from "@/lib/api";
import { openArenaStream } from "@/lib/sse";
import { fmtScore, solverLabel } from "@/lib/format";

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
  const [pkg, setPkg] = useState<PackageOut | null>(null);
  const [validating, setValidating] = useState(false);
  const [validateOpen, setValidateOpen] = useState(false);
  const [validateError, setValidateError] = useState<string | null>(null);
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
    api.solvers().then(setSolvers).catch(() => setSolvers([]));
    api.docker().then(setDocker).catch(() => setDocker({ available: false, info: "Could not check Docker." }));
    api.arenaStatus(project.id).then((s) => setRunning(s.running)).catch(() => undefined);
    api.packageGet(project.id).then(setPkg).catch(() => setPkg(null));
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
    if (logOpen) logEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, logOpen]);

  async function run() {
    setStarting(true);
    setError(null);
    try {
      await api.arenaRun(project.id, { replay: true });
      setRunning(true);
      setLogOpen(true);
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

  async function validate() {
    setValidating(true);
    setValidateError(null);
    setValidateOpen(true);
    try {
      const p = await api.packageBuild(project.id);
      setPkg(p);
      await refresh();
    } catch (e) {
      setValidateError(errorText(e));
    } finally {
      setValidating(false);
    }
  }

  const scored = board?.submissions ?? [];
  const rows: Row[] = [...scored, ...pending.filter((p) => !scored.some((s) => s.id === p.id))];
  const sorted = rows.slice().sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  const finalized = Boolean(board?.finalized);
  const hasScores = scored.some((s) => s.status === "scored");
  const validation = pkg?.validation ?? project.apex_validation ?? "not_run";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Arena</h1>
          <p className="mt-1 max-w-2xl text-muted">
            Local solvers stand in for the global network. Each one trains on the public split and is scored by the referee in a
            sandbox. Private scores stay hidden until you finalize.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ValidateBadge status={validation} busy={validating} onClick={() => (pkg || validating ? setValidateOpen((o) => !o) : void validate())} />
          <Button variant="secondary" busy={starting} disabled={running || !project.protect} onClick={() => void run()}>
            {running ? "Running local solvers" : hasScores ? "Run local solvers again" : "Run local solvers"}
          </Button>
          <Button busy={finalizing} disabled={finalized || running || !hasScores} onClick={() => void finalize()}>
            {finalized ? "Finalized" : "Finalize"}
          </Button>
        </div>
      </div>

      {!project.protect ? <Alert kind="warn">Run data protection first.</Alert> : null}
      {docker && !docker.available ? (
        <Alert kind="warn">
          Docker is not available: {docker.info || "unknown reason"}. Cached results can still be replayed. New solver runs need Docker Desktop running.
        </Alert>
      ) : null}
      {error ? <Alert>{error}</Alert> : null}

      {board?.business_card ? (
        <div className="pop-in rounded-2xl bg-accent px-8 py-7 text-accent-ink">
          <div className="text-xs font-medium uppercase tracking-wide opacity-80">{finalized ? "Result on the private holdout" : "Result so far on the public leaderboard"}</div>
          <div className="mt-2 text-2xl font-semibold leading-snug md:text-3xl">{board.business_card}</div>
          {board.raw_metric_line ? <div className="mt-2 text-xs opacity-75">{board.raw_metric_line}</div> : null}
          {board.savings_line ? (
            <div className="mt-4 inline-flex cursor-help items-center gap-2 rounded-lg bg-white/15 px-3 py-1.5 text-sm" title={board.savings_formula || undefined}>
              {board.savings_line}
              <span className="text-xs opacity-75">hover for the formula</span>
            </div>
          ) : null}
        </div>
      ) : null}

      <ValidateDrawer open={validateOpen} pkg={pkg} busy={validating} error={validateError} onClose={() => setValidateOpen(false)} onRerun={() => void validate()} />

      <Card
        title="Leaderboard"
        subtitle={
          finalized
            ? `Private scores revealed. Winner: ${board?.leader ? solverLabel(board.leader.solver) : "none"}.`
            : `Public scores update live. A new leader must beat the top score by at least ${Math.round((board?.takeover_margin ?? 0.01) * 100)}%.`
        }
        actions={
          <span className={cx("flex items-center gap-2 text-xs", connected ? "text-ok" : "text-muted")}>
            <span className={cx("h-2 w-2 rounded-full", connected ? "bg-ok" : "bg-stone-300")} />
            {connected ? "live" : "reconnecting"}
          </span>
        }
      >
        {sorted.length === 0 ? (
          <Empty>
            {solvers && solvers.length > 0
              ? `No submissions yet. Run the ${solvers.length} local solvers: ${solvers.map((s) => solverLabel(s.name)).join(", ")}.`
              : "No submissions yet."}
          </Empty>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-stone-50 text-xs text-muted">
                <tr>
                  <th className="w-14 px-4 py-2 font-medium">Rank</th>
                  <th className="px-4 py-2 font-medium">Local solver</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium">Public score</th>
                  <th className="px-4 py-2 text-right font-medium">Private score</th>
                  <th className="px-4 py-2 font-medium">In business terms</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => {
                  const fresh = !seen.current.has(r.id);
                  if (!fresh && r.status === "scored") seen.current.add(r.id);
                  if (fresh) seen.current.add(r.id);
                  return (
                    <tr key={r.id} className={cx("border-t border-border", fresh && "row-in", r.is_leader && finalized && "bg-accent-soft/50")}>
                      <td className="px-4 py-3 tabular-nums">{r.rank ?? ""}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 font-medium">
                          {solverLabel(r.solver)}
                          {r.is_leader && finalized ? <Badge tone="accent">Winner</Badge> : r.is_leader ? <Badge tone="neutral">Leading</Badge> : null}
                          {r.solver === "baseline_logreg" ? <Badge tone="neutral">baseline</Badge> : null}
                        </div>
                        {r.error ? <div className="mt-1 text-xs text-danger">{r.error}</div> : null}
                      </td>
                      <td className="px-4 py-3">
                        <StatusCell status={r.status} />
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.public_score != null ? fmtScore(r.public_score) : ""}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {finalized ? (
                          r.private_score != null ? (
                            fmtScore(r.private_score)
                          ) : (
                            ""
                          )
                        ) : (
                          <span className="text-xs text-muted">revealed on finalize</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">{r.business_value || ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {board?.baseline && board.leader && finalized ? (
          <p className="mt-3 text-xs text-muted">
            Winner chosen on the private holdout, which no solver ever saw. Baseline is {solverLabel(board.baseline.solver)}.
          </p>
        ) : null}
      </Card>

      <Card
        title="Run log"
        subtitle="What the arena is doing, line by line."
        actions={
          <Button size="sm" variant="ghost" onClick={() => setLogOpen((o) => !o)}>
            {logOpen ? "Hide" : `Show (${logs.length})`}
          </Button>
        }
      >
        {logOpen ? (
          <pre className="max-h-72 overflow-auto rounded-xl bg-stone-900 p-4 font-mono text-xs leading-relaxed text-stone-100">
            {logs.length === 0 ? "No log lines yet." : logs.join("\n")}
            <div ref={logEnd} />
          </pre>
        ) : null}
      </Card>

      <NextStep stage="serve" disabled={!finalized} label={finalized ? undefined : "Finalize to use the winner"} />
    </div>
  );
}

function StatusCell({ status }: { status: SubmissionOut["status"] }) {
  if (status === "running")
    return (
      <span className="inline-flex items-center gap-2 text-xs text-muted">
        <Spinner className="h-3.5 w-3.5" /> running
      </span>
    );
  if (status === "queued") return <span className="text-xs text-muted">queued</span>;
  if (status === "failed") return <Badge tone="danger">failed</Badge>;
  return <Badge tone="ok">scored</Badge>;
}

function ValidateBadge({ status, busy, onClick }: { status: "pass" | "fail" | "not_run"; busy: boolean; onClick: () => void }) {
  const tone = status === "pass" ? "ok" : status === "fail" ? "danger" : "neutral";
  const label = status === "pass" ? "pass" : status === "fail" ? "fail" : "not run";
  return (
    <button
      onClick={onClick}
      className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm hover:bg-stone-50"
      title="Builds the competition package and runs the Apex toolkit checks"
    >
      {busy ? <Spinner className="h-4 w-4" /> : null}
      <span>Validate with Apex toolkit</span>
      <Badge tone={tone}>{busy ? "running" : label}</Badge>
    </button>
  );
}

function ValidateDrawer({
  open,
  pkg,
  busy,
  error,
  onClose,
  onRerun,
}: {
  open: boolean;
  pkg: PackageOut | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onRerun: () => void;
}) {
  if (!open) return null;
  return (
    <Card
      className="pop-in"
      title="Apex toolkit validation"
      subtitle="Builds the competition package, then runs the toolkit's preflight and screen checks and a local referee run."
      actions={
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" busy={busy} onClick={onRerun}>
            Run again
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      {error ? <Alert className="mb-3">{error}</Alert> : null}
      {busy && !pkg ? (
        <div className="flex items-center gap-3 text-sm text-muted">
          <Spinner className="h-4 w-4" /> Building the package and running the checks. About 20 seconds.
        </div>
      ) : null}
      {pkg ? (
        <ol className="space-y-3">
          {pkg.steps.map((s) => (
            <li key={s.name} className="rounded-xl border border-border p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{s.name}</span>
                <Badge tone={s.status === "pass" ? "ok" : s.status === "fail" ? "danger" : "neutral"}>{s.status.replace("_", " ")}</Badge>
              </div>
              {s.log ? <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-stone-50 p-3 font-mono text-xs text-stone-700">{s.log}</pre> : null}
            </li>
          ))}
        </ol>
      ) : null}
      {pkg ? <p className="mt-3 text-xs text-muted">Package id {pkg.competition_id}. {pkg.files.length} files ready for handoff.</p> : null}
    </Card>
  );
}
