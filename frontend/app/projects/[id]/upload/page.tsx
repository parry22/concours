"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Select } from "@/components/Select";
import { Alert, Badge, Button, Card, DataTable, PageHeader, Skeleton, Spinner, Stat, cx } from "@/components/ui";
import { api, errorText, type SchemaOut } from "@/lib/api";
import { fmtInt, fmtPct } from "@/lib/format";
import { mapping as copy } from "@/lib/copy";
import { stepHref } from "@/lib/stages";

const MAX_MB = 200;

export default function TransactionsPage() {
  const { project, refresh } = useProject();
  const router = useRouter();
  const [schema, setSchema] = useState<SchemaOut | null | undefined>(undefined);
  const [choice, setChoice] = useState<Record<string, string | null>>({});
  const [busy, setBusy] = useState<"upload" | "confirm" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasFile = Boolean(project.profile);

  const load = useCallback(async () => {
    if (!hasFile) {
      setSchema(null);
      return;
    }
    try {
      const s = await api.schema(project.id);
      setSchema(s);
      setChoice(Object.fromEntries(s.fields.map((f) => [f.name, f.column ?? null])));
    } catch (e) {
      setError(errorText(e));
      setSchema(null);
    }
  }, [project.id, hasFile]);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(file: File) {
    setError(null);
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(copy.tooBig(Number((file.size / 1024 / 1024).toFixed(0)), MAX_MB));
      return;
    }
    setBusy("upload");
    try {
      await api.uploadData(project.id, file);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function confirm() {
    setBusy("confirm");
    setError(null);
    try {
      const p = await api.putSchema(project.id, choice);
      await refresh();
      router.push(stepHref(p.id, "intake"));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const fields = schema?.fields ?? [];
  const used = new Set(Object.values(choice).filter(Boolean));
  const missing = fields.filter((f) => f.required && !choice[f.name]);
  const requiredCount = fields.filter((f) => f.required).length;
  const extra = schema ? schema.columns.filter((c) => !used.has(c)).length : 0;
  const prof = project.profile;

  return (
    <div className="space-y-5">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void upload(f);
          e.target.value = "";
        }}
      />
      <PageHeader
        title={copy.title}
        actions={
          hasFile ? (
            <Button variant="secondary" busy={busy === "upload"} onClick={() => inputRef.current?.click()}>
              <Upload className="h-4 w-4" />
              {copy.replace}
            </Button>
          ) : null
        }
      >
        {project.source === "sample" && hasFile ? copy.sampleSub : copy.sub}
      </PageHeader>

      {error ? <Alert>{error}</Alert> : null}

      {!hasFile ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void upload(f);
          }}
          className={cx(
            "relative flex flex-col items-center justify-center gap-4 overflow-hidden rounded-2xl border border-dashed px-6 py-14 text-center transition-colors sm:py-20",
            dragging ? "border-accent bg-accent-soft" : "border-border-strong bg-card",
          )}
        >
          {busy === "upload" ? <Spinner className="h-8 w-8 text-pink" /> : <FileSpreadsheet className="icon-brand h-9 w-9" strokeWidth={1.5} aria-hidden />}
          <div>
            <p className="text-[15px] font-medium">{busy === "upload" ? copy.reading : copy.drop}</p>
            <p className="mt-1 text-[13px] text-muted">{copy.max(MAX_MB)}</p>
          </div>
          <Button size="lg" busy={busy === "upload"} onClick={() => inputRef.current?.click()}>
            <Upload className="h-4 w-4" />
            {copy.choose}
          </Button>
        </div>
      ) : (
        <>
          <div className={cx("grid gap-3", schema?.time_range ? "grid-cols-3" : "grid-cols-2")}>
            <Stat label={copy.rows} value={fmtInt(prof?.n_rows ?? 0)} />
            <Stat label={copy.fraudRate} value={prof?.positive_rate != null ? fmtPct(prof.positive_rate, 2) : "n/a"} />
            {schema?.time_range ? <Stat label={copy.days} value={fmtInt(Number(schema.time_range.days))} hint={copy.range(String(schema.time_range.start), String(schema.time_range.end))} /> : null}
          </div>

          <Card
            title={copy.card}
            subtitle={schema ? copy.extra(extra) : undefined}
            actions={
              project.schema_confirmed ? (
                <Badge tone="ok">{copy.confirmed}</Badge>
              ) : schema ? (
                <Badge tone={missing.length ? "neutral" : "ok"} className="num">
                  {copy.matched(requiredCount - missing.length, requiredCount)}
                </Badge>
              ) : null
            }
          >
            {schema === undefined ? (
              <div className="space-y-2">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-11" />
                ))}
              </div>
            ) : (
              <div className="space-y-6">
                {[
                  { title: copy.required, list: fields.filter((f) => f.required) },
                  { title: copy.optional, list: fields.filter((f) => !f.required) },
                ].map((group) => (
                  <section key={group.title}>
                    <h3 className="mb-1 text-[11px] font-medium tracking-[0.06em] text-muted uppercase">{group.title}</h3>
                    <ul className="divide-y divide-border">
                      {group.list.map((f) => {
                        const meta = copy.fields[f.name] ?? { label: f.name, hint: "" };
                        const val = choice[f.name] ?? null;
                        return (
                          <li key={f.name} className="grid gap-2 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:items-center md:gap-6">
                            <label htmlFor={`map-${f.name}`} className="min-w-0">
                              <span className="block text-[13px] font-medium">{meta.label}</span>
                              <span className="block text-[12px] leading-snug text-muted">{meta.hint}</span>
                            </label>
                            <Select
                              id={`map-${f.name}`}
                              value={val}
                              placeholder={copy.pick}
                              emptyOption={f.required ? undefined : copy.notMapped}
                              invalid={f.required && !val}
                              onChange={(v) => setChoice((c) => ({ ...c, [f.name]: v }))}
                              options={(schema?.columns ?? []).map((c) => {
                                const owner = Object.entries(choice).find(([k, v]) => v === c && k !== f.name)?.[0];
                                return {
                                  value: c,
                                  label: c,
                                  detail: sampleOf(schema?.preview ?? [], c),
                                  tag: c === f.suggested ? copy.suggested : undefined,
                                  disabledReason: owner ? copy.usedFor(copy.fields[owner]?.label ?? owner) : undefined,
                                };
                              })}
                            />
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))}
              </div>
            )}
          </Card>

          {schema?.notes?.length ? (
            <ul className="space-y-1 text-[12px] leading-relaxed text-muted">
              {schema.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}

          {schema?.preview?.length ? (
            <Card title={copy.preview}>
              <DataTable columns={schema.columns} rows={schema.preview} highlight={Object.values(choice).filter(Boolean) as string[]} className="max-h-[320px]" />
            </Card>
          ) : null}
        </>
      )}

      <ActionBar hint={project.schema_confirmed ? copy.hintDone : copy.hintTodo}>
        {hasFile && schema ? (
          <Button size="lg" busy={busy === "confirm"} disabled={missing.length > 0} onClick={() => void confirm()}>
            {busy === "confirm" ? copy.confirming : copy.confirm}
          </Button>
        ) : (
          <NextLink stage="intake" label={copy.next} disabled={!project.schema_confirmed} />
        )}
      </ActionBar>
    </div>
  );
}

/** A short sample of a column for the picker: the first non-empty value in the preview rows. */
function sampleOf(rows: Record<string, unknown>[], col: string): string | undefined {
  const v = rows.map((r) => r[col]).find((x) => x !== null && x !== undefined && x !== "");
  if (v === undefined) return undefined;
  const s = String(v);
  return s.length > 22 ? `${s.slice(0, 21)}…` : s;
}
