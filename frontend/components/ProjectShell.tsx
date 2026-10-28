"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, Check, ChevronDown, LayoutGrid, Lock, Plus, X } from "lucide-react";
import { api, errorText, type ProjectOut, type Stage } from "@/lib/api";
import { STEPS, doneCount, isUnlocked, reachedIndex, stepHref, TEMPLATE_COLOR, TEMPLATE_LABEL } from "@/lib/stages";
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
    <AppFrame rail={<StepRail project={project} />} top={<TopBar project={project} />}>
      {error ? (
        <Alert>
          {error}{" "}
          <button className="font-medium underline underline-offset-2" onClick={() => void refresh()}>
            Retry
          </button>
        </Alert>
      ) : !value ? (
        <div className="space-y-4">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-9 w-72" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      ) : (
        <ProjectContext.Provider value={value}>
          <StepProgress project={value.project} />
          <div className="mt-6 sm:mt-8">
            <StepGuard project={value.project}>{children}</StepGuard>
          </div>
        </ProjectContext.Provider>
      )}
    </AppFrame>
  );
}

/** Rail on the left (desktop), top bar, centred content. Shared by Home and project pages. */
export function AppFrame({ rail, top, children }: { rail?: ReactNode; top?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[68px] flex-col items-center border-r border-border bg-background py-4 lg:flex">
        <Link href="/" aria-label="All projects" className="rounded-[10px] transition-transform active:scale-95">
          <Logo />
        </Link>
        <div className="my-4 h-px w-8 bg-border" />
        <RailLink href="/" label="All projects" icon={<LayoutGrid className="h-[18px] w-[18px]" />} exact />
        {rail}
      </aside>
      <div className="lg:pl-[68px]">
        {top}
        <main className="mx-auto w-full max-w-[1180px] px-4 pt-5 pb-36 sm:px-6 sm:pt-7 lg:px-8 lg:pb-28">{children}</main>
      </div>
    </div>
  );
}

function RailLink({ href, label, icon, exact }: { href: string; label: string; icon: ReactNode; exact?: boolean }) {
  const pathname = usePathname();
  const active = exact ? pathname === href : pathname.startsWith(href);
  return (
    <Link
      href={href}
      aria-label={label}
      className={cx(
        "group relative flex h-10 w-10 items-center justify-center rounded-xl transition-colors",
        active ? "bg-card-3 text-foreground" : "text-muted hover:bg-card-2 hover:text-foreground",
      )}
    >
      {icon}
      <Tip>{label}</Tip>
    </Link>
  );
}

function Tip({ children }: { children: ReactNode }) {
  return (
    <span className="pointer-events-none absolute left-full z-40 ml-3 rounded-lg border border-border-strong bg-card-2 px-2.5 py-1.5 text-[12px] font-medium whitespace-nowrap text-foreground opacity-0 shadow-xl transition-opacity duration-150 group-hover:opacity-100">
      {children}
    </span>
  );
}

function StepRail({ project }: { project: ProjectOut | null }) {
  const pathname = usePathname();
  const current = currentStage(pathname);
  if (!project) return null;
  const done = doneCount(project);
  return (
    <nav aria-label="Steps" className="mt-2 flex flex-col items-center gap-1.5">
      {STEPS.map((s, i) => {
        const unlocked = isUnlocked(project, s.stage);
        const active = current === s.stage;
        const Icon = s.icon;
        const inner = (
          <>
            <Icon className="h-[18px] w-[18px]" />
            {i < done && !active ? <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-ok" /> : null}
            <Tip>
              <span className="text-muted">{i + 1}.</span> {s.label}
              {!unlocked ? <span className="text-muted"> · locked</span> : null}
            </Tip>
          </>
        );
        const cls = cx(
          "group relative flex h-10 w-10 items-center justify-center rounded-xl transition-colors",
          active ? "bg-card-3 text-foreground ring-1 ring-border-strong" : unlocked ? "text-subtle hover:bg-card-2 hover:text-foreground" : "cursor-not-allowed text-[#3a3a40]",
        );
        return unlocked ? (
          <Link key={s.stage} href={stepHref(project.id, s.stage)} aria-current={active ? "step" : undefined} aria-label={s.label} className={cls}>
            {inner}
          </Link>
        ) : (
          <span key={s.stage} aria-disabled aria-label={`${s.label}, locked`} className={cls}>
            {inner}
          </span>
        );
      })}
    </nav>
  );
}

export function TopBar({ project, right }: { project?: ProjectOut | null; right?: ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/80 pt-[var(--safe-top)] backdrop-blur-xl">
      <div className="mx-auto flex h-14 w-full max-w-[1180px] items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" aria-label="All projects" className="shrink-0 lg:hidden">
            <Logo className="h-7 w-7" />
          </Link>
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[13px]">
            <Link href="/" className={cx("shrink-0 text-muted transition-colors hover:text-foreground", project === undefined && "text-foreground")}>
              Projects
            </Link>
            {project !== undefined ? (
              <>
                <span className="text-[#3a3a40]">/</span>
                {project ? (
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-medium">{project.name}</span>
                    <span
                      className="hidden h-5 shrink-0 items-center rounded-md px-1.5 text-[11px] font-medium sm:inline-flex"
                      style={{ color: TEMPLATE_COLOR[project.template], background: "color-mix(in srgb, currentColor 14%, transparent)" }}
                    >
                      {TEMPLATE_LABEL[project.template] || project.template}
                    </span>
                  </span>
                ) : (
                  <Skeleton className="h-4 w-24" />
                )}
              </>
            ) : null}
          </nav>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {right}
          <span
            className="hidden h-8 items-center gap-2 rounded-full border border-border-strong bg-card-2 px-3 text-[12px] font-medium text-subtle sm:inline-flex"
            title="Data, solvers and the referee all run on this machine"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
            Local mode
          </span>
          {project !== undefined ? (
            <Link
              href="/"
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border-strong bg-card-2 text-subtle transition-colors hover:text-foreground"
              aria-label="Start a new problem"
              title="Start a new problem"
            >
              <Plus className="h-4 w-4" />
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function StepProgress({ project }: { project: ProjectOut }) {
  const pathname = usePathname();
  const current = currentStage(pathname);
  const idx = STEPS.findIndex((s) => s.stage === current);
  const step = STEPS[idx];
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  if (!step) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex w-full items-center gap-4 text-left lg:pointer-events-none"
        aria-label="Show all steps"
      >
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center justify-between gap-3 text-[12px]">
            <span className="flex items-center gap-1.5 font-medium text-subtle">
              <span className="num text-foreground">
                {idx + 1}/{STEPS.length}
              </span>
              <span className="text-[#3a3a40]">·</span>
              {step.phase}
              <ChevronDown className="h-3.5 w-3.5 text-muted lg:hidden" />
            </span>
            <span className="hidden text-muted sm:inline">{STEPS[idx + 1] ? `Next: ${STEPS[idx + 1].label}` : "Last step"}</span>
          </div>
          <Segments total={STEPS.length} filled={Math.min(doneCount(project), STEPS.length)} current={idx} size="sm" />
        </div>
      </button>
      {open ? <StepSheet project={project} current={current} onClose={() => setOpen(false)} /> : null}
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
      <div className="sheet-in absolute inset-x-0 bottom-0 rounded-t-[24px] border-t border-border-strong bg-card px-4 pt-2 pb-[calc(16px+var(--safe-bottom))]">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-strong" />
        <div className="mb-2 flex items-center justify-between px-1">
          <h2 className="text-[15px] font-semibold">Steps</h2>
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-card-2" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <ol className="space-y-1">
          {STEPS.map((s, i) => {
            const unlocked = isUnlocked(project, s.stage);
            const active = current === s.stage;
            const Icon = s.icon;
            const body = (
              <div
                className={cx(
                  "flex items-center gap-3 rounded-xl px-3 py-3",
                  active ? "bg-card-3" : unlocked ? "active:bg-card-2" : "opacity-45",
                )}
              >
                <span className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border", active ? "border-border-strong bg-card-2" : "border-border bg-card-2")}>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-medium">{s.label}</div>
                  <div className="text-[12px] text-muted">{s.blurb}</div>
                </div>
                {i < done ? (
                  <Check className="h-4 w-4 text-ok" />
                ) : !unlocked ? (
                  <Lock className="h-3.5 w-3.5 text-muted" />
                ) : active ? (
                  <span className="h-2 w-2 rounded-full bg-accent" />
                ) : null}
              </div>
            );
            return (
              <li key={s.stage}>
                {unlocked ? (
                  <Link href={stepHref(project.id, s.stage)} onClick={onClose}>
                    {body}
                  </Link>
                ) : (
                  body
                )}
              </li>
            );
          })}
        </ol>
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
