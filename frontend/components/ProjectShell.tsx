"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, Check, Lock, Menu, X } from "lucide-react";
import { ProjectSwitcher } from "@/components/ProjectSwitcher";
import { api, errorText, type ProjectOut } from "@/lib/api";
import { SETUP, STEPS, TABS, isUnlocked, landing, setupDone, slugOf, stepHref, type Slug } from "@/lib/stages";
import { brand, nav, phases } from "@/lib/copy";
import { rememberProject } from "@/lib/last-project";
import { Alert, Logo, Segments, Skeleton, StatusPill, cx } from "./ui";

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
    rememberProject(id);
  }, [refresh, id]);

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
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      ) : (
        <ProjectContext.Provider value={value}>
          <StepGuard project={value.project}>{children}</StepGuard>
        </ProjectContext.Provider>
      )}
    </AppFrame>
  );
}

/**
 * Desktop: a sidebar with the project's pages, its setup steps below them, and the project switcher at the foot.
 * Phones: a sticky header; the menu opens the same navigation as a sheet. `project` undefined: no project open.
 */
export function AppFrame({ project, children }: { project?: ProjectOut | null; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <Sidebar project={project} />
      <MobileHeader project={project} />
      <div className="lg:pl-[248px]">
        <main className="mx-auto w-full max-w-[1120px] px-4 pt-5 pb-36 sm:px-6 sm:pt-7 lg:px-10 lg:pt-10 lg:pb-28">{children}</main>
      </div>
    </div>
  );
}

function Sidebar({ project }: { project?: ProjectOut | null }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-border bg-background lg:flex">
      <Link href="/" className="flex items-center gap-2 px-5 pt-5 pb-3" aria-label={brand.name}>
        <Logo />
        <span className="text-[15px] font-semibold tracking-[-0.01em]">{brand.name}</span>
      </Link>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {project ? <ProjectNav project={project} /> : project === null ? <Skeleton className="mt-4 h-56" /> : null}
      </div>
      <div className="border-t border-border p-3">
        <ProjectSwitcher current={project ?? null} />
      </div>
    </aside>
  );
}

/** The project's pages, then its setup steps (with progress until setup is done). */
function ProjectNav({ project, onNavigate, roomy }: { project: ProjectOut; onNavigate?: () => void; roomy?: boolean }) {
  const pathname = usePathname();
  const current = slugOf(pathname);
  const done = setupDone(project);
  const finished = done >= SETUP.length;
  return (
    <nav aria-label={nav.steps}>
      <div className="mt-3">
        <div className="flex h-6 items-center justify-between px-2">
          <span className="text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{phases.Project}</span>
          {project.active_model ? (
            <span className="flex items-center gap-1.5">
              <span className="num text-[11px] font-medium text-subtle">v{project.active_model.version}</span>
              <StatusPill status={project.model_status} />
            </span>
          ) : null}
        </div>
        <ol className="mt-1 space-y-0.5">
          {TABS.map((s) => (
            <li key={s.slug}>
              <TabRow project={project} slug={s.slug} active={current === s.slug} onNavigate={onNavigate} roomy={roomy} />
            </li>
          ))}
        </ol>
      </div>
      <div className="mt-6">
        <div className="flex h-6 items-center justify-between px-2">
          <span className="text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{phases.Setup}</span>
          <span className={cx("num text-[11px]", finished ? "text-subtle" : "text-muted")}>
            {done}/{SETUP.length}
          </span>
        </div>
        {!finished ? <Segments total={SETUP.length} filled={done} size="sm" className="mt-1.5 px-2" /> : null}
        <ol className="mt-1.5 space-y-0.5">
          {SETUP.map((s, i) => (
            <li key={s.slug}>
              <StepRow project={project} slug={s.slug} n={i + 1} active={current === s.slug} done={i < done} onNavigate={onNavigate} roomy={roomy} />
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}

function TabRow({ project, slug, active, onNavigate, roomy }: { project: ProjectOut; slug: Slug; active: boolean; onNavigate?: () => void; roomy?: boolean }) {
  const s = STEPS.find((x) => x.slug === slug)!;
  const unlocked = isUnlocked(project, slug);
  const Icon = s.icon;
  const alert = slug === "overview" && project.health === "slipping";
  const body = (
    <div className={cx("flex items-center gap-2.5 rounded-lg px-2", roomy ? "h-11" : "h-9", active ? "bg-card-2 text-foreground" : unlocked ? "text-subtle hover:bg-card hover:text-foreground" : "text-muted opacity-50")}>
      <Icon className={cx("h-4 w-4 shrink-0", active ? "icon-brand" : "text-muted")} strokeWidth={1.75} />
      <span className="text-[13px] font-medium">{s.label}</span>
      {alert ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-danger" aria-label={nav.slipping} /> : null}
      {!unlocked ? <Lock className="ml-auto h-3 w-3" aria-hidden /> : null}
    </div>
  );
  return unlocked ? (
    <Link href={stepHref(project.id, slug)} aria-current={active ? "page" : undefined} onClick={onNavigate} className="block">
      {body}
    </Link>
  ) : (
    <div aria-disabled title={nav.tabsLocked}>
      {body}
    </div>
  );
}

function StepRow({ project, slug, n, active, done, onNavigate, roomy }: { project: ProjectOut; slug: Slug; n: number; active: boolean; done: boolean; onNavigate?: () => void; roomy?: boolean }) {
  const s = STEPS.find((x) => x.slug === slug)!;
  const unlocked = isUnlocked(project, slug);
  const body = (
    <div className={cx("flex items-center gap-2.5 rounded-lg px-2", roomy ? "h-11" : "h-9", active ? "bg-card-2" : unlocked ? "hover:bg-card" : "opacity-50")}>
      <StepDot n={n} state={done && !active ? "done" : active ? "active" : unlocked ? "todo" : "locked"} />
      <span className={cx("text-[13px] font-medium", active ? "text-foreground" : "text-subtle")}>{s.label}</span>
    </div>
  );
  return unlocked ? (
    <Link href={stepHref(project.id, slug)} aria-current={active ? "step" : undefined} onClick={onNavigate} className="block">
      {body}
    </Link>
  ) : (
    <div aria-disabled title={nav.stepLocked}>
      {body}
    </div>
  );
}

function StepDot({ n, state }: { n: number; state: "done" | "active" | "todo" | "locked" }) {
  if (state === "done")
    return (
      <span className="bg-brand flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-background">
        <Check className="h-2.5 w-2.5" strokeWidth={3.5} />
      </span>
    );
  if (state === "locked")
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-border text-muted">
        <Lock className="h-2 w-2" />
      </span>
    );
  return (
    <span className={cx("num flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px]", state === "active" ? "bg-foreground font-semibold text-background" : "border border-border-strong text-subtle")}>{n}</span>
  );
}

function MobileHeader({ project }: { project?: ProjectOut | null }) {
  const pathname = usePathname();
  const step = STEPS.find((s) => s.slug === slugOf(pathname));
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <>
      <header className="sticky top-0 z-20 border-b border-border bg-background/85 pt-[var(--safe-top)] backdrop-blur-xl lg:hidden">
        <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
          <Link href="/" aria-label={brand.name} className="shrink-0">
            <Logo className="h-6 w-[19px]" />
          </Link>
          <div className="min-w-0 flex-1 leading-tight">
            {project ? (
              <>
                <div className="truncate text-[11px] text-muted">{project.name}</div>
                <div className="truncate text-[14px] font-medium">{step?.label ?? nav.project}</div>
              </>
            ) : project === null ? (
              <Skeleton className="h-4 w-32" />
            ) : (
              <span className="text-[15px] font-semibold">{brand.name}</span>
            )}
          </div>
          <button onClick={() => setOpen(true)} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border-strong bg-card-2" aria-label={nav.menu}>
            <Menu className="h-4 w-4" />
          </button>
        </div>
      </header>
      {open ? <MenuSheet project={project ?? null} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function MenuSheet({ project, onClose }: { project: ProjectOut | null; onClose: () => void }) {
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
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal aria-label={nav.menu}>
      <button className="fade-in absolute inset-0 bg-black/60 backdrop-blur-[2px]" aria-label="Close" onClick={onClose} />
      <div className="sheet-in absolute inset-x-0 bottom-0 max-h-[88dvh] overflow-y-auto rounded-t-[24px] border-t border-border-strong bg-card px-3 pt-2 pb-[calc(16px+var(--safe-bottom))]">
        <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-border-strong" />
        <div className="flex items-center justify-between px-2">
          <h2 className="truncate text-[15px] font-semibold">{project?.name ?? brand.name}</h2>
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-card-2" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        {project ? <ProjectNav project={project} onNavigate={onClose} roomy /> : null}
        <div className="mt-5 rounded-xl border border-border bg-background/40">
          <ProjectSwitcher current={project} placement="sheet" onNavigate={onClose} />
        </div>
      </div>
    </div>
  );
}

function StepGuard({ project, children }: { project: ProjectOut; children: ReactNode }) {
  const pathname = usePathname();
  const slug = slugOf(pathname);
  if (!slug || isUnlocked(project, slug)) return <>{children}</>;
  const to = STEPS.find((s) => s.slug === landing(project))!;
  return (
    <Alert kind="warn">
      {nav.stepOpensLater}{" "}
      <Link href={stepHref(project.id, to.slug)} className="font-medium underline underline-offset-2">
        {nav.goTo(to.label)}
      </Link>
    </Alert>
  );
}

/** The one primary action of a step. Pinned above the home indicator on phones, a floating bar on desktop. */
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
export function NextLink({ stage, label, disabled, href }: { stage?: Slug; label?: string; disabled?: boolean; href?: string }) {
  const { project } = useProject();
  const step = stage ? STEPS.find((s) => s.slug === stage) : undefined;
  const ok = !disabled && (href ? true : stage ? isUnlocked(project, stage) : false);
  const text = label || step?.label || "Continue";
  const target = href || (stage ? stepHref(project.id, stage) : "#");
  const cls = "inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-[14px] font-medium whitespace-nowrap transition-[background-color,transform] duration-150";
  return ok ? (
    <Link href={target} className={cx(cls, "bg-foreground text-background hover:bg-white active:scale-[0.98]")}>
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
