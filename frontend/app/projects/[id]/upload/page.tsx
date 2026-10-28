"use client";

import { useRef, useState } from "react";
import { NextStep, useProject } from "@/components/ProjectShell";
import { Alert, Button, Card, DataTable, Stat } from "@/components/ui";
import { api, errorText, type DataProfile } from "@/lib/api";
import { fmtInt, fmtPct } from "@/lib/format";

const MAX_MB = 200;

export default function UploadPage() {
  const { project, refresh } = useProject();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const profile: DataProfile | null | undefined = project.profile;

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

  const previewCols = profile?.columns.map((c) => c.name) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New problem</h1>
        <p className="mt-1 text-muted">
          {project.template === "custom"
            ? "Upload a CSV with one row per case and one column that records the outcome."
            : "The template dataset is loaded. Upload your own CSV to replace it, or continue."}
        </p>
      </div>

      <Card>
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
          className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${dragging ? "border-accent bg-accent-soft" : "border-border"}`}
        >
          <p className="text-sm">Drop a CSV here, or</p>
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
          <Button variant="secondary" busy={busy} onClick={() => inputRef.current?.click()}>
            {busy ? "Reading the file" : "Choose a CSV"}
          </Button>
          <p className="text-xs text-muted">Max {MAX_MB} MB. The file stays on this machine.</p>
        </div>
        {error ? <Alert className="mt-4">{error}</Alert> : null}
      </Card>

      {profile ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Rows" value={fmtInt(profile.n_rows)} />
            <Stat label="Columns" value={fmtInt(profile.n_cols)} />
            <Stat
              label="Likely outcome column"
              value={<span className="text-lg">{profile.target_candidates?.[0] || "Not sure yet"}</span>}
              hint={profile.positive_rate != null ? `${fmtPct(profile.positive_rate, 2)} of rows are positive` : "We will confirm this in the next step"}
            />
          </div>

          <Card title="First 10 rows" subtitle="A preview of the data as uploaded. Nothing has been changed yet.">
            <DataTable columns={previewCols} rows={profile.preview_rows.slice(0, 10)} />
          </Card>

          <Card title="Columns" subtitle="Type, missing values and how many distinct values each column has.">
            <div className="overflow-auto rounded-xl border border-border">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-stone-50 text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Column</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Missing</th>
                    <th className="px-3 py-2 font-medium">Distinct</th>
                    <th className="px-3 py-2 font-medium">Range</th>
                    <th className="px-3 py-2 font-medium">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.columns.map((c) => (
                    <tr key={c.name} className="border-t border-border">
                      <td className="px-3 py-1.5 font-medium">{c.name}</td>
                      <td className="px-3 py-1.5 text-muted">{c.dtype}</td>
                      <td className="px-3 py-1.5 tabular-nums">{fmtPct(c.null_pct / 100, 1)}</td>
                      <td className="px-3 py-1.5 tabular-nums">{fmtInt(c.n_unique)}</td>
                      <td className="px-3 py-1.5 tabular-nums text-muted">
                        {c.min != null && c.max != null ? `${String(c.min)} to ${String(c.max)}` : ""}
                      </td>
                      <td className="px-3 py-1.5 text-muted">
                        {[c.looks_like_time ? "looks like a time" : "", c.pii_masked ? "personal data, masked" : ""].filter(Boolean).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}

      <NextStep stage="intake" />
    </div>
  );
}
