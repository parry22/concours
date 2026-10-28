"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorText, type ProjectOut, type Stage, type TemplateId } from "@/lib/api";
import { STEPS, isUnlocked, reachedIndex, stepHref, TEMPLATE_LABEL } from "@/lib/stages";
import { Alert, Button, Loading, cx } from "./ui";

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
  }, [refresh]);

  const value = useMemo(() => (project ? { project, setProject, refresh } : null), [project, refresh]);

  return (
    <div className="min-h-screen">
      <Header project={project} />
      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-6">
        {error ? (
          <Alert>
            {error}{" "}
            <button className="underline" onClick={() => void refresh()}>
              Retry
            </button>
          </Alert>
        ) : !value ? (
          <Loading label="Loading project" />
        ) : (
          <ProjectContext.Provider value={value}>
            <Stepper project={value.project} />
            <div className="mt-8">
              <StepGuard project={value.project}>{children}</StepGuard>
            </div>
          </ProjectContext.Provider>
        )}
      </main>
    </div>
  );
}

function Header({ project }: { project: ProjectOut | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState<TemplateId | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function switchTo(template: TemplateId) {
    setBusy(template);
    setErr(null);
    try {
      const p = await api.createProject(template);
      router.push(stepHref(p.id, "intake"));
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-6 px-6 py-3">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            Brief
          </Link>
          {project ? (
            <span className="text-sm text-muted">
              {project.name}
              <span className="ml-2 rounded-full bg-stone-100 px-2 py-0.5 text-xs">{TEMPLATE_LABEL[project.template] || project.template}</span>
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Template</span>
          {(["fraud", "churn"] as TemplateId[]).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={project?.template === t ? "primary" : "secondary"}
              busy={busy === t}
              disabled={busy !== null}
              onClick={() => void switchTo(t)}
              title={`Start a new ${TEMPLATE_LABEL[t]} project from the bundled dataset`}
            >
              {TEMPLATE_LABEL[t]}
            </Button>
          ))}
        </div>
      </div>
      {err ? (
        <div className="mx-auto w-full max-w-6xl px-6 pb-3">
          <Alert>{err}</Alert>
        </div>
      ) : null}
    </header>
  );
}

function Stepper({ project }: { project: ProjectOut }) {
  const pathname = usePathname();
  const current = (pathname.split("/").pop() || "") as Stage;

  return (
    <nav aria-label="Steps">
      <ol className="grid grid-cols-6 gap-2">
        {STEPS.map((s, i) => {
          const unlocked = isUnlocked(project, s.stage);
          const active = current === s.stage;
          const inner = (
            <div
              className={cx(
                "flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors",
                active ? "border-foreground bg-foreground text-white" : unlocked ? "border-border bg-card hover:bg-stone-50" : "border-transparent bg-stone-100 text-stone-400",
              )}
            >
              <span
                className={cx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  active ? "bg-white text-foreground" : unlocked ? "bg-stone-200 text-foreground" : "bg-stone-200 text-stone-400",
                )}
              >
                {i + 1}
              </span>
              <span className="hidden truncate font-medium xl:inline">{s.label}</span>
              <span className="truncate font-medium xl:hidden">{s.short}</span>
            </div>
          );
          return (
            <li key={s.stage}>
              {unlocked ? (
                <Link href={stepHref(project.id, s.stage)} aria-current={active ? "step" : undefined}>
                  {inner}
                </Link>
              ) : (
                <div aria-disabled title="Finish the previous step first">
                  {inner}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function StepGuard({ project, children }: { project: ProjectOut; children: ReactNode }) {
  const pathname = usePathname();
  const current = pathname.split("/").pop() || "";
  const stage = STEPS.find((s) => s.stage === current)?.stage;
  if (!stage || isUnlocked(project, stage)) return <>{children}</>;
  const reached = STEPS[reachedIndex(project)];
  return (
    <Alert kind="warn">
      This step is locked until the earlier ones are done.{" "}
      <Link href={stepHref(project.id, reached.stage)} className="underline">
        Go to {reached.label}
      </Link>
    </Alert>
  );
}

export function NextStep({ stage, label, disabled }: { stage: Stage; label?: string; disabled?: boolean }) {
  const { project } = useProject();
  const step = STEPS.find((s) => s.stage === stage);
  const ok = !disabled && isUnlocked(project, stage);
  return (
    <div className="mt-6 flex justify-end">
      {ok ? (
        <Link href={stepHref(project.id, stage)} className="inline-flex h-10 items-center rounded-lg bg-foreground px-4 text-sm font-medium text-white hover:bg-stone-700">
          {label || `Continue to ${step?.label}`}
        </Link>
      ) : (
        <span className="inline-flex h-10 cursor-not-allowed items-center rounded-lg bg-stone-200 px-4 text-sm font-medium text-stone-400">
          {label || `Continue to ${step?.label}`}
        </span>
      )}
    </div>
  );
}
