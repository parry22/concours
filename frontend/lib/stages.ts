import { CreditCard, Database, FileUp, Megaphone, MessageSquareText, Rocket, ShieldCheck, Sparkles, UserMinus, Layers, type LucideIcon } from "lucide-react";
import type { ProjectOut, Stage } from "./api";
import { phases, steps as stepCopy } from "./copy";

export const STAGES: Stage[] = ["upload", "intake", "protect", "model", "improve", "launch"];

export type Phase = keyof typeof phases;

export const STEPS: { stage: Stage; label: string; short: string; phase: Phase; icon: LucideIcon; blurb: string }[] = [
  { stage: "upload", ...stepCopy.upload, phase: "Setup", icon: Database },
  { stage: "intake", ...stepCopy.intake, phase: "Setup", icon: MessageSquareText },
  { stage: "protect", ...stepCopy.protect, phase: "Model", icon: ShieldCheck },
  { stage: "model", ...stepCopy.model, phase: "Model", icon: Layers },
  { stage: "improve", ...stepCopy.improve, phase: "Improve", icon: Sparkles },
  { stage: "launch", ...stepCopy.launch, phase: "Improve", icon: Rocket },
];

export function stageIndex(stage: Stage): number {
  return STAGES.indexOf(stage);
}

/** Highest step index the project has reached. Version 1 unlocks Your model and Improve; Improve unlocks Launch. */
export function reachedIndex(project: ProjectOut): number {
  let idx = stageIndex(project.stage);
  if (project.active_model) idx = Math.max(idx, stageIndex("improve"));
  if (project.versions.length > 1 || project.finalized) idx = Math.max(idx, stageIndex("launch"));
  return idx;
}

export function isUnlocked(project: ProjectOut, stage: Stage): boolean {
  return stageIndex(stage) <= reachedIndex(project);
}

/** Steps whose work is finished, for the progress bar. */
export function doneCount(project: ProjectOut): number {
  let n = stageIndex(project.stage);
  if (project.active_model) n = Math.max(n, stageIndex("model"));
  if (project.versions.length > 1) n = Math.max(n, stageIndex("improve"));
  if (project.apex_validation === "pass") n = STAGES.length;
  return n;
}

/** Lists open once version 1 exists (step 4 onward). */
export function listsUnlocked(project: ProjectOut): boolean {
  return Boolean(project.active_model);
}

/** True once the scoring rule was confirmed. Templates arrive with a prefilled spec, so the spec alone does not say. */
export function specConfirmed(project: ProjectOut): boolean {
  return stageIndex(project.stage) >= stageIndex("protect");
}

export function stepHref(id: string, stage: Stage): string {
  return `/projects/${id}/${stage}`;
}

export function listsHref(id: string): string {
  return `/projects/${id}/lists`;
}

export const TEMPLATE_LABEL: Record<string, string> = {
  fraud: "Fraud",
  churn: "Churn",
  leads: "Leads",
  custom: "Custom",
};

export const TEMPLATE_ICON: Record<string, LucideIcon> = { fraud: CreditCard, churn: UserMinus, leads: Megaphone, custom: FileUp };

export const PHASES: Phase[] = ["Setup", "Model", "Improve"];
