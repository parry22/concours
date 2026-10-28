"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, ChevronRight, CreditCard, FileUp, Trash2, UserMinus, type LucideIcon } from "lucide-react";
import { AppFrame, TopBar } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, Segments, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type ProjectOut, type TemplateId, type TemplateOut } from "@/lib/api";
import { STEPS, TEMPLATE_COLOR, TEMPLATE_LABEL, doneCount, stageIndex, stepHref } from "@/lib/stages";
import { fmtAgo, fmtCompact, fmtInt, solverShort } from "@/lib/format";

const TEMPLATE_ICON: Record<string, LucideIcon> = { fraud: CreditCard, churn: UserMinus, custom: FileUp };
const TEMPLATE_METRIC: Record<string, string> = {
  fraud: "Fraud caught at 1 false alarm per 1,000",
  churn: "Leavers reached in the riskiest 10%",
  custom: "You pick the outcome column",
};

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
  const rows = projects?.reduce((a, p) => a + (p.profile?.n_rows ?? 0), 0) ?? 0;
  const validated = projects?.filter((p) => p.apex_validation === "pass").length ?? 0;
  const cards: { id: TemplateId; name: string; description: string; has_dataset: boolean }[] = templates
    ? [...templates.slice().sort((a, b) => (a.id === "fraud" ? -1 : b.id === "fraud" ? 1 : 0)), { id: "custom", name: "Your own CSV", description: "Upload a spreadsheet with one row per case and one column that records the outcome.", has_dataset: true }]
    : [];

  return (
    <AppFrame top={<TopBar />}>
      <div className="flex flex-col gap-1">
        <div className="text-[12px] font-medium text-muted">From spreadsheet to proven model</div>
        <h1 className="text-[26px] font-semibold tracking-[-0.02em] sm:text-[30px]">Prediction problems</h1>
        <p className="max-w-2xl text-[14px] leading-relaxed text-subtle">
          Describe a problem in plain words, load a CSV, and Brief turns it into fair rules, protects the data, proves it with local
          solvers and hands back a model.
        </p>
      </div>

      {error ? <Alert className="mt-6">{error}</Alert> : null}

      <section className="mt-6 grid grid-cols-2 gap-3 sm:mt-8 lg:grid-cols-4">
        <Kpi label="Problems" value={projects ? fmtInt(projects.length) : null} />
        <Kpi label="Winners picked" value={projects ? fmtInt(finalized) : null} sub={projects && projects.length ? `of ${projects.length}` : undefined} />
        <Kpi label="Rows protected" value={projects ? fmtCompact(rows) : null} />
        <Kpi label="Apex validated" value={projects ? fmtInt(validated) : null} dot={validated > 0} />
      </section>

      <section className="mt-10">
        <SectionTitle>Start a problem</SectionTitle>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {!templates
            ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-[188px] rounded-2xl" />)
            : cards.map((t) => {
                const Icon = TEMPLATE_ICON[t.id] ?? FileUp;
                const color = TEMPLATE_COLOR[t.id];
                const disabled = busy !== null || !t.has_dataset;
                return (
                  <button
                    key={t.id}
                    onClick={() => void create(t.id)}
                    disabled={disabled}
                    className={cx(
                      "group relative flex min-h-[188px] flex-col overflow-hidden rounded-2xl border border-border bg-card p-5 text-left transition-[border-color,background-color,transform] duration-200",
                      "hover:border-border-strong hover:bg-[#161618] active:scale-[0.99] disabled:cursor-not-allowed",
                      t.id === "custom" && "border-dashed",
                    )}
                  >
                    <span
                      aria-hidden
                      className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full opacity-[0.10] blur-2xl transition-opacity duration-300 group-hover:opacity-20"
                      style={{ background: color }}
                    />
                    <div className="flex items-center justify-between">
                      <span
                        className="flex h-10 w-10 items-center justify-center rounded-xl border border-border-strong"
                        style={{ color, background: "color-mix(in srgb, currentColor 10%, var(--card-2))" }}
                      >
                        <Icon className="h-[18px] w-[18px]" />
                      </span>
                      {t.id !== "custom" ? <Badge tone={t.has_dataset ? "neutral" : "warn"}>{t.has_dataset ? "Sample data" : "Data not fetched"}</Badge> : <Badge>Max 200 MB</Badge>}
                    </div>
                    <h3 className="mt-4 text-[16px] font-semibold tracking-[-0.01em]">{t.name}</h3>
                    <p className="mt-1 flex-1 text-[13px] leading-relaxed text-muted">{t.description}</p>
                    <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-3 text-[12px]">
                      <span className="flex min-w-0 items-center gap-2 text-subtle">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
                        <span className="truncate">{TEMPLATE_METRIC[t.id]}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1 font-medium text-foreground">
                        {busy === t.id ? <Spinner className="h-3.5 w-3.5" /> : null}
                        Start
                        <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </button>
                );
              })}
        </div>
      </section>

      <section className="mt-10">
        <div className="flex items-center justify-between">
          <SectionTitle>Your projects</SectionTitle>
          {projects && projects.length > 0 ? <span className="num text-[12px] text-muted">{projects.length}</span> : null}
        </div>
        {!projects ? (
          <div className="mt-3 space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[72px] rounded-2xl" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="mt-3">
            <Empty>No projects yet. Start with the fraud template above: it runs end to end in about three minutes.</Empty>
          </div>
        ) : (
          <Card pad={false} className="mt-3 overflow-hidden">
            <div className="hidden grid-cols-[minmax(0,2fr)_minmax(0,1.6fr)_minmax(0,1fr)_88px] gap-4 border-b border-border px-5 py-2.5 text-[12px] font-medium text-muted md:grid">
              <span>Name</span>
              <span>Progress</span>
              <span>Winner</span>
              <span />
            </div>
            <ul className="divide-y divide-border">
              {projects.map((p) => {
                const step = STEPS[stageIndex(p.stage)];
                const done = doneCount(p);
                const confirming = confirmId === p.id;
                return (
                  <li key={p.id} className="group relative">
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 px-4 py-3.5 transition-colors hover:bg-[#161618] md:grid-cols-[minmax(0,2fr)_minmax(0,1.6fr)_minmax(0,1fr)_88px] md:px-5">
                      <Link href={`/projects/${p.id}`} className="flex min-w-0 items-center gap-3 after:absolute after:inset-0 after:content-['']">
                        <span
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-border-strong"
                          style={{ color: TEMPLATE_COLOR[p.template], background: "color-mix(in srgb, currentColor 10%, var(--card-2))" }}
                        >
                          {(() => {
                            const I = TEMPLATE_ICON[p.template] ?? FileUp;
                            return <I className="h-4 w-4" />;
                          })()}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[14px] font-medium">{p.name}</span>
                          <span className="block truncate text-[12px] text-muted">
                            {TEMPLATE_LABEL[p.template]} · {p.profile?.n_rows ? `${fmtCompact(p.profile.n_rows)} rows · ` : ""}
                            {fmtAgo(p.created_at)}
                          </span>
                        </span>
                      </Link>
                      <div className="col-span-2 row-start-2 min-w-0 md:col-span-1 md:row-start-auto">
                        <div className="mb-1.5 flex items-center justify-between text-[12px]">
                          <span className="text-subtle">{step?.label}</span>
                          <span className="num text-muted">
                            {done}/{STEPS.length}
                          </span>
                        </div>
                        <Segments total={STEPS.length} filled={done} size="sm" />
                      </div>
                      <div className="hidden min-w-0 text-[13px] md:block">
                        {p.winner_solver ? (
                          <span className="flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
                            <span className="truncate">{solverShort(p.winner_solver)}</span>
                          </span>
                        ) : (
                          <span className="text-muted">Not yet</span>
                        )}
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

function Kpi({ label, value, sub, dot }: { label: string; value: string | null; sub?: string; dot?: boolean }) {
  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-4">
      <div className="flex items-center gap-2 text-[12px] font-medium text-muted">
        {dot ? <span className="h-1.5 w-1.5 rounded-full bg-ok" /> : null}
        {label}
      </div>
      {value === null ? (
        <Skeleton className="mt-2 h-7 w-16" />
      ) : (
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="num text-[26px] leading-none font-medium sm:text-[30px]">{value}</span>
          {sub ? <span className="num text-[12px] text-muted">{sub}</span> : null}
        </div>
      )}
    </div>
  );
}
