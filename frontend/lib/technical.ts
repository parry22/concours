/**
 * Algorithm names. Shown only inside the technical details drawer on the project page; the copy lint allows them
 * in this file alone. Everywhere else a model is "v2", never its approach.
 */
export const APPROACH: Record<string, string> = {
  baseline_logreg: "Logistic regression with standard scaling",
  lgbm_default: "Gradient-boosted trees, default settings (LightGBM)",
  lgbm_tuned: "Gradient-boosted trees with entity history features, tuned (LightGBM)",
  lgbm_regularized: "Gradient-boosted trees, slow learning rate and strong regularisation (LightGBM)",
  lgbm_ensemble: "Five gradient-boosted tree models with different seeds, averaged (LightGBM)",
};

export function approachLabel(solver: string): string {
  const agent = solver.match(/^agent_solver_(\d+)$/);
  if (agent) return `Solver written by an agent, attempt ${agent[1]}`;
  return APPROACH[solver] || solver.replace(/_/g, " ");
}
