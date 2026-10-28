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

export function solverLabel(name: string): string {
  const map: Record<string, string> = {
    baseline_logreg: "Baseline (logistic regression)",
    lgbm_default: "LightGBM, default settings",
    lgbm_tuned: "LightGBM, tuned",
    agent_solver: "Agent solver",
  };
  return map[name] || name.replace(/_/g, " ");
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
