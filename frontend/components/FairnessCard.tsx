"use client";

import { useEffect, useState } from "react";
import { Scale } from "lucide-react";
import { Badge, Card, Meter, Skeleton, cx } from "@/components/ui";
import { api, type FairnessColumn, type FairnessReport } from "@/lib/api";
import { fmtInt, fmtPct } from "@/lib/format";
import { fairness as copy } from "@/lib/copy";

/**
 * The fairness report: for each sensitive column Protect set aside, how often each group is put on the list
 * (selection rate) and how often those picks turn out right (hit rate), on the private holdout. Shown on the
 * Protect screen and on the model page. `version` re-fetches when a new version becomes active.
 */
export function FairnessCard({ projectId, columns, version, className }: { projectId: string; columns: string[]; version: number | null; className?: string }) {
  const [report, setReport] = useState<FairnessReport | null | undefined>(undefined);

  useEffect(() => {
    if (version === null) return;
    let live = true;
    setReport(undefined);
    api
      .fairness(projectId)
      .then((r) => live && setReport(r))
      .catch(() => live && setReport(null));
    return () => {
      live = false;
    };
  }, [projectId, version]);

  return (
    <Card className={className} title={copy.title} subtitle={copy.sub(columns)} actions={<Scale className="h-4 w-4 text-muted" strokeWidth={1.5} aria-hidden />}>
      {version === null ? (
        <p className="text-[13px] leading-relaxed text-muted">{copy.waiting}</p>
      ) : report === undefined ? (
        <div className="space-y-2">
          <Skeleton className="h-6" />
          <Skeleton className="h-24" />
        </div>
      ) : report === null ? (
        <p className="text-[13px] leading-relaxed text-muted">{copy.unavailable}</p>
      ) : (
        <div className="space-y-6">
          <p className="text-[13px] leading-relaxed text-subtle">{copy.how(fmtInt(report.selected), fmtInt(report.rows), report.rule === "top_k")}</p>
          {report.columns.map((c) => (
            <ColumnTable key={c.column} c={c} />
          ))}
        </div>
      )}
    </Card>
  );
}

function ColumnTable({ c }: { c: FairnessColumn }) {
  const top = Math.max(...c.groups.map((g) => g.selection_rate), 0.0001);
  const gap = c.min_selection_ratio !== null && c.min_selection_ratio !== undefined && c.min_selection_ratio < 0.8;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="num text-[13px] font-medium">{c.column}</span>
        <span className="text-[12px] text-muted">{c.trait}</span>
        {c.min_selection_ratio !== null && c.min_selection_ratio !== undefined ? (
          <Badge tone={gap ? "warn" : "ok"} title={copy.ratioTitle}>
            {copy.ratio(fmtPct(c.min_selection_ratio, 0))}
          </Badge>
        ) : null}
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[480px] text-[12px]">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-1.5 pr-3 font-medium">{copy.cols.group}</th>
              <th className="py-1.5 pr-3 text-right font-medium">{copy.cols.rows}</th>
              <th className="w-[34%] py-1.5 pr-3 font-medium">{copy.cols.selection}</th>
              <th className="py-1.5 pr-3 text-right font-medium">{copy.cols.hit}</th>
              <th className="py-1.5 text-right font-medium">{copy.cols.base}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {c.groups.map((g) => (
              <tr key={g.group} className={cx(!g.enough_rows && "text-muted")}>
                <td className="py-1.5 pr-3">
                  {g.group}
                  {!g.enough_rows ? <span className="ml-1.5 text-[11px]">{copy.few}</span> : null}
                </td>
                <td className="num py-1.5 pr-3 text-right">{fmtInt(g.rows)}</td>
                <td className="py-1.5 pr-3">
                  <div className="flex items-center gap-2">
                    <Meter value={g.selection_rate / top} className="h-1.5 flex-1" />
                    <span className="num w-12 text-right">{fmtPct(g.selection_rate, 1)}</span>
                  </div>
                </td>
                <td className="num py-1.5 pr-3 text-right">{g.hit_rate === null || g.hit_rate === undefined ? "–" : fmtPct(g.hit_rate, 0)}</td>
                <td className="num py-1.5 text-right">{fmtPct(g.base_rate, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {c.note ? <p className="mt-2 text-[12px] leading-relaxed text-subtle">{c.note}</p> : null}
    </div>
  );
}
