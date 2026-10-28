import { CreditCard, Database, FileUp, MessageSquareText, Rocket, ShieldCheck, Trophy, UserMinus, Zap, type LucideIcon } from "lucide-react";
import type { ProjectOut, Stage } from "./api";

export const STAGES: Stage[] = ["upload", "intake", "protect", "arena", "serve", "launch"];

export type Phase = "Setup" | "Prove" | "Deliver";

export const STEPS: { stage: Stage; label: string; short: string; phase: Phase; icon: LucideIcon; blurb: string }[] = [
  { stage: "upload", label: "Your data", short: "Data", phase: "Setup", icon: Database, blurb: "Check what was loaded" },
  { stage: "intake", label: "Describe the goal", short: "Goal", phase: "Setup", icon: MessageSquareText, blurb: "Agree how to score" },
  { stage: "protect", label: "Protect the data", short: "Protect", phase: "Prove", icon: ShieldCheck, blurb: "Split and check for leaks" },
  { stage: "arena", label: "Arena", short: "Arena", phase: "Prove", icon: Trophy, blurb: "Solvers compete" },
  { stage: "serve", label: "Use the winner", short: "Use", phase: "Deliver", icon: Zap, blurb: "Score new rows" },
  { stage: "launch", label: "Launch on Apex", short: "Launch", phase: "Deliver", icon: Rocket, blurb: "Package and hand off" },
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

/** Steps whose work is finished, used for the progress bar. The backend advances the stage as each step completes. */
export function doneCount(project: ProjectOut): number {
  let n = stageIndex(project.stage);
  if (project.finalized) n = Math.max(n, stageIndex("serve"));
  if (project.apex_validation === "pass") n = STAGES.length;
  return n;
}

/** True once the scoring rule was confirmed. Templates arrive with a prefilled spec, so the spec alone does not say. */
export function specConfirmed(project: ProjectOut): boolean {
  return stageIndex(project.stage) >= stageIndex("protect");
}

export function stepHref(id: string, stage: Stage): string {
  return `/projects/${id}/${stage}`;
}

export const TEMPLATE_GOAL: Record<string, string> = {
  fraud: "We want to catch more card fraud without annoying good customers.",
  churn: "We want to know which customers are about to leave so we can call them first.",
};

/** Suggested replies for the scripted intake, one per turn after the goal. */
export const TEMPLATE_REPLIES: Record<string, string[]> = {
  fraud: [
    TEMPLATE_GOAL.fraud,
    "About 1 in 1000 false alarms is fine.",
    "A missed fraud costs about 120 dollars, a blocked customer about 4. 300,000 transactions a month.",
  ],
  churn: [
    TEMPLATE_GOAL.churn,
    "We can call the riskiest 10% each month.",
    "A lost customer costs about 60 dollars, a call about 3. 3,000 customers a month.",
  ],
};

export const TEMPLATE_LABEL: Record<string, string> = {
  fraud: "Fraud",
  churn: "Churn",
  custom: "Custom",
};

export const TEMPLATE_COLOR: Record<string, string> = {
  fraud: "var(--c-pink)",
  churn: "var(--c-indigo)",
  custom: "var(--c-peach)",
};

export const TEMPLATE_ICON: Record<string, LucideIcon> = { fraud: CreditCard, churn: UserMinus, custom: FileUp };

export const PHASES: Phase[] = ["Setup", "Prove", "Deliver"];
