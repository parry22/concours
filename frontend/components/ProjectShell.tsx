"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, Check, ChevronDown, LayoutGrid, Lock, Plus, X } from "lucide-react";
import { api, errorText, type ProjectOut, type Stage } from "@/lib/api";
import { PHASES, STEPS, TEMPLATE_ICON, TEMPLATE_LABEL, doneCount, isUnlocked, reachedIndex, stepHref } from "@/lib/stages";
import { fmtCompact } from "@/lib/format";
import { Alert, Logo, Segments, Skeleton, cx } from "./ui";

type Ctx = {
  project: ProjectOut;
  setProject: (p: ProjectOut) => void;
  refresh: () => Promise<ProjectOut | undefined>;
};

const ProjectContext = createContext<Ctx | null>(null);

export function useProject(): Ctx {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject outside ProjectShell");
  return ctx;
}

function currentStage(pathname: string): Stage | undefined {
  const last = pathname.split("/").pop() || "";
  return STEPS.find((s) => s.stage === last)?.stage;
}

export function ProjectShell({ id, children }: { id: string; children: ReactNode }) {
  const [project, setProject] = useState<ProjectOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const p = await api.project(id);
      setProject(p);
      setError(null);
      return p;
    } catch (e) {
      setError(errorText(e));
      return undefined;
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => (project ? { project, setProject, refresh } : null), [project, refresh]);

  return (
    <AppFrame project={project}>
      {error ? (
        <Alert>
          {error}{" "}
          <button className="font-medium underline underline-offset-2" onClick={() => void refresh()}>
            Retry
          </button>
        </Alert>
      ) : !value ? (
        <div className="space-y-4">
          <Skeleton className="h-9 w-72" />
          <Skeleton className="h-4 w-96 max-w-full" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      ) : (
        <ProjectContext.Provider value={value}>
          <StepEyebrow />
          <StepGuard project={value.project}>{children}</StepGuard>
        </ProjectContext.Provider>
      )}
    </AppFrame>
  );
}

/**
 * Desktop: a labelled sidebar (navigation, and the steps when a project is open). Phones: one sticky header with the
 * current step and a progress line. `project` undefined means the projects home.
 */
export function AppFrame({ project, children }: { project?: ProjectOut | null; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <Sidebar project={project} />
      <MobileHeader project={project} />
      <div className="lg:pl-[248px]">
        <main className="mx-auto w-full max-w-[1080px] px-4 pt-5 pb-36 sm:px-6 sm:pt-7 lg:px-10 lg:pt-10 lg:pb-28">{children}</main>
      </div>
    </div>
  );
}

function Sidebar({ project }: { project?: ProjectOut | null }) {
  const pathname = usePathname();
  return (
    <aside className="scroll-thin fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col overflow-y-auto border-r border-border bg-background lg:flex">
      <Link href="/" className="flex items-center gap-2 px-5 pt-5 pb-4">
        <Logo />
        <span className="text-[15px] font-semibold tracking-[-0.01em]">Brief</span>
      </Link>
      <nav className="space-y-0.5 px-3">
        <SideLink href="/" active={pathname === "/"} icon={<LayoutGrid className="h-4 w-4" />}>
          All projects
        </SideLink>
        <SideLink href="/#start" icon={<Plus className="h-4 w-4" />}>
          New problem
        </SideLink>
      </nav>

      {project === undefined ? <HowItWorks /> : project ? <ProjectSteps project={project} /> : <Skeleton className="mx-4 mt-6 h-40" />}

      <div className="mt-auto p-3">
        <div className="rounded-xl border border-border bg-card px-3 py-2.5" title="Data, solvers and the referee all run on this machine">
          <div className="flex items-center gap-2 text-[12px] font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-pink" />
            Local mode
          </div>
          <div className="mt-0.5 text-[11px] leading-snug text-muted">Nothing leaves this machine.</div>
        </div>
      </div>
    </aside>
  );
}

function SideLink({ href, active, icon, children }: { href: string; active?: boolean; icon: ReactNode; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={cx(
        "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-colors",
        active ? "bg-card-2 text-foreground" : "text-subtle hover:bg-card hover:text-foreground",
      )}
    >
      <span className={active ? "[&>svg]:[stroke:url(#brand-stroke)]" : "text-muted"}>{icon}</span>
      {children}
    </Link>
  );
}

function HowItWorks() {
  return (
    <div className="mt-7 px-5">
      <div className="text-[11px] font-medium tracking-[0.06em] text-muted uppercase">How it works</div>
      <ol className="mt-3 space-y-4">
        {PHASES.map((phase, pi) => (
          <li key={phase} className="flex gap-3">
            <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong text-[10px] text-subtle">
              {pi + 1}
            </span>
            <div className="min-w-0">
              <div className="text-[13px] font-medium">{phase}</div>
              <div className="mt-0.5 text-[12px] leading-snug text-muted">
                {STEPS.filter((s) => s.phase === phase)
                  .map((s) => s.label)
                  .join(", ")}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ProjectSteps({ project }: { project: ProjectOut }) {
  const pathname = usePathname();
  const current = currentStage(pathname);
  const done = doneCount(project);
  const Icon = TEMPLATE_ICON[project.template];
  return (
    <div className="mt-6 px-3">
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border-strong bg-card-2">
          {Icon ? <Icon className="icon-brand h-4 w-4" /> : null}
        </span>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-medium">{project.name}</div>
          <div className="truncate text-[11px] text-muted">
            {TEMPLATE_LABEL[project.template]}
            {project.profile?.n_rows ? ` · ${fmtCompact(project.profile.n_rows)} rows` : ""}
          </div>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-3 px-1">
        <Segments total={STEPS.length} filled={done} size="sm" className="flex-1" />
        <span className="num shrink-0 text-[11px] text-muted">
          {done}/{STEPS.length}
        </span>
      </div>
      <nav aria-label="Steps" className="mt-2">
        {PHASES.map((phase) => (
          <div key={phase} className="mt-4">
            <div className="px-2 text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{phase}</div>
            <ol className="mt-1.5 space-y-0.5">
              {STEPS.map((s, i) => ({ s, i }))
                .filter(({ s }) => s.phase === phase)
                .map(({ s, i }) => (
                  <li key={s.stage}>
                    <StepRow project={project} index={i} active={current === s.stage} done={i < done} />
                  </li>
                ))}
            </ol>
          </div>
        ))}
      </nav>
    </div>
  );
}

function StepRow({
  project,
  index,
  active,
  done,
  onNavigate,
  roomy,
}: {
  project: ProjectOut;
  index: number;
  active: boolean;
  done: boolean;
  onNavigate?: () => void;
  roomy?: boolean;
}) {
  const s = STEPS[index];
  const unlocked = isUnlocked(project, s.stage);
  const body = (
    <div className={cx("flex items-start gap-3 rounded-lg px-2", roomy ? "py-3" : "py-2", active ? "bg-card-2" : unlocked ? "hover:bg-card" : "opacity-45")}>
      <StepDot n={index + 1} state={done && !active ? "done" : active ? "active" : unlocked ? "todo" : "locked"} />
      <div className="min-w-0 pt-px">
        <div className={cx("text-[13px] font-medium", active ? "text-foreground" : done ? "text-subtle" : "text-subtle")}>{s.label}</div>
        {active || roomy ? <div className="mt-0.5 text-[12px] leading-snug text-muted">{s.blurb}</div> : null}
      </div>
    </div>
  );
  return unlocked ? (
    <Link href={stepHref(project.id, s.stage)} aria-current={active ? "step" : undefined} onClick={onNavigate} className="block">
      {body}
    </Link>
  ) : (
    <div aria-disabled title="Finish the earlier steps first">
      {body}
    </div>
  );
}

function StepDot({ n, state }: { n: number; state: "done" | "active" | "todo" | "locked" }) {
  if (state === "done")
    return (
      <span className="bg-brand flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-background">
        <Check className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  if (state === "locked")
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border text-muted">
        <Lock className="h-2.5 w-2.5" />
      </span>
    );
  return (
    <span
      className={cx(
        "num flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px]",
        state === "active" ? "bg-foreground font-semibold text-background" : "border border-border-strong text-subtle",
      )}
    >
      {n}
    </span>
  );
}

function MobileHeader({ project }: { project?: ProjectOut | null }) {
  const pathname = usePathname();
  const current = currentStage(pathname);
  const idx = STEPS.findIndex((s) => s.stage === current);
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);
  const done = project ? doneCount(project) : 0;

  return (
    <>
      <header className="sticky top-0 z-20 border-b border-border bg-background/85 pt-[var(--safe-top)] backdrop-blur-xl lg:hidden">
        <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
          <Link href="/" aria-label="All projects" className="shrink-0">
            <Logo className={project === undefined ? undefined : "h-6 w-[19px]"} />
          </Link>
          {project === undefined ? (
            <span className="flex-1 text-[15px] font-semibold">Brief</span>
          ) : (
            <div className="min-w-0 flex-1 leading-tight">
              {project ? (
                <>
                  <div className="truncate text-[11px] text-muted">{project.name}</div>
                  <div className="truncate text-[14px] font-medium">{idx >= 0 ? STEPS[idx].label : "Project"}</div>
                </>
              ) : (
                <Skeleton className="h-4 w-32" />
              )}
            </div>
          )}
          {project && idx >= 0 ? (
            <button
              onClick={() => setOpen(true)}
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border-strong bg-card-2 pr-2.5 pl-3 text-[12px] font-medium"
              aria-label="Show all steps"
            >
              <span className="num">
                {idx + 1}/{STEPS.length}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-muted" />
            </button>
          ) : project === undefined ? (
            <Link
              href="/#start"
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border-strong bg-card-2 px-3 text-[12px] font-medium"
            >
              <Plus className="h-3.5 w-3.5" />
              New
            </Link>
          ) : null}
        </div>
        {project ? (
          <div className="h-[2px] w-full bg-card-3" aria-hidden>
            <div
              className="bg-brand-x h-full transition-[width] duration-500"
              style={{
                width: `${(Math.max(done, idx + 0.5) / STEPS.length) * 100}%`,
              }}
            />
          </div>
        ) : null}
      </header>
      {/* Outside the header: its backdrop-filter would trap a fixed-position sheet inside it. */}
      {open && project ? <StepSheet project={project} current={current} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function StepSheet({ project, current, onClose }: { project: ProjectOut; current?: Stage; onClose: () => void }) {
  const done = doneCount(project);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal aria-label="Steps">
      <button className="fade-in absolute inset-0 bg-black/60 backdrop-blur-[2px]" aria-label="Close" onClick={onClose} />
      <div className="sheet-in absolute inset-x-0 bottom-0 max-h-[88dvh] overflow-y-auto rounded-t-[24px] border-t border-border-strong bg-card px-3 pt-2 pb-[calc(16px+var(--safe-bottom))]">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-strong" />
        <div className="mb-1 flex items-center justify-between px-2">
          <div>
            <h2 className="text-[15px] font-semibold">{project.name}</h2>
            <div className="num text-[12px] text-muted">
              {done}/{STEPS.length} steps done
            </div>
          </div>
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-card-2" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        {PHASES.map((phase) => (
          <div key={phase} className="mt-3">
            <div className="px-2 text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{phase}</div>
            <ol className="mt-1">
              {STEPS.map((s, i) => ({ s, i }))
                .filter(({ s }) => s.phase === phase)
                .map(({ s, i }) => (
                  <li key={s.stage}>
                    <StepRow project={project} index={i} active={current === s.stage} done={i < done} onNavigate={onClose} roomy />
                  </li>
                ))}
            </ol>
          </div>
        ))}
        <Link
          href="/"
          onClick={onClose}
          className="mt-3 flex h-11 items-center justify-center gap-2 rounded-xl border border-border-strong text-[13px] font-medium text-subtle"
        >
          <LayoutGrid className="h-4 w-4" />
          All projects
        </Link>
      </div>
    </div>
  );
}

function StepGuard({ project, children }: { project: ProjectOut; children: ReactNode }) {
  const pathname = usePathname();
  const stage = currentStage(pathname);
  if (!stage || isUnlocked(project, stage)) return <>{children}</>;
  const reached = STEPS[reachedIndex(project)];
  return (
    <Alert kind="warn">
      This step opens once the earlier ones are done.{" "}
      <Link href={stepHref(project.id, reached.stage)} className="font-medium underline underline-offset-2">
        Go to {reached.label}
      </Link>
    </Alert>
  );
}

/** Small "Step 4 of 6 · Prove" line above a step title, desktop only (phones show it in the header). */
function StepEyebrow() {
  const pathname = usePathname();
  const idx = STEPS.findIndex((s) => s.stage === currentStage(pathname));
  if (idx < 0) return null;
  return (
    <div className="mb-2 hidden items-center gap-2 text-[12px] font-medium text-muted lg:flex">
      <span className="num">
        Step {idx + 1} of {STEPS.length}
      </span>
      <span className="text-[#3a3a40]">·</span>
      {STEPS[idx].phase}
    </div>
  );
}

/**
 * The one primary action of a step. Pinned above the home indicator on phones, a floating bar on desktop.
 */
export function ActionBar({ hint, secondary, children }: { hint?: ReactNode; secondary?: ReactNode; children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/85 px-4 pt-3 pb-[calc(12px+var(--safe-bottom))] backdrop-blur-xl lg:sticky lg:bottom-5 lg:mt-8 lg:rounded-2xl lg:border lg:border-border-strong lg:bg-[#151517]/95 lg:px-4 lg:py-3 lg:shadow-[0_20px_50px_-20px_rgb(0_0_0/0.8)]">
      <div className="flex items-center gap-3">
        {hint ? <div className="hidden min-w-0 flex-1 text-[13px] text-muted sm:block">{hint}</div> : <div className="hidden flex-1 sm:block" />}
        <div className="flex w-full items-center gap-2 sm:w-auto [&>*]:flex-1 sm:[&>*]:flex-none">
          {secondary}
          {children}
        </div>
      </div>
    </div>
  );
}

/** Link to a later step, rendered as the primary button. */
export function NextLink({ stage, label, disabled }: { stage: Stage; label?: string; disabled?: boolean }) {
  const { project } = useProject();
  const step = STEPS.find((s) => s.stage === stage);
  const ok = !disabled && isUnlocked(project, stage);
  const text = label || step?.label || "Continue";
  const cls =
    "inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-[14px] font-medium whitespace-nowrap transition-[background-color,transform] duration-150";
  return ok ? (
    <Link href={stepHref(project.id, stage)} className={cx(cls, "bg-foreground text-background hover:bg-white active:scale-[0.98]")}>
      {text}
      <ArrowRight className="h-4 w-4" />
    </Link>
  ) : (
    <span aria-disabled className={cx(cls, "cursor-not-allowed bg-card-3 text-muted")}>
      {text}
      <ArrowRight className="h-4 w-4" />
    </span>
  );
}
