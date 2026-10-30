"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, KeyRound, Lock, Play, RotateCcw, ShieldCheck, Terminal, Trash2, Trophy, X } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, ResultFigure, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type ApexStatus, type ChainOut, type DockerStatus, type GateResult, type LeaderboardOut, type ModelVersionOut, type SolverKey, type SolverOut, type SubmissionOut } from "@/lib/api";
import { openArenaStream } from "@/lib/sse";
import { attemptLabel, fmtAgo } from "@/lib/format";
import { apexStatus as apexCopy, chain as chainCopy, gates as gateCopy, improve as copy, solvers as solverCopy } from "@/lib/copy";

const money = (x: number | null | undefined) => (x == null ? "–" : `${x < 0 ? "-" : ""}$${Math.abs(Math.round(x)).toLocaleString("en-US")}`);

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
  const [chain, setChain] = useState<ChainOut | null>(null);
  const [apex, setApex] = useState<ApexStatus | null>(null);
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
    api.apexStatus().then(setApex).catch(() => setApex(null));
  }, [project.id, loadBoard]);

  // the Bittensor network's state while a validator reports it (outside solvers' attempts also arrive on the live stream)
  useEffect(() => {
    const load = () => api.chain(project.id).then(setChain).catch(() => setChain(null));
    void load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [project.id, boardVersion]);

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
          setPending((p) => (p.some((r) => r.id === ev.id) ? p : [...p, { id: ev.id, solver: ev.solver, status: "running", logs_path: "", is_leader: false, placeholder: true, gates: [], champion: false, origin: "local" }]));
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
      // The backend picks the fraud round: the current model re-scored when the data moved, then the local solvers.
      await api.arenaRun(project.id, { replay: true });
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
  const contestCount = 2;
  const isChampion = (r: Row) => !versionBySub.get(r.id) && r.solver === active?.solver_name && !r.gates?.length;
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
                  <span>{copy.perDayLabel(project.fraud_settings?.daily_capacity ?? 200)}</span>
                </span>
              }
              value={money(active.private_score)}
              line={active.improvement_line}
              delta={v1 && active.version > 1 && active.private_score > v1.private_score ? <Badge tone="accent" className="num">+{money(active.private_score - v1.private_score)}</Badge> : null}
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
              {apex ? (
                <Badge tone={apex.live ? "accent" : "neutral"} dot={apex.live} title={apexCopy.detail[apex.mode]}>
                  {apexCopy.modes[apex.mode]}
                </Badge>
              ) : null}
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
        <Card pad={false} className="lg:col-span-8" title={copy.attempts} subtitle={gateCopy.sub} actions={<Badge tone={chain?.netuid != null ? "accent" : undefined}>{chain?.netuid != null ? chainCopy.badge(chain.network ?? "test", chain.netuid) : copy.localSolvers}</Badge>}>
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
                const champ = isChampion(r);
                if (!ver && !champ && !r.solver.startsWith("agent_solver")) attemptIndex += 1;
                return (
                  <li key={r.id} className={cx("flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5", fresh && "row-in", isActive && "bg-[linear-gradient(90deg,rgb(167_139_250/0.08),transparent_60%)]")}>
                    <span className={cx("num flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border text-[12px]", isActive ? "bg-brand border-transparent text-background" : "border-border-strong bg-card-2 text-subtle")}>
                      {ver ? `v${ver.version}` : (r.rank ?? "–")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="truncate text-[14px] font-medium">{isV1 ? copy.v1 : ver ? `Version ${ver.version}` : champ ? gateCopy.champion : r.origin === "chain" ? chainCopy.solver(r.uid) : r.origin === "direct" ? solverCopy.solver(r.submitted_by) : r.origin === "apex_local" || r.origin === "apex_actions" ? apexCopy.attempt(attemptIndex) : attemptLabel(r.solver, attemptIndex)}</span>
                        {r.origin === "chain" && ver ? <span className="text-[12px] text-muted">{chainCopy.solver(r.uid)}</span> : r.origin === "direct" && ver ? <span className="text-[12px] text-muted">{solverCopy.solver(r.submitted_by)}</span> : null}
                        {isActive ? <Badge tone="accent">{copy.active}</Badge> : ver ? <Badge>v{ver.version}</Badge> : r.is_leader ? <Badge>{copy.leading}</Badge> : null}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-muted sm:truncate">{r.error ? <span className="text-danger">{r.error}</span> : r.origin === "chain" ? chainCopy.minerLine(r.hotkey ?? "", r.chain_block) : r.origin === "direct" ? solverCopy.line : r.origin === "apex_local" ? apexCopy.attemptLine : r.origin === "apex_actions" ? apexCopy.actionsLine : r.status === "scored" ? copy.perDayLabel(project.fraud_settings?.daily_capacity ?? 200) : <StatusText status={r.status} />}</div>
                      {r.gates?.length ? <GateChips gates={r.gates} /> : null}
                    </div>
                    <div className="grid shrink-0 grid-cols-2 items-end gap-4 text-right sm:gap-6">
                      <div>
                        <div className="text-[11px] text-muted">{copy.businessValue}</div>
                        <div className={cx("num text-[18px] leading-none font-medium", isActive ? "text-gradient" : "text-foreground")}>
                          {r.private_score != null ? money(r.private_score) : r.status === "running" ? <Spinner className="ml-auto h-3.5 w-3.5" /> : "–"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-muted">{copy.rawMetric}</div>
                        <div className="num text-[11px] text-muted">{r.public_score != null ? money(r.public_score) : "–"}</div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="min-w-0 space-y-4 lg:col-span-4">
          {chain?.netuid != null ? <SubnetCard chain={chain} /> : null}
          <SolversCard projectId={project.id} />
          <Card title={gateCopy.title} actions={<ShieldCheck className="icon-brand h-4 w-4" />}>
            <ol className="space-y-2.5 text-[13px]">
              {gateCopy.list.map((g, i) => (
                <li key={g.name} className="flex gap-2.5">
                  <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong text-[10px] text-subtle">{i + 1}</span>
                  <span>
                    <span className="font-medium">{g.name}.</span> <span className="text-subtle">{g.text}</span>
                  </span>
                </li>
              ))}
            </ol>
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

const short = (k: string | null | undefined) => (k ? `${k.slice(0, 5)}…${k.slice(-4)}` : "–");

/** The Bittensor network this project runs on: where, which outside solver holds the weights, what the validator last did. */
function SubnetCard({ chain }: { chain: ChainOut }) {
  const weights = Object.entries(chain.weights ?? {});
  const top = weights.sort((a, b) => b[1] - a[1])[0];
  const rows: [string, React.ReactNode][] = [
    [chainCopy.network, <span key="n" className="num">{chainCopy.networkName(chain.network ?? "test")} · netuid {chain.netuid}</span>],
    [chainCopy.block, <span key="b" className="num">{chain.block?.toLocaleString("en-US") ?? "–"}</span>],
    [chainCopy.solvers, <span key="m" className="num">{chain.solvers ?? 0}</span>],
    [chainCopy.winner, chain.winner_uid != null ? <span key="w" className="num">uid {chain.winner_uid} · {short(chain.winner_hotkey)}</span> : <span key="w" className="text-muted">{chainCopy.noWinner}</span>],
    [chainCopy.weights, top ? <span key="x" className="num">uid {top[0]}{chain.weights_block ? ` · block ${chain.weights_block.toLocaleString("en-US")}` : ""}</span> : <span key="x" className="text-muted">{chainCopy.noWeights}</span>],
    [chainCopy.validator, <span key="v" className="num">{short(chain.validator_hotkey)}</span>],
  ];
  return (
    <Card title={chainCopy.title} subtitle={chainCopy.sub} actions={<Badge tone="accent">{chainCopy.live}</Badge>}>
      <dl className="space-y-2 text-[13px]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3">
            <dt className="text-subtle">{k}</dt>
            <dd className="min-w-0 truncate text-right">{v}</dd>
          </div>
        ))}
      </dl>
      {chain.note ? <p className="mt-3 border-t border-border pt-3 text-[12px] text-muted">{chain.note}</p> : null}
    </Card>
  );
}

/** Keys for outside solvers: one per person, shown once, revocable. Their attempts land in the list above. */
function SolversCard({ projectId }: { projectId: string }) {
  const [keys, setKeys] = useState<SolverKey[] | null>(null);
  const [fresh, setFresh] = useState<SolverKey | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const load = useCallback(() => api.solverKeys(projectId).then(setKeys).catch((e) => setErr(errorText(e))), [projectId]);
  useEffect(() => {
    void load();
  }, [load]);
  const act = async (id: string, fn: () => Promise<void>) => {
    setBusy(id);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Card title={solverCopy.title} subtitle={solverCopy.sub} actions={<Badge>{solverCopy.badge}</Badge>}>
      {err ? <Alert>{err}</Alert> : null}
      {fresh?.token ? (
        <div className="mb-3 rounded-xl border border-border-strong bg-card-2 p-3">
          <div className="text-[12px] font-medium">{solverCopy.freshTitle}</div>
          <div className="mt-2 flex items-center gap-2">
            <code className="num min-w-0 flex-1 truncate rounded-lg bg-background px-2.5 py-2 text-[12px]">{fresh.token}</code>
            <Button size="sm" variant="secondary" onClick={() => void navigator.clipboard?.writeText(fresh.token ?? "")}>
              <Copy className="h-3.5 w-3.5" />
              {solverCopy.copy}
            </Button>
          </div>
          <p className="num mt-2 text-[12px] leading-snug text-muted">{solverCopy.kitHint(origin)}</p>
        </div>
      ) : null}
      {!keys ? (
        <Skeleton className="h-12" />
      ) : (
        <ul className="divide-y divide-border">
          {keys.length === 0 ? <li className="py-1 text-[13px] text-muted">{solverCopy.none}</li> : null}
          {keys.map((k) => (
            <li key={k.id} className="flex items-center gap-3 py-2">
              <KeyRound className="h-4 w-4 shrink-0 text-muted" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">{k.name}</span>
                <span className="num block text-[11px] text-muted">
                  {k.prefix}… · {solverCopy.attempts(k.attempts)} · {k.last_used_at ? solverCopy.used(fmtAgo(k.last_used_at)) : solverCopy.neverUsed}
                </span>
              </span>
              <Button size="sm" variant="ghost" busy={busy === k.id} aria-label={solverCopy.revoke} onClick={() => void act(k.id, async () => {
                await api.revokeSolverKey(projectId, k.id);
                await load();
              })}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void act("create", async () => {
            setFresh(await api.createSolverKey(projectId, name.trim() || "Solver"));
            setName("");
            await load();
          });
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={solverCopy.name}
          className="h-9 min-w-0 flex-1 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] placeholder:text-muted" />
        <Button type="submit" size="sm" busy={busy === "create"}>{solverCopy.create}</Button>
      </form>
    </Card>
  );
}

function StatusText({ status }: { status: SubmissionOut["status"] }) {
  if (status === "running") return <>{copy.statusRunning}</>;
  if (status === "queued") return <>{copy.queued}</>;
  if (status === "failed") return <span className="text-danger">{copy.failed}</span>;
  return <>{copy.scored}</>;
}

/** Five gates as a segmented bar (the reference's score bar) with the deciding line; details open below. */
function GateChips({ gates }: { gates: GateResult[] }) {
  const passed = gates.filter((g) => g.passed).length;
  const first = gates.find((g) => !g.passed);
  return (
    <details className="group mt-2.5 max-w-[460px]">
      <summary className="flex cursor-pointer list-none items-center gap-3 [&::-webkit-details-marker]:hidden">
        <span className="flex w-[110px] shrink-0 gap-[3px]" aria-hidden>
          {gates.map((g) => (
            <span key={g.key} className={cx("h-1.5 flex-1 rounded-[2px]", g.passed ? "bg-brand-x" : "bg-danger/70")} />
          ))}
        </span>
        <span className="min-w-0 truncate text-[12px] text-subtle">
          {first ? (
            <>
              <span className="font-medium text-foreground">{first.name}:</span> {first.line}
            </>
          ) : (
            gateCopy.allPassed
          )}
        </span>
        <span className="num shrink-0 text-[11px] text-muted">{passed}/5</span>
      </summary>
      <ul className="mt-2.5 space-y-1.5 border-l border-border pl-3">
        {gates.map((g) => (
          <li key={g.key} className="flex items-start gap-2 text-[12px]">
            {g.passed ? <Check className="icon-brand mt-0.5 h-3 w-3 shrink-0" strokeWidth={3} /> : <X className="mt-0.5 h-3 w-3 shrink-0 text-danger" strokeWidth={3} />}
            <span className="min-w-0">
              <span className="font-medium">{g.name}.</span> <span className="text-muted">{g.line}</span>
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

const TICKS = [1, 0.75, 0.5, 0.25, 0];

/** Cylinder bars: business value per attempt (the private holdout score). The active version glows; versions are labelled. */
function AttemptChart({ rows, versionBySub }: { rows: Row[]; versionBySub: Map<string | null | undefined, ModelVersionOut> }) {
  let n = 0;
  const groups = rows.map((r) => {
    const ver = versionBySub.get(r.id);
    const value = r.private_score ?? null;
    if (!ver && !r.solver.startsWith("agent_solver")) n += 1;
    return { key: r.id, value: Number.isFinite(value as number) ? value : null, running: r.status === "running" || r.status === "queued", ver, label: ver ? `v${ver.version}` : r.solver.startsWith("agent_solver") ? attemptLabel(r.solver) : `Attempt ${n}` };
  });
  if (groups.length === 0) return null;
  const top = Math.max(1, ...groups.map((g) => g.value ?? 0));
  const step = top > 4000 ? 2000 : top > 1000 ? 1000 : 100;
  const max = Math.ceil((top * 1.15) / step) * step;
  const ticks = TICKS.map((t) => t * max);
  const h = (v: number | null) => (v == null ? 0 : Math.max(4, (v / max) * 100));
  return (
    <div className="mt-6 flex gap-3">
      <div className="flex h-[200px] shrink-0 flex-col justify-between pb-0 text-right sm:h-[240px]">
        {ticks.map((t) => (
          <span key={t} className="num -translate-y-1/2 text-[11px] leading-none text-muted first:translate-y-0 last:translate-y-0">
            {t >= 1000 ? `$${(t / 1000).toFixed(t % 1000 ? 1 : 0)}k` : `$${Math.round(t)}`}
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
                      {money(g.value)}
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
