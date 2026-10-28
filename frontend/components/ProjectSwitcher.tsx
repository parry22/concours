"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronsUpDown, CreditCard, Plus, Trash2, UserRound } from "lucide-react";
import { NewProjectModal } from "@/components/NewProjectModal";
import { Button, Spinner, cx } from "@/components/ui";
import { api, errorText, type ProjectOut } from "@/lib/api";
import { status as statusCopy, switcher as copy } from "@/lib/copy";
import { fmtCompact } from "@/lib/format";
import { forgetProject } from "@/lib/last-project";
import { STEPS, landing } from "@/lib/stages";

const money = (x: number) => `${x < 0 ? "-" : ""}$${Math.abs(Math.round(x)).toLocaleString("en-US")}`;

/** One line under a project's name: today's money per day, or where its setup stands. */
function summary(p: ProjectOut): string {
  if (p.money_per_day != null) return copy.perDay(money(p.money_per_day));
  const step = STEPS.find((s) => s.slug === landing(p));
  return step ? copy.setup(step.label) : copy.noModel;
}

/**
 * The current project at the foot of the sidebar. Opens upward: every project with its result, a delete per row,
 * and New project (a modal). `placement="sheet"` renders the list inline for the phone menu.
 */
export function ProjectSwitcher({ current, placement = "sidebar", onNavigate }: { current?: ProjectOut | null; placement?: "sidebar" | "sheet"; onNavigate?: () => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(placement === "sheet");
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setProjects(await api.projects());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  useEffect(() => {
    if (!open || placement === "sheet") return;
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, placement]);

  async function remove(p: ProjectOut) {
    setDeleting(p.id);
    try {
      await api.deleteProject(p.id);
      forgetProject(p.id);
      setConfirm(null);
      await load();
      if (current?.id === p.id) router.push("/");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDeleting(null);
    }
  }

  const list = (
    <div className={cx(placement === "sidebar" && "select-pop absolute right-0 bottom-[calc(100%+8px)] left-0 z-40 origin-bottom overflow-hidden rounded-xl border border-border-strong bg-[#161618] shadow-[0_18px_50px_-12px_rgb(0_0_0/0.8)]")}>
      <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5">
        <span className="text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{copy.projects}</span>
        {projects ? <span className="num text-[11px] text-muted">{projects.length}</span> : null}
      </div>
      <ul className="scroll-thin max-h-[320px] overflow-y-auto px-1 pb-1">
        {!projects && !error ? (
          <li className="flex items-center gap-2 px-2.5 py-3 text-[12px] text-muted">
            <Spinner className="h-3.5 w-3.5" />
            {copy.loading}
          </li>
        ) : null}
        {error ? <li className="px-2.5 py-3 text-[12px] text-danger">{error}</li> : null}
        {projects?.map((p) => {
          const active = current?.id === p.id;
          return (
            <li key={p.id} className="group relative">
              {confirm === p.id ? (
                <div className="flex items-center gap-2 rounded-lg bg-card-3 px-2.5 py-2">
                  <span className="min-w-0 flex-1 truncate text-[12px] text-subtle">{copy.deleteAsk(p.name)}</span>
                  <Button size="sm" variant="danger" busy={deleting === p.id} onClick={() => void remove(p)}>
                    {copy.delete}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirm(null)} disabled={deleting === p.id}>
                    {copy.keep}
                  </Button>
                </div>
              ) : (
                <>
                  <Link
                    href={`/projects/${p.id}`}
                    onClick={() => {
                      setOpen(placement === "sheet");
                      onNavigate?.();
                    }}
                    className={cx("flex items-center gap-2.5 rounded-lg px-2.5 py-2 pr-9", active ? "bg-card-3" : "hover:bg-card-2")}
                  >
                    <span className="flex w-4 shrink-0 justify-center">{active ? <Check className="icon-brand h-3.5 w-3.5" strokeWidth={2.5} /> : null}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-medium">{p.name}</span>
                      <span className="flex items-center gap-1.5 text-[11px] text-muted">
                        {p.active_model && p.model_status !== "none" ? (
                          <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", p.model_status === "slipping" ? "bg-danger" : "bg-brand")} title={statusCopy[p.model_status]} />
                        ) : null}
                        <span className="num truncate">{summary(p)}</span>
                      </span>
                    </span>
                  </Link>
                  <button
                    onClick={() => setConfirm(p.id)}
                    className="absolute top-1/2 right-1.5 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-card-3 hover:text-danger focus-visible:opacity-100"
                    aria-label={copy.deleteLabel(p.name)}
                    title={copy.deleteLabel(p.name)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </li>
          );
        })}
      </ul>
      <div className="border-t border-border p-1">
        <button onClick={() => setModal(true)} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-subtle hover:bg-card-2 hover:text-foreground">
          <span className="flex w-4 shrink-0 justify-center">
            <Plus className="h-4 w-4" />
          </span>
          {copy.newProject}
        </button>
        <Link href="/account" onClick={() => { setOpen(placement === "sheet"); onNavigate?.(); }}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-subtle hover:bg-card-2 hover:text-foreground">
          <span className="flex w-4 shrink-0 justify-center">
            <UserRound className="h-4 w-4" />
          </span>
          {copy.account}
        </Link>
      </div>
    </div>
  );

  return (
    <div ref={root} className="relative">
      {placement === "sidebar" ? (
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-haspopup="menu"
          className={cx(
            "flex w-full items-center gap-2.5 rounded-xl border bg-card px-2.5 py-2 text-left transition-[border-color,background-color] duration-150 hover:bg-card-2",
            open ? "border-border-strong" : "border-border",
          )}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-card-2">
            <CreditCard className="icon-brand h-4 w-4" strokeWidth={1.75} aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium">{current?.name ?? copy.choose}</span>
            <span className="num block truncate text-[11px] text-muted">
              {current ? (current.profile?.n_rows ? copy.payments(fmtCompact(current.profile.n_rows)) : copy.noData) : copy.chooseLine}
            </span>
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted" aria-hidden />
        </button>
      ) : null}
      {open ? list : null}
      {modal ? (
        <NewProjectModal
          onClose={() => {
            setModal(false);
            onNavigate?.();
          }}
        />
      ) : null}
    </div>
  );
}
