"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Card, PageHeader, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type QueueCase, type QueueOut } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { queue as copy } from "@/lib/copy";

const money = (x: number) => `$${x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const PAGE = 50;

export default function QueuePage() {
  const { project } = useProject();
  const [q, setQ] = useState<QueueOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [all, setAll] = useState(false);

  useEffect(() => {
    setQ(null);
    setError(null);
    api
      .queue(project.id)
      .then(setQ)
      .catch((e) => setError(errorText(e)));
  }, [project.id, project.active_model?.id, project.as_of]);

  async function mark(c: QueueCase, label: "fraud" | "not_fraud" | null) {
    setSaving(c.transaction_id);
    try {
      setQ(await api.labelCase(project.id, c.transaction_id, label));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(null);
    }
  }

  const cases = q ? (all ? q.cases : q.cases.slice(0, PAGE)) : [];
  const capacity = project.fraud_settings?.daily_capacity ?? 200;

  return (
    <div className="space-y-5">
      <PageHeader
        title={copy.title}
        actions={
          q ? (
            <a href={api.queueDownloadUrl(project.id)} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-border-strong bg-card-2 px-3 text-[13px] font-medium hover:bg-card-3">
              <Download className="h-3.5 w-3.5" />
              {copy.download}
            </a>
          ) : null
        }
      >
        {copy.sub(capacity)}
      </PageHeader>
      {error ? <Alert kind={error.includes("moved forward") ? "warn" : "error"}>{error.includes("moved forward") ? copy.windowMoved : error}</Alert> : null}

      {!q && !error ? (
        <Card>
          <div className="flex items-center gap-3 text-[14px] font-medium">
            <Spinner className="h-4 w-4 text-pink" />
            {copy.loading}
          </div>
          <div className="mt-4 space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        </Card>
      ) : null}

      {q ? (
        <>
          <div className="grid grid-cols-2 overflow-hidden rounded-2xl border border-border bg-card sm:grid-cols-4">
            <Fig label={copy.figDay} value={q.day} hint={copy.version(q.model_version)} />
            <Fig label={copy.figScored} value={fmtInt(q.rows_scored)} hint={copy.figScoredHint} />
            <Fig label={copy.atStake} value={money(q.expected_loss_total)} hint={copy.figStakeHint(q.cases.length)} />
            <Fig label={copy.figReviewed} value={`${q.labeled}/${q.cases.length}`} hint={q.explore_slots ? copy.figReviewedExplore(q.explore_slots) : copy.figReviewedHint} />
          </div>

          <Card pad={false} className="overflow-hidden">
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full min-w-[920px] text-[13px]">
                <thead>
                  <tr className="border-b border-border text-left text-[12px] text-muted">
                    <th className="px-4 py-2.5 font-medium">{copy.cols.rank}</th>
                    <th className="px-2 py-2.5 font-medium">{copy.cols.id}</th>
                    <th className="px-2 py-2.5 font-medium">{copy.cols.time}</th>
                    <th className="px-2 py-2.5 text-right font-medium">{copy.cols.amount}</th>
                    <th className="px-2 py-2.5 font-medium">{copy.cols.customer}</th>
                    <th className="px-2 py-2.5 text-right font-medium">{copy.cols.risk}</th>
                    <th className="px-2 py-2.5 text-right font-medium">{copy.cols.loss}</th>
                    <th className="px-2 py-2.5 font-medium">{copy.cols.reasons}</th>
                    <th className="px-4 py-2.5 text-right font-medium">{copy.cols.verdict}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {cases.map((c) => (
                    <tr key={c.transaction_id} className={cx("align-top transition-opacity", c.label === "not_fraud" && "opacity-55")}>
                      <td className="num px-4 py-3 text-muted">{c.rank}</td>
                      <td className="num px-2 py-3">
                        {c.transaction_id}
                        {c.explore ? <Badge tone="neutral" className="ml-2 align-middle" title={copy.exploreHint}>{copy.explore}</Badge> : null}
                      </td>
                      <td className="num px-2 py-3 whitespace-nowrap text-subtle">{c.time.slice(11)}</td>
                      <td className="num px-2 py-3 text-right font-medium">{money(c.amount)}</td>
                      <td className="num px-2 py-3 text-muted" title={copy.hashed}>
                        {c.customer}
                      </td>
                      <td className="num px-2 py-3 text-right">{(c.risk * 100).toFixed(0)}%</td>
                      <td className="num px-2 py-3 text-right font-medium">{money(c.expected_loss)}</td>
                      <td className="px-2 py-3">
                        <ul className="space-y-0.5 text-[12px] leading-snug text-subtle">
                          {c.reasons.map((r) => (
                            <li key={r.text}>{r.text}</li>
                          ))}
                        </ul>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex justify-end gap-1">
                          <Verdict value={c.label ?? null} busy={saving === c.transaction_id} onChange={(v) => void mark(c, v)} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!all && q.cases.length > PAGE ? (
              <button onClick={() => setAll(true)} className="w-full border-t border-border py-3 text-[13px] font-medium text-subtle hover:bg-card-2">
                {copy.showMore(q.cases.length)}
              </button>
            ) : null}
          </Card>
          <p className="text-[12px] text-muted">{copy.feedback}</p>
        </>
      ) : null}

      <ActionBar hint={copy.feedback}>
        <NextLink stage="improve" label={copy.next} />
      </ActionBar>
    </div>
  );
}

/** Fraud / Not fraud as one segmented control. Picking the chosen side again clears the verdict. */
function Verdict({ value, busy, onChange }: { value: "fraud" | "not_fraud" | null; busy: boolean; onChange: (v: "fraud" | "not_fraud" | null) => void }) {
  const opt = (v: "fraud" | "not_fraud", label: string) => {
    const on = value === v;
    return (
      <button
        type="button"
        role="radio"
        aria-checked={on}
        disabled={busy}
        onClick={() => onChange(on ? null : v)}
        title={on ? copy.undo : undefined}
        className={cx(
          "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium transition-colors disabled:opacity-60",
          on ? "bg-card-3 text-foreground shadow-[inset_0_0_0_1px_var(--border-strong)]" : "text-muted hover:text-subtle",
        )}
      >
        {on ? <span className={cx("h-1.5 w-1.5 rounded-full", v === "fraud" ? "bg-danger" : "bg-subtle")} /> : null}
        {label}
      </button>
    );
  };
  return (
    <div role="radiogroup" aria-label={copy.cols.verdict} className="inline-flex items-center gap-0.5 rounded-lg border border-border bg-card-2 p-0.5">
      {busy ? <Spinner className="mx-1 h-3 w-3 text-muted" /> : null}
      {opt("fraud", copy.fraud)}
      {opt("not_fraud", copy.notFraud)}
    </div>
  );
}


function Fig({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0 border-border px-4 py-3.5 max-sm:[&:nth-child(-n+2)]:border-b sm:border-r sm:last:border-r-0 max-sm:odd:border-r">
      <div className="text-[12px] text-muted">{label}</div>
      <div className="num mt-1 truncate text-[18px] font-medium">{value}</div>
      <div className="mt-0.5 truncate text-[11px] text-muted">{hint}</div>
    </div>
  );
}
