"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Clock, Download, ListOrdered, Upload } from "lucide-react";
import { ActionBar, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Card, Empty, LinkButton, Meter, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api, errorText, type ListOut } from "@/lib/api";
import { stepHref } from "@/lib/stages";
import { fmtCell, fmtDateTime, fmtInt } from "@/lib/format";
import { lists as copy } from "@/lib/copy";

export default function ListsPage() {
  const { project, refresh } = useProject();
  const [all, setAll] = useState<ListOut[] | null>(null);
  const [current, setCurrent] = useState<ListOut | null>(null);
  const [busy, setBusy] = useState<"upload" | "sample" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingRefresh, setSavingRefresh] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .lists(project.id)
      .then((l) => {
        setAll(l);
        setCurrent(l[0] ?? null);
      })
      .catch((e) => setError(errorText(e)));
  }, [project.id]);

  async function build(file?: File) {
    setBusy(file ? "upload" : "sample");
    setError(null);
    try {
      const l = await api.createList(project.id, file, { sample: !file });
      setCurrent(l);
      setAll((a) => [l, ...(a ?? []).filter((x) => x.id !== l.id)]);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function toggleRefresh() {
    setSavingRefresh(true);
    try {
      await api.putSettings(project.id, { refresh_daily: !project.refresh_daily });
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSavingRefresh(false);
    }
  }

  const framing = { label: current?.row_label ?? "row", action: current?.action_label ?? "Act" };
  const otherCols = current ? current.columns.filter((c) => !["rank", "score", "action"].includes(c)) : [];
  const rows = current?.preview ?? [];

  return (
    <div className="space-y-5">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void build(f);
          e.target.value = "";
        }}
      />
      <PageHeader
        title={copy.title(project.list_name)}
        actions={
          project.active_model ? (
            <Badge tone="accent" className="num">
              {copy.model} v{project.active_model.version}
            </Badge>
          ) : null
        }
      >
        {copy.sub(framing.label, framing.action)}
      </PageHeader>

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          onClick={() => void build()}
          disabled={busy !== null || !project.active_model}
          className="group relative flex items-start gap-4 overflow-hidden rounded-2xl border border-border-strong bg-card p-4 text-left transition-colors hover:bg-[#161618] disabled:cursor-not-allowed disabled:opacity-60 sm:p-5"
        >
          <span aria-hidden className="pointer-events-none absolute -top-20 -right-20 h-44 w-44 rounded-full opacity-[0.12] blur-2xl" style={{ background: "var(--brand-gradient)" }} />
          <span className="relative mt-0.5 shrink-0">{busy === "sample" ? <Spinner className="h-5 w-5 text-pink" /> : <ListOrdered className="icon-brand h-5 w-5" strokeWidth={1.75} aria-hidden />}</span>
          <span className="relative min-w-0">
            <span className="block text-[14px] font-medium">{copy.scoreSample}</span>
            <span className="mt-1 block text-[13px] leading-relaxed text-muted">{copy.scoreSampleSub}</span>
          </span>
        </button>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy !== null || !project.active_model}
          className="flex items-start gap-4 rounded-2xl border border-dashed border-border-strong bg-card p-4 text-left transition-colors hover:bg-[#161618] disabled:cursor-not-allowed disabled:opacity-60 sm:p-5"
        >
          <span className="mt-0.5 shrink-0">{busy === "upload" ? <Spinner className="h-5 w-5 text-pink" /> : <Upload className="icon-brand h-5 w-5" strokeWidth={1.75} aria-hidden />}</span>
          <span className="min-w-0">
            <span className="block text-[14px] font-medium">{copy.upload}</span>
            <span className="mt-1 block text-[13px] leading-relaxed text-muted">{copy.uploadSub}</span>
          </span>
        </button>
      </div>

      {error ? <Alert>{error}</Alert> : null}
      {busy ? (
        <p className="flex items-center gap-2 text-[13px] text-muted">
          <Spinner className="h-3.5 w-3.5" /> {copy.scoring}
        </p>
      ) : null}

      {current ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={copy.topN(current.top_n, current.row_label)} value={fmtInt(current.top_n)} accent />
            <Stat label={copy.rowsScored} value={fmtInt(current.rows_scored)} />
            <Stat label={copy.model} value={`v${current.model_version}`} />
            <Stat label={copy.built} value={<span className="text-[18px] sm:text-[20px]">{fmtDateTime(current.created_at)}</span>} />
          </div>

          <Card
            pad={false}
            title={current.name}
            subtitle={
              <span className="num">
                {copy.model} v{current.model_version} · {fmtDateTime(current.created_at)}
              </span>
            }
            actions={
              <LinkButton href={api.listDownloadUrl(project.id, current.id)} download variant="secondary" size="sm">
                <Download className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{copy.download}</span>
              </LinkButton>
            }
          >
            <div className="scroll-thin overflow-x-auto border-t border-border">
              <table className="num min-w-full border-separate border-spacing-0 text-left text-[12px]">
                <thead>
                  <tr className="text-muted">
                    <th className="sticky left-0 z-10 bg-card px-4 py-2.5 font-medium sm:px-5">{copy.rank}</th>
                    <th className="px-3 py-2.5 font-medium">{copy.action}</th>
                    <th className="px-3 py-2.5 font-medium">{copy.score}</th>
                    {otherCols.map((c) => (
                      <th key={c} className="px-3 py-2.5 font-medium whitespace-nowrap">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const s = Number(r.score);
                    const act = String(r.action ?? "");
                    return (
                      <tr key={i}>
                        <td className="sticky left-0 z-10 border-t border-border bg-card px-4 py-2.5 font-medium sm:px-5">{String(r.rank)}</td>
                        <td className="border-t border-border px-3 py-2.5">
                          <span className={cx("inline-flex h-[22px] items-center rounded-md px-2 text-[12px] font-medium", act ? "bg-pink/15 text-pink" : "bg-card-3 text-muted")}>{act || "–"}</span>
                        </td>
                        <td className="border-t border-border px-3 py-2.5">
                          <span className="flex items-center gap-2">
                            <Meter value={s} color={act ? "var(--c-pink)" : "#5a5a60"} className="h-1.5 w-14" />
                            <span className={cx(act ? "text-foreground" : "text-subtle")}>{s.toFixed(4)}</span>
                          </span>
                        </td>
                        {otherCols.map((c) => (
                          <td key={c} className="border-t border-border px-3 py-2.5 whitespace-nowrap text-subtle">
                            {fmtCell(r[c])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="border-t border-border px-4 py-3 text-[12px] text-muted sm:px-5">{copy.showing(rows.length, current.rows_scored)}</p>
          </Card>
        </>
      ) : all && !busy ? (
        <Empty>{copy.none}</Empty>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-5" title={copy.refresh} subtitle={copy.refreshOff}>
          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-[13px]">
              <Clock className="h-4 w-4 text-muted" />
              {copy.refresh}
            </span>
            <button
              role="switch"
              aria-checked={project.refresh_daily}
              disabled={savingRefresh}
              onClick={() => void toggleRefresh()}
              className={cx("relative h-6 w-11 shrink-0 rounded-full transition-colors", project.refresh_daily ? "bg-brand-x" : "bg-card-3")}
            >
              <span className={cx("absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-foreground shadow transition-transform", project.refresh_daily && "translate-x-5")} />
            </button>
          </label>
          {project.refresh_daily ? <p className="mt-3 text-[12px] text-pink">{copy.refreshHint}</p> : null}
        </Card>
        <Card className="lg:col-span-7" title={copy.earlier} pad={false}>
          {!all || all.length <= 1 ? (
            <p className="px-4 pb-4 text-[13px] text-muted sm:px-5">{copy.hint}</p>
          ) : (
            <ul className="divide-y divide-border border-t border-border">
              {all.map((l) => (
                <li key={l.id}>
                  <button
                    onClick={() => void api.list(project.id, l.id).then(setCurrent)}
                    className={cx("flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-[13px] transition-colors hover:bg-card-2 sm:px-5", current?.id === l.id && "bg-card-2")}
                  >
                    <span className="num">
                      {fmtDateTime(l.created_at)} · v{l.model_version}
                    </span>
                    <span className="num text-muted">
                      {copy.topN(l.top_n, l.row_label)} of {fmtInt(l.rows_scored)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <ActionBar
        hint={copy.hint}
        secondary={
          current ? (
            <LinkButton href={api.listDownloadUrl(project.id, current.id)} download variant="secondary" size="lg" className="sm:hidden">
              <Download className="h-4 w-4" />
              {copy.csv}
            </LinkButton>
          ) : null
        }
      >
        <Link href={stepHref(project.id, "model")} className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-border-strong bg-card-2 px-5 text-[14px] font-medium whitespace-nowrap text-foreground transition-colors hover:bg-card-3">
          {copy.back}
        </Link>
      </ActionBar>
    </div>
  );
}
