"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronDown, RotateCcw } from "lucide-react";
import { Badge, Button, Spinner, cx, inputClass } from "@/components/ui";
import { api, errorText, type ValueParam, type ValueParamsIn, type ValueReport } from "@/lib/api";
import { fmtInt, fmtPct, solverLabel } from "@/lib/format";

function money(x: number | null | undefined, digits = 0): string {
  if (x == null || !Number.isFinite(x)) return "–";
  const sign = x < 0 ? "-" : "";
  return `${sign}$${Math.abs(x).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

function signedMoney(x: number): string {
  return `${x >= 0 ? "+" : ""}${money(x)}`;
}

function paramValue(p: ValueParam): string {
  if (p.unit === "money") return money(p.value, p.value < 100 && p.value % 1 !== 0 ? 2 : 0);
  if (p.unit === "rate") return fmtPct(p.value, p.value < 0.01 ? 2 : 1);
  return fmtInt(Math.round(p.value));
}

const SOURCE_TONE: Record<ValueParam["source"], { label: string; tone: "ok" | "accent" | "warn" }> = {
  data: { label: "Measured", tone: "ok" },
  user: { label: "Yours", tone: "accent" },
  default: { label: "Placeholder", tone: "warn" },
};

const USER_KEYS: (keyof ValueParamsIn)[] = ["rows_per_month", "value_per_positive", "action_success_rate", "cost_per_action", "cost_per_false_positive"];

export function ValuePanel({ projectId, version, finalized, onChange }: { projectId: string; version: number; finalized: boolean; onChange?: () => void }) {
  const [report, setReport] = useState<ValueReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.value(projectId);
      setReport(r);
      setError(null);
    } catch (e) {
      const text = errorText(e);
      // 409 = nothing scored yet; not an error worth showing
      setError(/no scored submission/i.test(text) ? null : text);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load, version, finalized]);

  const dirty = Object.keys(edits).length > 0;

  async function save() {
    if (!report) return;
    setSaving(true);
    try {
      const body: ValueParamsIn = {};
      for (const k of USER_KEYS) {
        if (!(k in edits)) continue;
        const raw = edits[k].trim();
        body[k] = raw === "" ? null : Number(raw);
      }
      const r = await api.putValueParams(projectId, body);
      setReport(r);
      setEdits({});
      setError(null);
      onChange?.();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  }

  async function reset(key: keyof ValueParamsIn) {
    setSaving(true);
    try {
      const r = await api.putValueParams(projectId, { [key]: null });
      setReport(r);
      onChange?.();
      setEdits((e) => {
        const n = { ...e };
        delete n[key];
        return n;
      });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  }

  if (!report) {
    return (
      <div className="text-[13px] leading-relaxed text-muted">
        {loading ? (
          <span className="flex items-center gap-2">
            <Spinner className="h-3.5 w-3.5" /> Pricing the leader
          </span>
        ) : error ? (
          <span className="text-danger">{error}</span>
        ) : (
          "Appears once a solver is scored."
        )}
      </div>
    );
  }

  const c = report.contract;
  const o = report.optimal;
  const b = report.baseline;
  const byKey = Object.fromEntries(report.params.map((p) => [p.key, p])) as Record<string, ValueParam>;
  const be = report.breakeven ?? {};
  const assumptions = report.assumptions ?? [];
  const placeholders = report.params.filter((p) => p.source === "default").length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
        <span>{solverLabel(report.solver)}</span>
        <span aria-hidden>·</span>
        <span>{report.eval_split === "holdout" ? "Priced on the private holdout" : "Priced on the public slice, finalize for the holdout figure"}</span>
        {loading ? <Spinner className="h-3 w-3" /> : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Figure label="Net value per month" value={money(c.net)} hint={c.net_low != null && c.net_high != null ? `90% range ${money(c.net_low)} to ${money(c.net_high)}` : undefined} accent />
        <Figure label="Against the simple baseline" value={report.uplift_net != null ? signedMoney(report.uplift_net) : "–"} hint={b ? `Baseline nets ${money(b.net)} a month` : "Run the baseline solver to compare"} />
        <Figure label="At stake without a model" value={money(report.exposure_per_month)} hint={`${fmtInt(Math.round(byKey.rows_per_month.value * byKey.positive_rate.value))} cases a month x ${money(byKey.value_per_positive.value)}`} />
      </div>

      {placeholders > 0 ? (
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] leading-relaxed text-subtle">
          {placeholders} of {report.params.length} inputs {placeholders === 1 ? "is a placeholder" : "are placeholders"}. Replace them below with your own numbers; every figure here recalculates.
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="min-w-0 lg:col-span-3">
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-[13px] font-medium">Net value by how much you flag</h3>
            <span className="text-[11px] text-muted">share of rows flagged, log scale</span>
          </div>
          <ValueCurve report={report} />
        </div>
        <div className="min-w-0 lg:col-span-2">
          <h3 className="mb-2 text-[13px] font-medium">Two operating points</h3>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] text-muted">
                <th className="py-1 font-normal" />
                <th className="py-1 text-right font-normal">Agreed rule</th>
                <th className="py-1 text-right font-normal">Best value</th>
              </tr>
            </thead>
            <tbody className="num">
              <PointRow label="Rows flagged" a={fmtPct(c.flagged_share, 2)} b={fmtPct(o.flagged_share, 2)} />
              <PointRow label="Cases caught" a={fmtPct(c.recall)} b={fmtPct(o.recall)} />
              <PointRow label="Caught per month" a={fmtInt(Math.round(c.tp))} b={fmtInt(Math.round(o.tp))} />
              <PointRow label="Wrong flags per month" a={fmtInt(Math.round(c.fp))} b={fmtInt(Math.round(o.fp))} />
              <PointRow label="Net per month" a={money(c.net)} b={money(o.net)} strong />
            </tbody>
          </table>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">
            The agreed rule is the false-alarm budget or contact share from intake. Best value is the point on the curve with the highest net at these inputs.
          </p>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-[13px] font-medium">Inputs</h3>
          {dirty ? (
            <Button size="sm" busy={saving} onClick={() => void save()}>
              Recalculate
            </Button>
          ) : null}
        </div>
        <ul className="divide-y divide-border rounded-xl border border-border">
          {report.params.map((p) => {
            const editable = p.key !== "positive_rate";
            const st = SOURCE_TONE[p.source];
            return (
              <li key={p.key} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 sm:flex-nowrap">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px]">{p.label}</div>
                  {p.note ? <div className="text-[11px] leading-snug text-muted">{p.note}</div> : null}
                </div>
                <Badge tone={st.tone}>{st.label}</Badge>
                {editable ? (
                  <div className="flex items-center gap-1.5">
                    <input
                      className={cx(inputClass, "num w-28 text-right")}
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step={p.unit === "rate" ? "0.01" : "1"}
                      value={p.key in edits ? edits[p.key] : p.unit === "rate" ? String(p.value) : String(Math.round(p.value * 100) / 100)}
                      onChange={(e) => setEdits((s) => ({ ...s, [p.key]: e.target.value }))}
                      aria-label={p.label}
                    />
                    {p.source === "user" ? (
                      <button type="button" className="text-muted hover:text-foreground" title="Back to the measured value or placeholder" onClick={() => void reset(p.key as keyof ValueParamsIn)}>
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>
                    ) : null}
                  </div>
                ) : (
                  <span className="num w-28 text-right text-[13px]">{paramValue(p)}</span>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <details className="group" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="flex cursor-pointer list-none items-center gap-1 text-[12px] text-muted [&::-webkit-details-marker]:hidden">
          What moves the number, and what is assumed
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div>
            <h4 className="mb-1.5 text-[12px] font-medium">If an input were half, or one and a half times</h4>
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-left text-[11px] text-muted">
                  <th className="py-1 font-normal">Input</th>
                  <th className="py-1 text-right font-normal">Half</th>
                  <th className="py-1 text-right font-normal">1.5x</th>
                </tr>
              </thead>
              <tbody className="num">
                {report.sensitivity.map((s) => (
                  <tr key={s.key} className="border-t border-border">
                    <td className="py-1 pr-2 font-sans">{s.label}</td>
                    <td className="py-1 text-right">{money(s.low_net)}</td>
                    <td className="py-1 text-right">{money(s.high_net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {be.cost_per_false_positive != null || be.action_success_rate != null ? (
              <p className="mt-2 text-[11px] leading-relaxed text-muted">
                Break-even:
                {be.cost_per_false_positive != null ? ` the value hits zero if a wrong flag cost ${money(be.cost_per_false_positive)}` : ""}
                {be.cost_per_false_positive != null && be.action_success_rate != null ? ", or" : ""}
                {be.action_success_rate != null ? ` if only ${fmtPct(be.action_success_rate)} of flagged cases were acted on successfully` : ""}.
              </p>
            ) : null}
          </div>
          <div>
            <h4 className="mb-1.5 text-[12px] font-medium">How it is worked out</h4>
            <p className="num rounded-lg bg-card-2 p-3 text-[11px] leading-relaxed text-subtle">{report.formula}</p>
            <ul className="mt-2 space-y-1 text-[11px] leading-relaxed text-muted">
              {assumptions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </div>
  );
}

function axisMoney(v: number): string {
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${Math.round(a / 1e3)}k`;
  return `${sign}$${Math.round(a)}`;
}

function Figure({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-card-2 px-3.5 py-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className={cx("num mt-1 text-[24px] leading-none font-medium tracking-[-0.02em]", accent && "text-gradient")}>{value}</div>
      {hint ? <div className="mt-1.5 text-[11px] leading-snug text-muted">{hint}</div> : null}
    </div>
  );
}

function PointRow({ label, a, b, strong }: { label: string; a: string; b: string; strong?: boolean }) {
  return (
    <tr className={cx("border-t border-border", strong && "font-medium")}>
      <td className="py-1.5 pr-2 font-sans text-subtle">{label}</td>
      <td className="py-1.5 text-right">{a}</td>
      <td className="py-1.5 text-right">{b}</td>
    </tr>
  );
}

function ValueCurve({ report }: { report: ValueReport }) {
  const data = useMemo(() => report.curve.map((p) => ({ x: p.flagged_share * 100, net: p.net, recall: p.recall })), [report]);
  const ticks = [0.05, 0.1, 0.3, 1, 3, 10, 30].filter((t) => data.length > 0 && t >= data[0].x * 0.99 && t <= data[data.length - 1].x * 1.01);
  const cx100 = report.contract.flagged_share * 100;
  const ox100 = report.optimal.flagged_share * 100;
  const gradId = `value-fill-${report.solver}`;
  // The far right of the curve (half the rows flagged) can plunge far below zero; clip it so the useful part stays readable.
  const maxNet = Math.max(1, ...data.map((d) => d.net));
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="x" type="number" scale="log" domain={["dataMin", "dataMax"]} ticks={ticks} tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
          <YAxis
            domain={[(min: number) => Math.min(0, Math.max(min, -maxNet)), (max: number) => Math.max(max * 1.1, 1)]}
            allowDataOverflow
            tickFormatter={axisMoney}
            tick={{ fontSize: 11, fill: "var(--muted)" }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: "var(--border-strong)" }}
            contentStyle={{ background: "var(--card-2)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12, color: "var(--foreground)" }}
            labelFormatter={(v) => `${Number(v).toFixed(2)}% flagged`}
            formatter={(v, name) => (name === "net" ? [money(Number(v)), "Net per month"] : [fmtPct(Number(v)), "Cases caught"])}
          />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Area type="monotone" dataKey="net" stroke="none" fill={`url(#${gradId})`} isAnimationActive={false} />
          <Line type="monotone" dataKey="net" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="recall" stroke="transparent" dot={false} isAnimationActive={false} yAxisId={0} legendType="none" />
          <ReferenceLine x={cx100} stroke="var(--foreground)" strokeDasharray="3 3" label={{ value: "agreed", position: "insideTopLeft", fontSize: 10, fill: "var(--subtle)" }} />
          {Math.abs(ox100 - cx100) / Math.max(cx100, 1e-9) > 0.05 ? (
            <ReferenceLine x={ox100} stroke="var(--warn)" strokeDasharray="3 3" label={{ value: "best", position: "insideBottomRight", fontSize: 10, fill: "var(--warn)" }} />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
