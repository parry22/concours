"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, ChevronRight, FileUp, Trash2 } from "lucide-react";
import { AppFrame } from "@/components/ProjectShell";
import { Alert, Button, Card, Empty, Skeleton, Spinner, StatusPill, cx } from "@/components/ui";
import { api, errorText, type ProjectOut, type TemplateId, type TemplateOut } from "@/lib/api";
import { STEPS, TEMPLATE_ICON, stageIndex, stepHref } from "@/lib/stages";
import { home, status as statusCopy, tooltips } from "@/lib/copy";
import { fmtAgo, fmtCompact } from "@/lib/format";

type StartCard = { id: TemplateId; title: string; line: string; footer: string; has_dataset: boolean };

const ORDER: TemplateId[] = ["fraud", "churn", "leads", "custom"];

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

  const live = projects?.filter((p) => p.active_model).length ?? 0;
  const improving = projects?.filter((p) => p.model_status === "improving").length ?? 0;
  const ready = projects?.filter((p) => p.apex_validation === "pass").length ?? 0;
  const has = new Set((templates ?? []).filter((t) => t.has_dataset).map((t) => t.id));
  const cards: StartCard[] = templates ? ORDER.map((id) => ({ id, ...home.cards[id], has_dataset: id === "custom" || has.has(id) })) : [];
  // The hero's sample stat: the latest fraud project's measured result, else the dataset line.
  const fraudResult = projects?.find((p) => p.template === "fraud" && p.result_short)?.result_short;

  return (
    <AppFrame>
      <h1 className="max-w-3xl text-[26px] font-semibold tracking-[-0.02em] sm:text-[32px]">{home.h1}</h1>
      <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-subtle sm:text-[15px]">{home.subhead}</p>

      {error ? <Alert className="mt-6">{error}</Alert> : null}

      <section id="start" className="mt-7 scroll-mt-20 sm:mt-9">
        <SectionTitle>{home.start}</SectionTitle>

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
                  <button onClick={() => void create(t.id)} disabled={busy !== null || !t.has_dataset} className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-card-2 disabled:opacity-50">
                    <TemplateGlyph id={t.id} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium">{t.title}</span>
                      <span className="block text-[12px] leading-snug text-muted">{t.line}</span>
                    </span>
                    {busy === t.id ? <Spinner className="h-4 w-4 text-muted" /> : <ArrowRight className="h-4 w-4 text-muted" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Larger screens: cards. Card fraud is the hero and spans two columns; your own CSV is a full-width row under them. */}
        <div className="mt-3 hidden gap-3 sm:grid sm:grid-cols-2 lg:grid-cols-4">
          {!templates
            ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className={cx("h-[176px] rounded-2xl", i === 0 && "sm:col-span-2", i === 3 && "sm:col-span-2 lg:col-span-4 lg:h-[88px]")} />)
            : cards.map((t) => {
                const hero = t.id === "fraud";
                const own = t.id === "custom";
                if (own)
                  return (
                    <button
                      key={t.id}
                      onClick={() => void create(t.id)}
                      disabled={busy !== null}
                      className="group flex items-center gap-4 rounded-2xl border border-dashed border-border bg-card p-5 text-left transition-[border-color,background-color,transform] duration-200 hover:border-border-strong hover:bg-[#161618] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 sm:col-span-2 lg:col-span-4"
                    >
                      <TemplateGlyph id={t.id} />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                          <span className="text-[15px] font-semibold tracking-[-0.01em]">{t.title}</span>
                          <span className="text-[14px] text-subtle">{t.line}</span>
                        </span>
                        <span className="mt-0.5 block text-[12px] text-muted">{t.footer}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1 text-[12px] font-medium">
                        {busy === t.id ? <Spinner className="h-3.5 w-3.5" /> : null}
                        {home.start_button}
                        <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                      </span>
                    </button>
                  );
                return (
                  <button
                    key={t.id}
                    onClick={() => void create(t.id)}
                    disabled={busy !== null || !t.has_dataset}
                    className={cx(
                      "group relative flex min-h-[176px] flex-col overflow-hidden rounded-2xl border bg-card p-5 text-left transition-[border-color,background-color,transform] duration-200",
                      "hover:border-border-strong hover:bg-[#161618] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60",
                      hero ? "border-border-strong sm:col-span-2" : "border-border",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cx("pointer-events-none absolute -top-16 -right-16 rounded-full opacity-[0.10] blur-2xl transition-opacity duration-300 group-hover:opacity-20", hero ? "h-56 w-56 opacity-[0.16]" : "h-40 w-40")}
                      style={{ background: "var(--brand-gradient)" }}
                    />
                    <div className="relative flex items-center gap-2.5">
                      <TemplateGlyph id={t.id} />
                      <h3 className="text-[15px] font-semibold tracking-[-0.01em]">{t.title}</h3>
                    </div>
                    <p className={cx("relative mt-3 flex-1 leading-snug", hero ? "text-[22px] font-semibold tracking-[-0.02em] sm:text-[24px]" : "text-[16px] font-medium")}>{t.line}</p>
                    {hero ? <p className="num relative mt-2 text-[13px] leading-snug text-subtle">{fraudResult ?? home.sampleStat}</p> : null}
                    <div className="relative mt-4 flex items-end justify-between gap-3 text-[12px]">
                      <span className="leading-snug text-muted">{t.footer}</span>
                      <span className="flex shrink-0 items-center gap-1 font-medium">
                        {busy === t.id ? <Spinner className="h-3.5 w-3.5" /> : null}
                        {home.start_button}
                        <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </button>
                );
              })}
        </div>
      </section>

      <section className="mt-12">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>{home.yourProjects}</SectionTitle>
          {projects && projects.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
              <Chip>{home.chips.live(live)}</Chip>
              <Chip>{home.chips.improving(improving)}</Chip>
              <Chip title={tooltips.readyToLaunch}>
                <span className="bg-brand h-1.5 w-1.5 rounded-full" />
                {home.chips.ready(ready)}
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
            <Empty>{home.noProjects}</Empty>
          </div>
        ) : (
          <Card pad={false} className="mt-3 overflow-hidden">
            <div className="hidden grid-cols-[minmax(0,1.6fr)_minmax(0,0.9fr)_minmax(0,1.6fr)_minmax(0,0.9fr)_minmax(0,0.6fr)_56px] gap-5 border-b border-border px-5 py-2.5 text-[12px] font-medium text-muted md:grid">
              <span>{home.columns.name}</span>
              <span>{home.columns.stage}</span>
              <span>{home.columns.result}</span>
              <span>{home.columns.model}</span>
              <span>{home.columns.updated}</span>
              <span />
            </div>
            <ul className="divide-y divide-border">
              {projects.map((p) => {
                const confirming = confirmId === p.id;
                const stageLabel = p.apex_validation === "pass" ? home.readyToLaunch : STEPS[stageIndex(p.stage)]?.label;
                return (
                  <li key={p.id} className="group relative">
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-4 py-3.5 transition-colors hover:bg-[#161618] md:grid-cols-[minmax(0,1.6fr)_minmax(0,0.9fr)_minmax(0,1.6fr)_minmax(0,0.9fr)_minmax(0,0.6fr)_56px] md:gap-x-5 md:px-5">
                      <Link href={`/projects/${p.id}`} className="flex min-w-0 items-center gap-3 after:absolute after:inset-0 after:content-['']">
                        <TemplateGlyph id={p.template} small />
                        <span className="min-w-0">
                          <span className="block text-[14px] font-medium leading-snug">{p.name}</span>
                          <span className="block text-[12px] text-muted">
                            {p.profile?.n_rows ? `${fmtCompact(p.profile.n_rows)} rows` : ""}
                            <span className="md:hidden"> · {stageLabel}</span>
                          </span>
                        </span>
                      </Link>
                      <div className="hidden text-[13px] text-subtle md:block" title={p.apex_validation === "pass" ? tooltips.readyToLaunch : undefined}>
                        {stageLabel}
                      </div>
                      <div className="col-span-2 row-start-2 min-w-0 text-[13px] leading-snug md:col-span-1 md:row-start-auto">
                        {p.result_short ? <span className="num font-medium">{p.result_short}</span> : <span className="text-muted">{home.noResultYet}</span>}
                      </div>
                      <div className="hidden min-w-0 items-center gap-2 md:flex">
                        {p.active_model ? (
                          <>
                            <span className="num text-[13px] font-medium">{statusCopy.version(p.active_model.version)}</span>
                            <StatusPill status={p.model_status} />
                          </>
                        ) : (
                          <span className="text-[13px] text-muted">{statusCopy.none}</span>
                        )}
                      </div>
                      <div className="hidden text-[12px] text-muted md:block">{fmtAgo(p.updated_at ?? p.created_at)}</div>
                      <div className="relative z-10 flex items-center justify-end gap-1">
                        {confirming ? (
                          <>
                            <Button size="sm" variant="danger" busy={busy === p.id} onClick={() => void remove(p)}>
                              {home.delete}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)} disabled={busy === p.id}>
                              {home.keep}
                            </Button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => setConfirmId(p.id)}
                              disabled={busy !== null}
                              className="flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-card-3 hover:text-danger md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                              aria-label={home.deleteProject(p.name)}
                              title={home.deleteTitle}
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

function Chip({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <span title={title} className="inline-flex h-6 items-center gap-1.5 rounded-md bg-card-2 px-2 text-[12px] text-subtle">
      {children}
    </span>
  );
}

function TemplateGlyph({ id, small }: { id: string; small?: boolean }) {
  const Icon = TEMPLATE_ICON[id] ?? FileUp;
  return <Icon className={cx("icon-brand shrink-0", small ? "h-5 w-5" : "h-6 w-6")} strokeWidth={1.75} aria-hidden />;
}

