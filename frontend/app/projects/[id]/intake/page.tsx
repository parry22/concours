"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { NextStep, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Field, Loading, inputClass } from "@/components/ui";
import { api, errorText, type IntakeMessage, type IntakeStatus, type ProblemSpec } from "@/lib/api";
import { TEMPLATE_GOAL, stepHref } from "@/lib/stages";
import { metricLabel, rawMetricLabel } from "@/lib/format";

type ChatMessage = IntakeMessage & { source?: "llm" | "cache" | "defaults" };

function emptySpec(template: ProblemSpec["template"]): ProblemSpec {
  return {
    template,
    task_type: "binary",
    target_column: "",
    positive_label: null,
    time_column: null,
    primary_metric: template === "churn" ? "recall_at_top_k" : "recall_at_fpr",
    metric_params: template === "churn" ? { top_k: 0.1 } : { fpr: 0.001 },
    secondary_metric: null,
    metric_rationale: "",
    business_template: template === "custom" ? "fraud" : template,
    constraints: { max_ms_per_row: 5, allowed_libs: ["scikit-learn", "lightgbm", "xgboost", "pandas", "numpy"] },
    economics: null,
  };
}

export default function IntakePage() {
  const { project, setProject, refresh } = useProject();
  const router = useRouter();
  const [history, setHistory] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState(TEMPLATE_GOAL[project.template] || "");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [status, setStatus] = useState<IntakeStatus | null>(null);
  const [spec, setSpec] = useState<ProblemSpec>(project.spec ?? emptySpec(project.template));
  const [confirming, setConfirming] = useState(false);
  const [specError, setSpecError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [done, setDone] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.intakeHistory(project.id)
      .then((h) => {
        setHistory(h);
        if (h.length > 0) setDraft("");
      })
      .catch((e) => {
      setHistory([]);
      setChatError(errorText(e));
    });
    api.intakeStatus().then(setStatus).catch(() => setStatus(null));
  }, [project.id]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [history]);

  async function send() {
    const text = draft.trim();
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
      setDraft(TEMPLATE_GOAL[project.template] || "");
      const p = await refresh();
      if (p?.spec) setSpec(p.spec);
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
      setConfirmed(true);
      router.push(stepHref(p.id, "protect"));
    } catch (e) {
      setSpecError(errorText(e));
    } finally {
      setConfirming(false);
    }
  }

  const columns = project.profile?.columns.map((c) => c.name) ?? [];
  const params = (spec.metric_params ?? {}) as Record<string, unknown>;
  const constraints = (spec.constraints ?? {}) as Record<string, unknown>;
  const econ = (spec.economics ?? {}) as Record<string, unknown>;
  const canConfirm = Boolean(spec.target_column) && !confirming;

  function patch(p: Partial<ProblemSpec>) {
    setSpec((s) => ({ ...s, ...p }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Describe the goal</h1>
        <p className="mt-1 text-muted">
          Tell Brief what you want in plain words. It asks at most three questions and fills the problem spec on the right.
          Every field can be edited by hand.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card
          className="flex min-h-[560px] flex-col lg:col-span-3"
          title="Chat"
          subtitle={
            status
              ? status.offline || !status.has_key
                ? "Offline mode: replies come from the saved script, not a live model."
                : `Live intake analyst (${status.model}). It sees column names, stats and masked sample rows, never the data.`
              : undefined
          }
          actions={
            history && history.length > 0 ? (
              <Button size="sm" variant="ghost" onClick={() => void reset()} disabled={sending}>
                Start over
              </Button>
            ) : null
          }
        >
          <div ref={listRef} className="flex-1 space-y-3 overflow-auto pr-1">
            {history === null ? (
              <Loading label="Loading conversation" />
            ) : history.length === 0 ? (
              <div className="rounded-xl bg-stone-50 px-4 py-3 text-sm text-muted">
                Start by saying what you want to achieve. The first message is prefilled for this template.
              </div>
            ) : (
              history.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                      m.role === "user" ? "bg-foreground text-white" : "bg-stone-100 text-foreground"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    {m.source && m.source !== "llm" ? (
                      <div className="mt-1.5">
                        <Badge tone="neutral">replayed</Badge>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))
            )}
            {sending ? (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-stone-100 px-4 py-2.5 text-sm text-muted">Thinking</div>
              </div>
            ) : null}
          </div>
          {chatError ? <Alert className="mt-3">{chatError}</Alert> : null}
          {done ? (
            <Alert kind="ok" className="mt-3">
              The spec is complete. Check it on the right, then confirm.
            </Alert>
          ) : null}
          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <input
              className={inputClass}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type a message"
              disabled={sending || !project.has_data}
              autoFocus
            />
            <Button type="submit" busy={sending} disabled={!draft.trim() || !project.has_data}>
              Send
            </Button>
          </form>
          {!project.has_data ? <p className="mt-2 text-xs text-muted">Upload a CSV first so the analyst can see the columns.</p> : null}
        </Card>

        <Card className="lg:col-span-2" title="Problem spec" subtitle="Fills in as the conversation goes. Edit anything.">
          <div className="space-y-4">
            <Field label="Outcome column (target)">
              <select className={inputClass} value={spec.target_column} onChange={(e) => patch({ target_column: e.target.value })}>
                <option value="">Choose a column</option>
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Positive label">
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
              <Field label="Task">
                <select className={inputClass} value={spec.task_type} onChange={(e) => patch({ task_type: e.target.value as ProblemSpec["task_type"] })}>
                  <option value="binary">Yes or no</option>
                  <option value="regression">A number</option>
                </select>
              </Field>
            </div>

            <div className="rounded-xl border border-border bg-stone-50 p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-muted">How we score</div>
              <p className="mt-1 text-sm">{spec.metric_rationale || metricLabel(spec.primary_metric, params)}</p>
              <p className="mt-1 text-xs text-muted">Raw metric: {rawMetricLabel(spec.primary_metric, params)}{spec.secondary_metric ? `, secondary ${spec.secondary_metric}` : ""}</p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <Field label="Metric">
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
                    <option value="recall_at_fpr">Caught at a false-alarm rate</option>
                    <option value="recall_at_top_k">Found in the riskiest share</option>
                    <option value="wape">Error as a share of total</option>
                  </select>
                </Field>
                {spec.primary_metric === "recall_at_fpr" ? (
                  <Field label="False alarms per 1,000 good rows">
                    <input
                      className={inputClass}
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={Number(params.fpr ?? 0.001) * 1000}
                      onChange={(e) => patch({ metric_params: { fpr: Number(e.target.value) / 1000 } })}
                    />
                  </Field>
                ) : spec.primary_metric === "recall_at_top_k" ? (
                  <Field label="Riskiest share to contact (%)">
                    <input
                      className={inputClass}
                      type="number"
                      step="1"
                      min="1"
                      max="100"
                      value={Math.round(Number(params.top_k ?? 0.1) * 100)}
                      onChange={(e) => patch({ metric_params: { top_k: Number(e.target.value) / 100 } })}
                    />
                  </Field>
                ) : null}
              </div>
            </div>

            <Field label="Time column (used to split by time)" hint="Leave empty for a random split.">
              <select className={inputClass} value={spec.time_column ?? ""} onChange={(e) => patch({ time_column: e.target.value || null })}>
                <option value="">None</option>
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Max time per row (ms)">
                <input
                  className={inputClass}
                  type="number"
                  min="1"
                  value={Number(constraints.max_ms_per_row ?? 5)}
                  onChange={(e) => patch({ constraints: { ...constraints, max_ms_per_row: Number(e.target.value) } })}
                />
              </Field>
              <Field label="Allowed libraries">
                <input
                  className={inputClass}
                  value={Array.isArray(constraints.allowed_libs) ? (constraints.allowed_libs as string[]).join(", ") : ""}
                  onChange={(e) =>
                    patch({
                      constraints: {
                        ...constraints,
                        allowed_libs: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      },
                    })
                  }
                />
              </Field>
            </div>

            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Economics (optional, for the savings estimate)</div>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Rows per month">
                  <input
                    className={inputClass}
                    type="number"
                    min="0"
                    value={econ.monthly_volume == null ? "" : Number(econ.monthly_volume)}
                    onChange={(e) => patch({ economics: { ...econ, monthly_volume: e.target.value === "" ? null : Number(e.target.value) } })}
                  />
                </Field>
                <Field label="Cost of a miss ($)">
                  <input
                    className={inputClass}
                    type="number"
                    min="0"
                    value={econ.cost_fn == null ? "" : Number(econ.cost_fn)}
                    onChange={(e) => patch({ economics: { ...econ, cost_fn: e.target.value === "" ? null : Number(e.target.value) } })}
                  />
                </Field>
                <Field label="Cost of a false alarm ($)">
                  <input
                    className={inputClass}
                    type="number"
                    min="0"
                    value={econ.cost_fp == null ? "" : Number(econ.cost_fp)}
                    onChange={(e) => patch({ economics: { ...econ, cost_fp: e.target.value === "" ? null : Number(e.target.value) } })}
                  />
                </Field>
              </div>
            </div>

            {specError ? <Alert>{specError}</Alert> : null}
            <Button className="w-full" busy={confirming} disabled={!canConfirm} onClick={() => void confirm()}>
              {confirmed ? "Spec confirmed" : "Confirm spec"}
            </Button>
            <p className="text-xs text-muted">Confirming saves the spec and unlocks data protection.</p>
          </div>
        </Card>
      </div>

      <NextStep stage="protect" />
    </div>
  );
}
