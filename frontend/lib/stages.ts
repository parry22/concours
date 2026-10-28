import type { ProjectOut, Stage } from "./api";

export const STAGES: Stage[] = ["upload", "intake", "protect", "arena", "serve", "launch"];

export const STEPS: { stage: Stage; label: string; short: string }[] = [
  { stage: "upload", label: "New problem", short: "Problem" },
  { stage: "intake", label: "Describe the goal", short: "Goal" },
  { stage: "protect", label: "Protect the data", short: "Protect" },
  { stage: "arena", label: "Arena", short: "Arena" },
  { stage: "serve", label: "Use the winner", short: "Winner" },
  { stage: "launch", label: "Launch on Apex", short: "Launch" },
];

export function stageIndex(stage: Stage): number {
  return STAGES.indexOf(stage);
}

/** Highest step index the project has reached. Finalizing the arena unlocks the last two steps. */
export function reachedIndex(project: ProjectOut): number {
  let idx = stageIndex(project.stage);
  if (project.finalized) idx = Math.max(idx, stageIndex("launch"));
  return idx;
}

export function isUnlocked(project: ProjectOut, stage: Stage): boolean {
  return stageIndex(stage) <= reachedIndex(project);
}

export function stepHref(id: string, stage: Stage): string {
  return `/projects/${id}/${stage}`;
}

export const TEMPLATE_GOAL: Record<string, string> = {
  fraud: "We want to catch more card fraud without annoying good customers.",
  churn: "We want to know which customers are about to leave so we can call them first.",
};

export const TEMPLATE_LABEL: Record<string, string> = {
  fraud: "Fraud",
  churn: "Churn",
  custom: "Blank",
};
