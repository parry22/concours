export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "";
  return new Intl.NumberFormat("en-US").format(n);
}

export function fmtPct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "";
  return `${(x * 100).toFixed(digits)}%`;
}

export function fmtScore(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "";
  return x.toFixed(4);
}

export function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/\.?0+$/, "");
  return String(v);
}

export function fmtMoney(n: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

/** Attempt label for the Improve screen: never an algorithm name. Local solvers are numbered; agent attempts named. */
export function attemptLabel(solver: string, index?: number): string {
  const agent = solver.match(/^agent_solver_(\d+)$/);
  if (agent) return `Agent attempt ${agent[1]}`;
  return index != null ? `Attempt ${index}` : "Attempt";
}

export function metricLabel(metric: string, params: Record<string, unknown> | undefined): string {
  if (metric === "recall_at_fpr") {
    const fpr = Number(params?.fpr ?? 0.001);
    const per1000 = Math.round(fpr * 1000 * 100) / 100;
    return `Share of positives caught at ${per1000} false alarm${per1000 === 1 ? "" : "s"} per 1,000 good rows`;
  }
  if (metric === "recall_at_top_k") {
    const k = Number(params?.top_k ?? 0.1);
    return `Share of positives found in the riskiest ${Math.round(k * 100)}% of rows`;
  }
  if (metric === "wape") return "Average error as a share of the total";
  return metric;
}

export function rawMetricLabel(metric: string, params: Record<string, unknown> | undefined): string {
  if (metric === "recall_at_fpr") return `recall at FPR ${params?.fpr ?? 0.001}`;
  if (metric === "recall_at_top_k") return `recall in top ${params?.top_k ?? 0.1}`;
  return metric;
}

export function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function fmtCompact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/** "84%" from a business line like "Fraud caught at 1 false alarm per 1,000 good transactions: 84%". */
export function figureOf(line: string | null | undefined): { label: string; value: string } | null {
  if (!line) return null;
  const i = line.lastIndexOf(":");
  if (i < 0) return null;
  return { label: line.slice(0, i).trim(), value: line.slice(i + 1).trim() };
}
