"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, ChevronRight, FileUp, Trash2 } from "lucide-react";
import { AppFrame } from "@/components/ProjectShell";
import { Alert, Button, Card, Empty, Segments, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type ProjectOut, type TemplateId, type TemplateOut } from "@/lib/api";
import { STEPS, TEMPLATE_ICON, TEMPLATE_LABEL, doneCount, stageIndex, stepHref } from "@/lib/stages";
import { fmtAgo, fmtCompact, solverShort } from "@/lib/format";

const TEMPLATE_METRIC: Record<string, string> = {
  fraud: "Fraud caught at 1 false alarm per 1,000",
  churn: "Leavers reached in the riskiest 10%",
  custom: "You pick the outcome column",
};

type StartCard = { id: TemplateId; name: string; description: string; has_dataset: boolean };

export default function Home() {
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateOut[] | null>(null);
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  async function load() {
    try {
      const [t, p] = await Promise.all([api.templates(), api.projects()]);
      setTemplates(t);
      setProjects(p);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function create(template: TemplateId) {
    setBusy(template);
    setError(null);
    try {
      const p = await api.createProject(template);
      router.push(stepHref(p.id, "upload"));
    } catch (e) {
      setError(errorText(e));
      setBusy(null);
    }
  }

  async function remove(p: ProjectOut) {
    setBusy(p.id);
    try {
      await api.deleteProject(p.id);
      setConfirmId(null);
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const finalized = projects?.filter((p) => p.finalized).length ?? 0;
  const validated = projects?.filter((p) => p.apex_validation === "pass").length ?? 0;
  const cards: StartCard[] = templates
    ? [
        ...templates.slice().sort((a, b) => (a.id === "fraud" ? -1 : b.id === "fraud" ? 1 : 0)),
        { id: "custom", name: "Your own CSV", description: "One row per case and one column that records the outcome.", has_dataset: true },
      ]
    : [];

  return (
    <AppFrame>
      <h1 className="text-[24px] font-semibold tracking-[-0.02em] sm:text-[28px]">Prediction problems</h1>
      <p className="mt-1.5 max-w-xl text-[14px] leading-relaxed text-subtle">
        Turn a spreadsheet into fair rules, protected data and a proven model, in about three minutes.
      </p>

      {error ? <Alert className="mt-6">{error}</Alert> : null}

      <section id="start" className="mt-7 scroll-mt-20 sm:mt-9">
        <SectionTitle>Start a problem</SectionTitle>

        {/* Phones: compact rows. */}
        <Card pad={false} className="mt-3 overflow-hidden sm:hidden">
          {!templates ? (
            <div className="space-y-2 p-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {cards.map((t) => (
                <li key={t.id}>
                  <button
                    onClick={() => void create(t.id)}
                    disabled={busy !== null || !t.has_dataset}
                    className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-card-2 disabled:opacity-50"
                  >
                    <TemplateGlyph id={t.id} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium">{t.name}</span>
                      <span className="block truncate text-[12px] text-muted">{TEMPLATE_METRIC[t.id]}</span>
                    </span>
                    {busy === t.id ? <Spinner className="h-4 w-4 text-muted" /> : <ArrowRight className="h-4 w-4 text-muted" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Larger screens: cards. */}
        <div className="mt-3 hidden gap-3 sm:grid sm:grid-cols-3">
          {!templates
            ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-[164px] rounded-2xl" />)
            : cards.map((t) => (
                <button
                  key={t.id}
                  onClick={() => void create(t.id)}
                  disabled={busy !== null || !t.has_dataset}
                  className={cx(
                    "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card p-4 text-left transition-[border-color,background-color,transform] duration-200 lg:p-5",
                    "hover:border-border-strong hover:bg-[#161618] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60",
                    t.id === "custom" && "border-dashed",
                  )}
                >
                  <span
                    aria-hidden
                    className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full opacity-[0.10] blur-2xl transition-opacity duration-300 group-hover:opacity-20"
                    style={{ background: "var(--brand-gradient)" }}
                  />
                  <TemplateGlyph id={t.id} />
                  <h3 className="mt-3.5 text-[15px] font-semibold tracking-[-0.01em]">{t.name}</h3>
                  <p className="mt-1 line-clamp-2 flex-1 text-[13px] leading-relaxed text-muted">{t.description}</p>
                  <div className="mt-4 flex items-center justify-between gap-3 text-[12px]">
                    <span className="truncate text-subtle">{TEMPLATE_METRIC[t.id]}</span>
                    <span className="flex shrink-0 items-center gap-1 font-medium">
                      {busy === t.id ? <Spinner className="h-3.5 w-3.5" /> : null}
                      Start
                      <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                    </span>
                  </div>
                </button>
              ))}
        </div>
      </section>

      <section className="mt-10">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Your projects</SectionTitle>
          {projects && projects.length > 0 ? (
            <div className="flex items-center gap-1.5 text-[12px]">
              <Chip>{projects.length} total</Chip>
              <Chip>{finalized} with a winner</Chip>
              <Chip>
                <span className="bg-brand h-1.5 w-1.5 rounded-full" />
                {validated} Apex ready
              </Chip>
            </div>
          ) : null}
        </div>
        {!projects ? (
          <div className="mt-3 space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[72px] rounded-2xl" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="mt-3">
            <Empty>No projects yet. Start with card fraud above: it runs end to end in about three minutes.</Empty>
          </div>
        ) : (
          <Card pad={false} className="mt-3 overflow-hidden">
            <div className="hidden grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_minmax(0,1fr)_72px] gap-5 border-b border-border px-5 py-2.5 text-[12px] font-medium text-muted md:grid">
              <span>Name</span>
              <span>Progress</span>
              <span>Winner</span>
              <span />
            </div>
            <ul className="divide-y divide-border">
              {projects.map((p) => {
                const done = doneCount(p);
                const confirming = confirmId === p.id;
                return (
                  <li key={p.id} className="group relative">
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 px-4 py-3.5 transition-colors hover:bg-[#161618] md:grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_minmax(0,1fr)_72px] md:gap-x-5 md:px-5">
                      <Link href={`/projects/${p.id}`} className="flex min-w-0 items-center gap-3 after:absolute after:inset-0 after:content-['']">
                        <TemplateGlyph id={p.template} small />
                        <span className="min-w-0">
                          <span className="block truncate text-[14px] font-medium">{p.name}</span>
                          <span className="block truncate text-[12px] text-muted">
                            {TEMPLATE_LABEL[p.template]}
                            {p.profile?.n_rows ? ` · ${fmtCompact(p.profile.n_rows)} rows` : ""} · {fmtAgo(p.created_at)}
                          </span>
                        </span>
                      </Link>
                      <div className="col-span-2 row-start-2 min-w-0 md:col-span-1 md:row-start-auto">
                        <div className="mb-1.5 flex items-center justify-between text-[12px]">
                          <span className="text-subtle">{done >= STEPS.length ? "Apex ready" : STEPS[stageIndex(p.stage)]?.label}</span>
                          <span className="num text-muted">
                            {done}/{STEPS.length}
                          </span>
                        </div>
                        <Segments total={STEPS.length} filled={done} size="sm" />
                      </div>
                      <div className="hidden min-w-0 truncate text-[13px] md:block">
                        {p.winner_solver ? solverShort(p.winner_solver) : <span className="text-muted">Not yet</span>}
                      </div>
                      <div className="relative z-10 flex items-center justify-end gap-1">
                        {confirming ? (
                          <>
                            <Button size="sm" variant="danger" busy={busy === p.id} onClick={() => void remove(p)}>
                              Delete
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)} disabled={busy === p.id}>
                              Keep
                            </Button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => setConfirmId(p.id)}
                              disabled={busy !== null}
                              className="flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-card-3 hover:text-danger md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                              aria-label={`Delete ${p.name}`}
                              title="Delete project and its files"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                            <ChevronRight className="pointer-events-none h-4 w-4 text-muted" />
                          </>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        )}
      </section>
    </AppFrame>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-[13px] font-medium text-subtle">{children}</h2>;
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="num inline-flex h-6 items-center gap-1.5 rounded-md bg-card-2 px-2 text-[11px] text-subtle">{children}</span>;
}

function TemplateGlyph({ id, small }: { id: string; small?: boolean }) {
  const Icon = TEMPLATE_ICON[id] ?? FileUp;
  return (
    <span
      className={cx("flex shrink-0 items-center justify-center border border-border-strong bg-card-2", small ? "h-9 w-9 rounded-[10px]" : "h-10 w-10 rounded-xl")}
    >
      <Icon className="icon-brand h-4 w-4" />
    </span>
  );
}
