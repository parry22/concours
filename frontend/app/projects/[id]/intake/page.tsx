"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, Check, RotateCcw, SlidersHorizontal } from "lucide-react";
import { ActionBar, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Field, Logo, Segments, Skeleton, cx, inputClass } from "@/components/ui";
import { api, errorText, type IntakeMessage, type IntakeStatus, type ProblemSpec, type TemplateOut } from "@/lib/api";
import { specConfirmed, stepHref } from "@/lib/stages";
import { fmtInt, fmtMoney, metricLabel, rawMetricLabel } from "@/lib/format";
import { intake as copy } from "@/lib/copy";

type ChatMessage = IntakeMessage & { source?: "llm" | "cache" | "defaults" };

function emptySpec(template: ProblemSpec["template"]): ProblemSpec {
  return {
    template,
    task_type: "binary",
    target_column: "",
    positive_label: null,
    time_column: null,
    primary_metric: template === "fraud" || template === "custom" ? "recall_at_fpr" : "recall_at_top_k",
    metric_params: template === "fraud" || template === "custom" ? { fpr: 0.001 } : { top_k: 0.1 },
    secondary_metric: null,
    metric_rationale: "",
    business_template: template === "fraud" || template === "custom" ? "fraud" : "churn",
    constraints: { max_ms_per_row: 5 },
    economics: null,
  };
}

export default function IntakePage() {
  const { project, setProject, refresh } = useProject();
  const router = useRouter();
  const [history, setHistory] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [status, setStatus] = useState<IntakeStatus | null>(null);
  const [template, setTemplate] = useState<TemplateOut | null>(null);
  const [spec, setSpec] = useState<ProblemSpec>(project.spec ?? emptySpec(project.template));
  const [confirming, setConfirming] = useState(false);
  const [specError, setSpecError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [tab, setTab] = useState<"chat" | "rule">("chat");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .intakeHistory(project.id)
      .then((h) => {
        setHistory(h);
        // Start the rule empty so it visibly fills as the chat goes, unless it was already agreed.
        if (h.length === 0 && !specConfirmed(project)) setSpec(emptySpec(project.template));
      })
      .catch((e) => {
        setHistory([]);
        setChatError(errorText(e));
      });
    api.intakeStatus().then(setStatus).catch(() => setStatus(null));
    api
      .templates()
      .then((ts) => setTemplate(ts.find((t) => t.id === project.template) ?? null))
      .catch(() => setTemplate(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [history, sending]);

  async function send(text: string) {
    text = text.trim();
    if (!text || sending) return;
    setSending(true);
    setChatError(null);
    setHistory((h) => [...(h || []), { role: "user", content: text }]);
    setDraft("");
    try {
      const r = await api.intake(project.id, text);
      setHistory([...r.history.slice(0, -1), { ...r.history[r.history.length - 1], source: r.source }]);
      if (r.spec) setSpec(r.spec);
      if (r.done) {
        setDone(true);
        setTab("rule");
        await refresh();
      }
    } catch (e) {
      setChatError(errorText(e));
    } finally {
      setSending(false);
    }
  }

  async function reset() {
    setChatError(null);
    try {
      await api.intakeReset(project.id);
      setHistory([]);
      setDone(false);
      setTab("chat");
      await refresh();
      setSpec(emptySpec(project.template));
    } catch (e) {
      setChatError(errorText(e));
    }
  }

  async function confirm() {
    setConfirming(true);
    setSpecError(null);
    try {
      const body: ProblemSpec = {
        ...spec,
        economics: spec.economics
          ? { ...spec.economics, positive_rate: project.profile?.positive_rate ?? spec.economics.positive_rate ?? null }
          : project.profile?.positive_rate != null
            ? { positive_rate: project.profile.positive_rate }
            : null,
      };
      const p = await api.putSpec(project.id, body);
      setProject(p);
      router.push(stepHref(p.id, "protect"));
    } catch (e) {
      setSpecError(errorText(e));
      setTab("rule");
      setConfirming(false);
    }
  }

  const columns = project.profile?.columns.map((c) => c.name) ?? [];
  const params = (spec.metric_params ?? {}) as Record<string, unknown>;
  const constraints = (spec.constraints ?? {}) as Record<string, unknown>;
  const econ = (spec.economics ?? {}) as Record<string, unknown>;
  const isChurn = spec.business_template === "churn";
  const userTurns = history?.filter((m) => m.role === "user").length ?? 0;
  const confirmed = specConfirmed(project);
  const offline = status ? status.offline || !status.has_key : null;

  const parts = {
    outcome: Boolean(spec.target_column),
    score: Boolean(spec.target_column) && (userTurns >= 2 || done || confirmed),
    split: Boolean(spec.target_column),
    econ: econ.value_per_positive != null || econ.cost_per_action != null || econ.cost_per_false_positive != null || econ.rows_per_month != null,
  };
  const agreed = Object.values(parts).filter(Boolean).length;

  const suggestions: string[] = (() => {
    if (!history || done || sending) return [];
    const script = template?.replies;
    if (script) return script[userTurns] ? [script[userTurns]] : [];
    if (userTurns === 0) return ["I want to predict which rows end in a positive outcome."];
    return (project.profile?.target_candidates ?? []).slice(0, 3).map((c) => `The outcome is ${c}.`);
  })();

  function patch(p: Partial<ProblemSpec>) {
    setSpec((s) => ({ ...s, ...p }));
  }

  const chat = (
    <Card pad={false} className={cx("flex flex-col lg:col-span-7", tab !== "chat" && "hidden lg:flex")}>
      <header className="flex items-start justify-between gap-3 px-4 pt-4 sm:px-5 sm:pt-5">
        <div className="flex min-w-0 items-center gap-3">
          <Logo className="h-6 w-[19px] shrink-0" />
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold">{copy.assistant}</h2>
            <p className="truncate text-[12px] text-muted">{offline === null ? copy.analyst : offline ? copy.offline : copy.live(status?.model ?? "")}</p>
          </div>
        </div>
        {history && history.length > 0 ? (
          <Button size="sm" variant="ghost" onClick={() => void reset()} disabled={sending}>
            <RotateCcw className="h-3.5 w-3.5" />
            {copy.startOver}
          </Button>
        ) : null}
      </header>

      <div ref={listRef} className="scroll-thin mt-3 flex max-h-[48dvh] min-h-[200px] flex-1 flex-col gap-3 overflow-y-auto px-4 pb-2 sm:px-5 lg:h-[460px] lg:max-h-none">
        {history === null ? (
          <div className="space-y-3 pt-2">
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="ml-auto h-10 w-1/2" />
          </div>
        ) : history.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-4 text-center sm:py-8">
            <p className="text-[18px] font-semibold tracking-[-0.01em]">{copy.whatPredict}</p>
            <p className="max-w-sm text-[13px] leading-relaxed text-muted">{copy.sayIt}</p>
          </div>
        ) : (
          history.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="row-in flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-3.5 py-2.5 text-[14px] leading-relaxed text-background">{m.content}</div>
              </div>
            ) : (
              <div key={i} className="row-in flex items-end gap-2.5">
                <Logo className="mb-1.5 h-5 w-4 shrink-0" />
                <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-border bg-card-2 px-3.5 py-2.5 text-[14px] leading-relaxed">
                  <div className="whitespace-pre-wrap">{m.content}</div>
                  {m.source && m.source !== "llm" ? <div className="mt-1.5 text-[11px] text-muted">{copy.replayed}</div> : null}
                </div>
              </div>
            ),
          )
        )}
        {sending ? (
          <div className="flex items-end gap-2.5">
            <Logo className="mb-1.5 h-5 w-4 shrink-0" />
            <div className="flex h-10 items-center gap-1 rounded-2xl rounded-bl-md border border-border bg-card-2 px-4">
              {[0, 1, 2].map((d) => (
                <span key={d} className="pulse-dot h-1.5 w-1.5 rounded-full bg-subtle" style={{ animationDelay: `${d * 180}ms` }} />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="px-4 pb-4 sm:px-5 sm:pb-5">
        {suggestions.length > 0 ? (
          <div className="mb-3 flex flex-col items-start gap-2">
            {suggestions.map((s, i) => (
              <button
                key={s}
                onClick={() => void send(s)}
                disabled={!project.has_data}
                className={cx(
                  "fade-in flex max-w-full items-start gap-2.5 rounded-xl border bg-card-2 py-2 pr-3.5 pl-2 text-left text-[13px] leading-snug transition-colors hover:bg-card-3",
                  i === 0 ? "border-dashed border-[#55555c]" : "border-border",
                )}
              >
                <span className="num mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-card-3 text-[11px] text-subtle">{userTurns + i + 1}</span>
                <span>{s}</span>
              </button>
            ))}
          </div>
        ) : null}
        {chatError ? <Alert className="mb-3">{chatError}</Alert> : null}
        {done ? (
          <Alert kind="ok" className="mb-3">
            {copy.ruleDone}
          </Alert>
        ) : null}
        <form
          className="flex items-center gap-2 rounded-2xl border border-border-strong bg-card-2 p-1.5 pl-4 transition-colors focus-within:border-accent/60"
          onSubmit={(e) => {
            e.preventDefault();
            void send(draft);
          }}
        >
          <input
            className="h-9 min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-muted"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={history?.length ? copy.reply : template?.goal ? copy.describeOrTap : copy.describe}
            disabled={sending || !project.has_data}
            enterKeyHint="send"
            aria-label={copy.reply}
          />
          <button
            type="submit"
            disabled={!draft.trim() || sending || !project.has_data}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-foreground text-background transition-[opacity,transform] active:scale-95 disabled:opacity-30"
            aria-label={copy.send}
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </form>
        {!project.has_data ? <p className="mt-2 text-[12px] text-muted">{copy.uploadFirst}</p> : null}
      </div>
    </Card>
  );

  const rule = (
    <div className={cx("min-w-0 space-y-3 lg:col-span-5", tab !== "rule" && "hidden lg:block")}>
      <Card
        title={copy.rule}
        subtitle={copy.ruleSub}
        actions={confirmed ? <Badge tone="ok" dot>{copy.saved}</Badge> : null}
      >
        <div className="mb-4 flex items-center gap-3">
          <Segments total={4} filled={agreed} size="sm" className="flex-1" />
          <span className="num shrink-0 text-[12px] text-muted">{copy.agreed(agreed, 4)}</span>
        </div>
        <ul className="space-y-2">
          <RulePart done={parts.outcome} label={copy.whatWePredict}>
            {spec.target_column ? (
              <span className="num text-[14px]">
                {spec.target_column} <span className="text-muted">=</span> {spec.positive_label == null ? "?" : String(spec.positive_label)}
              </span>
            ) : (
              <span className="text-muted">{copy.waiting}</span>
            )}
          </RulePart>
          <RulePart done={parts.score} label={copy.howWeScore}>
            <span className={cx(!parts.score && "text-muted")}>{spec.metric_rationale || metricLabel(spec.primary_metric, params)}</span>
            <span className="num mt-1 block text-[11px] text-muted">{rawMetricLabel(spec.primary_metric, params)}</span>
          </RulePart>
          <RulePart done={parts.split} label={copy.howWeSplit}>
            {spec.time_column ? (
              <span>
                {copy.byTime} <span className="num">{spec.time_column}</span>, {copy.neverFuture}
              </span>
            ) : (
              <span className={cx(!parts.split && "text-muted")}>{copy.random}</span>
            )}
          </RulePart>
          <RulePart done={parts.econ} label={copy.worth}>
            {parts.econ ? (
              <span className="num text-[13px]">
                {[
                  econ.value_per_positive != null ? `${fmtMoney(Number(econ.value_per_positive))} ${isChurn ? "kept per saved customer" : "per case"}` : null,
                  econ.cost_per_action != null ? `${fmtMoney(Number(econ.cost_per_action))} ${isChurn ? "per contact" : "to handle a flag"}` : null,
                  econ.cost_per_false_positive != null ? `${fmtMoney(Number(econ.cost_per_false_positive))} per wrong flag` : null,
                  econ.rows_per_month != null ? `${fmtInt(Number(econ.rows_per_month))}/mo` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            ) : (
              <span className="text-muted">{copy.worthOptional}</span>
            )}
          </RulePart>
        </ul>
      </Card>

      <details className="group rounded-2xl border border-border bg-card">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 sm:px-5 [&::-webkit-details-marker]:hidden">
          <span className="flex items-center gap-2.5 text-[14px] font-medium">
            <SlidersHorizontal className="h-4 w-4 text-muted" />
            {copy.fineTune}
          </span>
          <span className="text-[12px] text-muted group-open:hidden">{copy.editable}</span>
          <span className="hidden text-[12px] text-muted group-open:inline">{copy.hide}</span>
        </summary>
        <div className="space-y-4 border-t border-border px-4 py-4 sm:px-5">
          <Field label={copy.fields.outcome}>
            <select className={inputClass} value={spec.target_column} onChange={(e) => patch({ target_column: e.target.value })}>
              <option value="">{copy.fields.choose}</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={copy.fields.yesValue}>
              <input
                className={inputClass}
                value={spec.positive_label == null ? "" : String(spec.positive_label)}
                onChange={(e) => {
                  const v = e.target.value;
                  patch({ positive_label: v === "" ? null : /^-?\d+$/.test(v) ? Number(v) : v });
                }}
                placeholder="1"
              />
            </Field>
            <Field label={copy.fields.task}>
              <select className={inputClass} value={spec.task_type} onChange={(e) => patch({ task_type: e.target.value as ProblemSpec["task_type"] })}>
                <option value="binary">{copy.fields.yesNo}</option>
                <option value="regression">{copy.fields.number}</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label={copy.fields.metric}>
              <select
                className={inputClass}
                value={spec.primary_metric}
                onChange={(e) => {
                  const m = e.target.value as ProblemSpec["primary_metric"];
                  patch({
                    primary_metric: m,
                    metric_params: m === "recall_at_fpr" ? { fpr: Number(params.fpr ?? 0.001) } : m === "recall_at_top_k" ? { top_k: Number(params.top_k ?? 0.1) } : {},
                  });
                }}
              >
                <option value="recall_at_fpr">{copy.fields.caughtAt}</option>
                <option value="recall_at_top_k">{copy.fields.foundIn}</option>
                <option value="wape">{copy.fields.error}</option>
              </select>
            </Field>
            {spec.primary_metric === "recall_at_fpr" ? (
              <Field label={copy.fields.falseAlarms}>
                <input
                  className={inputClass}
                  type="number"
                  inputMode="decimal"
                  step="0.1"
                  min="0.1"
                  value={Number(params.fpr ?? 0.001) * 1000}
                  onChange={(e) => patch({ metric_params: { fpr: Number(e.target.value) / 1000 } })}
                />
              </Field>
            ) : spec.primary_metric === "recall_at_top_k" ? (
              <Field label={copy.fields.riskiestShare}>
                <input
                  className={inputClass}
                  type="number"
                  inputMode="numeric"
                  step="1"
                  min="1"
                  max="100"
                  value={Math.round(Number(params.top_k ?? 0.1) * 100)}
                  onChange={(e) => patch({ metric_params: { top_k: Number(e.target.value) / 100 } })}
                />
              </Field>
            ) : (
              <div />
            )}
          </div>
          <Field label={copy.fields.timeColumn} hint={copy.fields.timeHint}>
            <select className={inputClass} value={spec.time_column ?? ""} onChange={(e) => patch({ time_column: e.target.value || null })}>
              <option value="">{copy.fields.none}</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                ["rows_per_month", isChurn ? "Customers / month" : "Rows / month", "numeric"],
                ["value_per_positive", isChurn ? "Kept per saved customer ($)" : "Amount per case ($)", "decimal"],
                ["cost_per_action", isChurn ? "Per contact ($)" : "To handle a flag ($)", "decimal"],
                ["cost_per_false_positive", "Per wrong flag ($)", "decimal"],
              ] as const
            ).map(([key, label, mode]) => (
              <Field key={key} label={label}>
                <input
                  className={inputClass}
                  type="number"
                  inputMode={mode}
                  min="0"
                  value={econ[key] == null ? "" : Number(econ[key])}
                  onChange={(e) => patch({ economics: { ...econ, [key]: e.target.value === "" ? null : Number(e.target.value) } })}
                />
              </Field>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label={copy.fields.maxMs}>
              <input
                className={inputClass}
                type="number"
                inputMode="numeric"
                min="1"
                value={Number(constraints.max_ms_per_row ?? 5)}
                onChange={(e) => patch({ constraints: { ...constraints, max_ms_per_row: Number(e.target.value) } })}
              />
            </Field>
          </div>
        </div>
      </details>
      {specError ? <Alert>{specError}</Alert> : null}
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[22px] font-semibold tracking-[-0.02em] sm:text-[26px]">{copy.title}</h1>
          <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-subtle">{copy.sub}</p>
        </div>
        <div className="flex rounded-xl border border-border bg-card p-1 lg:hidden" role="tablist">
          {(
            [
              ["chat", copy.chat],
              ["rule", copy.ruleTab(agreed)],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={cx("h-9 flex-1 rounded-lg px-4 text-[13px] font-medium transition-colors", tab === k ? "bg-card-3 text-foreground" : "text-muted")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {chat}
        {rule}
      </div>

      <ActionBar hint={spec.target_column ? copy.hintConfirm : copy.hintAnswer}>
        <Button size="lg" busy={confirming} disabled={!spec.target_column || confirming} onClick={() => void confirm()}>
          {copy.confirm}
          <Check className="h-4 w-4" />
        </Button>
      </ActionBar>
    </div>
  );
}

function RulePart({ done, label, children }: { done: boolean; label: string; children: ReactNode }) {
  return (
    <li className={cx("flex gap-3 rounded-xl border px-3.5 py-3 transition-colors duration-300", done ? "border-border-strong bg-card-2" : "border-dashed border-border")}>
      <span
        className={cx(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors duration-300",
          done ? "bg-brand text-background" : "border border-dashed border-[#4a4a50]",
        )}
      >
        {done ? <Check className="h-3 w-3" strokeWidth={3} /> : null}
      </span>
      <div className="min-w-0 text-[13px] leading-relaxed">
        <div className="mb-0.5 text-[12px] font-medium text-muted">{label}</div>
        {children}
      </div>
    </li>
  );
}
