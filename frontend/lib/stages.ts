import { Database, Gauge, ListChecks, MessageSquareText, Rocket, ShieldCheck, Sparkles, Table2, type LucideIcon } from "lucide-react";
import type { ProjectOut, Stage } from "./api";
import { phases, steps as stepCopy } from "./copy";

/**
 * A fraud project has two parts. Setup, in order: your transactions (upload and column mapping), three
 * questions, protection (version 1 builds right after). Then the project tabs, open once version 1 exists.
 * `Stage` is the backend's progress field; `Slug` is the route.
 */
export type Slug = "upload" | "intake" | "protect" | "overview" | "queue" | "improve" | "data" | "launch";
export type Phase = keyof typeof phases;

export const STEPS: { slug: Slug; label: string; short: string; phase: Phase; icon: LucideIcon; blurb: string }[] = [
  { slug: "upload", ...stepCopy.upload, phase: "Setup", icon: Database },
  { slug: "intake", ...stepCopy.intake, phase: "Setup", icon: MessageSquareText },
  { slug: "protect", ...stepCopy.protect, phase: "Setup", icon: ShieldCheck },
  { slug: "overview", ...stepCopy.overview, phase: "Project", icon: Gauge },
  { slug: "queue", ...stepCopy.queue, phase: "Project", icon: ListChecks },
  { slug: "improve", ...stepCopy.improve, phase: "Project", icon: Sparkles },
  { slug: "data", ...stepCopy.data, phase: "Project", icon: Table2 },
  { slug: "launch", ...stepCopy.launch, phase: "Project", icon: Rocket },
];

export const SETUP = STEPS.filter((s) => s.phase === "Setup");
export const TABS = STEPS.filter((s) => s.phase === "Project");
export const PHASES: Phase[] = ["Setup", "Project"];

const STAGES: Stage[] = ["upload", "intake", "protect", "model", "improve", "launch"];

export function stageIndex(stage: Stage): number {
  return STAGES.indexOf(stage);
}

export function isUnlocked(project: ProjectOut, slug: Slug): boolean {
  if (slug === "upload") return true;
  if (slug === "intake") return project.schema_confirmed;
  if (slug === "protect") return project.schema_confirmed && stageIndex(project.stage) >= stageIndex("protect");
  return Boolean(project.active_model);
}

/** Setup steps finished, out of three. */
export function setupDone(project: ProjectOut): number {
  if (project.active_model) return SETUP.length;
  if (stageIndex(project.stage) >= stageIndex("protect")) return 2;
  return project.schema_confirmed ? 1 : 0;
}

/** Where to land when a project opens: the overview once a model exists, else the next setup step. */
export function landing(project: ProjectOut): Slug {
  if (project.active_model) return "overview";
  if (stageIndex(project.stage) >= stageIndex("protect")) return "protect";
  return project.schema_confirmed ? "intake" : "upload";
}

export function stepHref(id: string, slug: Slug): string {
  return `/projects/${id}/${slug}`;
}

export function slugOf(pathname: string): Slug | undefined {
  const last = pathname.split("/").pop() || "";
  return STEPS.find((s) => s.slug === last)?.slug;
}
