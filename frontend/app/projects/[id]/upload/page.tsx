"use client";

import { useRef, useState } from "react";
import { Clock, EyeOff, FileSpreadsheet, Upload } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, DataTable, Meter, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api, errorText, type DataProfile } from "@/lib/api";
import { fmtCompact, fmtInt, fmtPct } from "@/lib/format";

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
      setError(`That file is ${(file.size / 1024 / 1024).toFixed(0)} MB. The limit is ${MAX_MB} MB.`);
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
        title="Your data"
        actions={
          profile ? (
            <Button variant="secondary" busy={busy} onClick={() => inputRef.current?.click()}>
              <Upload className="h-4 w-4" />
              {isTemplate ? "Use my own CSV" : "Replace CSV"}
            </Button>
          ) : null
        }
      >
        {profile
          ? isTemplate
            ? "The sample dataset is loaded. Check it looks right, or swap in your own CSV with the same idea: one row per case, one outcome column."
            : "Here is what Brief read from your file. Nothing has been changed yet."
          : "Upload a CSV with one row per case and one column that records the outcome."}
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
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border-strong bg-card-2">
            {busy ? <Spinner className="h-6 w-6" /> : <FileSpreadsheet className="h-6 w-6 text-subtle" />}
          </span>
          <div>
            <p className="text-[15px] font-medium">{busy ? "Reading the file" : "Drop a CSV here"}</p>
            <p className="mt-1 text-[13px] text-muted">Max {MAX_MB} MB. The file stays on this machine.</p>
          </div>
          <Button size="lg" busy={busy} onClick={() => inputRef.current?.click()}>
            <Upload className="h-4 w-4" />
            Choose a CSV
          </Button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Rows" value={fmtInt(profile.n_rows)} hint={isTemplate ? "Sample dataset" : "As uploaded"} />
            <Stat label="Columns" value={fmtInt(profile.n_cols)} hint={`${profile.columns.filter((c) => c.looks_like_time).length} look like time`} />
            <Stat
              label="Outcome rate"
              value={profile.positive_rate != null ? fmtPct(profile.positive_rate, 2) : "n/a"}
              hint={profile.positive_rate != null ? `About 1 in ${fmtInt(Math.round(1 / Math.max(profile.positive_rate, 1e-9)))} rows` : "Confirmed in the next step"}
            />
            <Stat
              label="Likely outcome column"
              value={<span className="text-[16px] sm:text-[18px]">{target || "Not sure yet"}</span>}
              hint="We confirm this together next"
            />
          </div>

          <Card
            title="First 10 rows"
            subtitle="A preview of the data exactly as loaded."
            actions={<Badge>{fmtCompact(profile.n_rows)} rows</Badge>}
          >
            <DataTable columns={previewCols} rows={profile.preview_rows.slice(0, 10)} highlight={target ? [target] : undefined} className="max-h-[420px]" />
          </Card>

          <Card title="Column health" subtitle="How complete each column is, its type, and anything Brief noticed.">
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
                          <span title="Looks like a time" className="text-pink">
                            <Clock className="h-3.5 w-3.5" />
                          </span>
                        ) : null}
                        {c.pii_masked ? (
                          <span title="Personal data, masked" className="text-warn">
                            <EyeOff className="h-3.5 w-3.5" />
                          </span>
                        ) : null}
                        <span className="text-[12px] text-muted">{c.dtype}</span>
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Meter value={filled} color={filled > 0.98 ? "var(--brand-gradient-x)" : filled > 0.8 ? "var(--c-peach)" : "var(--danger)"} className="h-1.5 min-w-0 flex-1" />
                      <span className="num shrink-0 text-right text-[11px] whitespace-nowrap text-muted">
                        {fmtPct(filled, 0)} · {fmtCompact(c.n_unique)} distinct
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        </>
      )}

      <ActionBar hint={profile ? "Next, tell Brief in plain words what you want to predict." : "Upload a CSV to continue."}>
        <NextLink stage="intake" label="Describe the goal" disabled={!project.has_data} />
      </ActionBar>
    </div>
  );
}
