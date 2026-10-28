"use client";

import { useRef, useState } from "react";
import { Clock, EyeOff, FileSpreadsheet, Upload } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, DataTable, Meter, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api, errorText, type DataProfile } from "@/lib/api";
import { fmtCompact, fmtInt, fmtPct } from "@/lib/format";
import { upload as copy } from "@/lib/copy";

const MAX_MB = 200;

const TYPE_COLOR: Record<string, string> = {
  int: "var(--c-indigo)",
  float: "var(--c-violet)",
  object: "var(--c-peach)",
  str: "var(--c-peach)",
  bool: "var(--c-orchid)",
  datetime: "var(--c-pink)",
};

function typeColor(dtype: string): string {
  const key = Object.keys(TYPE_COLOR).find((k) => dtype.toLowerCase().includes(k));
  return key ? TYPE_COLOR[key] : "var(--c-orchid)";
}

export default function UploadPage() {
  const { project, refresh } = useProject();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const profile: DataProfile | null | undefined = project.profile;
  const isTemplate = project.template !== "custom";

  async function upload(file: File) {
    setError(null);
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(copy.tooBig(Number((file.size / 1024 / 1024).toFixed(0)), MAX_MB));
      return;
    }
    setBusy(true);
    try {
      await api.uploadData(project.id, file);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const target = profile?.target_candidates?.[0];
  const previewCols = profile?.columns.map((c) => c.name) ?? [];
  const picker = (
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
  );

  return (
    <div className="space-y-5">
      {picker}
      <PageHeader
        title={copy.title}
        actions={
          profile ? (
            <Button variant="secondary" busy={busy} onClick={() => inputRef.current?.click()}>
              <Upload className="h-4 w-4" />
              {isTemplate ? copy.useOwn : copy.replace}
            </Button>
          ) : null
        }
      >
        {profile ? (isTemplate ? copy.templateLoaded : copy.ownLoaded) : copy.empty}
      </PageHeader>

      {error ? <Alert>{error}</Alert> : null}

      {!profile ? (
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
          {busy ? <Spinner className="h-8 w-8 text-pink" /> : <FileSpreadsheet className="icon-brand h-9 w-9" strokeWidth={1.5} aria-hidden />}
          <div>
            <p className="text-[15px] font-medium">{busy ? copy.reading : copy.drop}</p>
            <p className="mt-1 text-[13px] text-muted">{copy.max(MAX_MB)}</p>
          </div>
          <Button size="lg" busy={busy} onClick={() => inputRef.current?.click()}>
            <Upload className="h-4 w-4" />
            {copy.choose}
          </Button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={copy.rows} value={fmtInt(profile.n_rows)} hint={isTemplate ? copy.sample : copy.asUploaded} />
            <Stat label={copy.columns} value={fmtInt(profile.n_cols)} hint={copy.lookLikeTime(profile.columns.filter((c) => c.looks_like_time).length)} />
            <Stat
              label={copy.outcomeRate}
              value={profile.positive_rate != null ? fmtPct(profile.positive_rate, 2) : "n/a"}
              hint={profile.positive_rate != null ? copy.oneIn(fmtInt(Math.round(1 / Math.max(profile.positive_rate, 1e-9)))) : copy.confirmedNext}
            />
            <Stat label={copy.likelyOutcome} value={<span className="num font-sans text-[16px] font-medium sm:text-[18px]">{target || copy.notSure}</span>} hint={copy.confirmTogether} />
          </div>

          <Card
            title={copy.first10}
            subtitle={copy.first10Sub}
            actions={<Badge>{fmtCompact(profile.n_rows)} rows</Badge>}
          >
            <DataTable columns={previewCols} rows={profile.preview_rows.slice(0, 10)} highlight={target ? [target] : undefined} className="max-h-[420px]" />
          </Card>

          <Card title={copy.health} subtitle={copy.healthSub}>
            <ul className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {profile.columns.map((c) => {
                const filled = 1 - c.null_pct / 100;
                return (
                  <li key={c.name} className="flex flex-col gap-2 border-b border-border/70 py-3 last:border-b-0 md:[&:nth-last-child(2)]:border-b-0">
                    <div className="flex items-center justify-between gap-3">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: typeColor(c.dtype) }} />
                        <span className="num truncate text-[13px] font-medium">{c.name}</span>
                        {c.name === target ? <Badge tone="accent">outcome?</Badge> : null}
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5">
                        {c.looks_like_time ? (
                          <span title={copy.looksLikeTime}>
                            <Clock className="icon-brand h-3.5 w-3.5" />
                          </span>
                        ) : null}
                        {c.pii_masked ? (
                          <span title={copy.piiMasked}>
                            <EyeOff className="icon-brand h-3.5 w-3.5" />
                          </span>
                        ) : null}
                        <span className="text-[12px] text-muted">{c.dtype}</span>
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Meter value={filled} color={filled > 0.98 ? "brand" : filled > 0.8 ? "var(--c-peach)" : "var(--danger)"} className="h-1.5 min-w-0 flex-1" />
                      <span className="num shrink-0 text-right text-[11px] whitespace-nowrap text-muted">
                        {fmtPct(filled, 0)} · {fmtCompact(c.n_unique)} {copy.distinct}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        </>
      )}

      <ActionBar hint={profile ? copy.hintNext : copy.hintUpload}>
        <NextLink stage="intake" label={copy.next} disabled={!project.has_data} />
      </ActionBar>
    </div>
  );
}
