"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, errorText, type ProjectOut, type TemplateId, type TemplateOut } from "@/lib/api";
import { STEPS, TEMPLATE_LABEL, stageIndex, stepHref } from "@/lib/stages";
import { fmtInt } from "@/lib/format";
import { Alert, Button, Card, Empty, Loading } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateOut[] | null>(null);
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

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
      router.push(stepHref(p.id, template === "custom" ? "upload" : "intake"));
    } catch (e) {
      setError(errorText(e));
      setBusy(null);
    }
  }

  async function remove(p: ProjectOut) {
    if (!window.confirm(`Delete "${p.name}" and its files?`)) return;
    setBusy(p.id);
    try {
      await api.deleteProject(p.id);
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-3">
          <span className="text-lg font-semibold tracking-tight">Brief</span>
          <span className="text-sm text-muted">From spreadsheet to proven model</span>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-10">
        <h1 className="text-3xl font-semibold tracking-tight">Start a new problem</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Describe a prediction problem in plain English and upload a CSV. Brief turns it into fair rules, protects the data,
          proves it with local solvers, and hands back a model you can use.
        </p>

        {error ? <Alert className="mt-6">{error}</Alert> : null}

        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted">Templates</h2>
          {!templates ? (
            <Loading label="Loading templates" />
          ) : (
            <div className="mt-3 grid gap-4 md:grid-cols-3">
              {templates.map((t) => (
                <Card key={t.id} className="flex flex-col">
                  <h3 className="text-lg font-semibold">{t.name}</h3>
                  <p className="mt-1 flex-1 text-sm text-muted">{t.description}</p>
                  <p className="mt-3 text-xs text-muted">{t.has_dataset ? "Sample dataset included" : "Dataset not fetched yet"}</p>
                  <Button className="mt-4" busy={busy === t.id} disabled={busy !== null || !t.has_dataset} onClick={() => void create(t.id)}>
                    Use {TEMPLATE_LABEL[t.id] || t.name}
                  </Button>
                </Card>
              ))}
              <Card className="flex flex-col border-dashed">
                <h3 className="text-lg font-semibold">Start blank</h3>
                <p className="mt-1 flex-1 text-sm text-muted">Upload your own CSV with one target column.</p>
                <p className="mt-3 text-xs text-muted">Max 200 MB</p>
                <Button variant="secondary" className="mt-4" busy={busy === "custom"} disabled={busy !== null} onClick={() => void create("custom")}>
                  Upload a CSV
                </Button>
              </Card>
            </div>
          )}
        </section>

        <section className="mt-12">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted">Your projects</h2>
          {!projects ? (
            <Loading label="Loading projects" />
          ) : projects.length === 0 ? (
            <Empty>No projects yet. Pick a template above.</Empty>
          ) : (
            <div className="mt-3 overflow-hidden rounded-2xl border border-border bg-card">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted">
                  <tr>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Template</th>
                    <th className="px-4 py-2 font-medium">Rows</th>
                    <th className="px-4 py-2 font-medium">Step</th>
                    <th className="px-4 py-2 font-medium">Winner</th>
                    <th className="px-4 py-2 font-medium">Created</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr key={p.id} className="border-t border-border">
                      <td className="px-4 py-2">
                        <Link href={`/projects/${p.id}`} className="font-medium hover:underline">
                          {p.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2">{TEMPLATE_LABEL[p.template] || p.template}</td>
                      <td className="px-4 py-2 tabular-nums">{fmtInt(p.profile?.n_rows)}</td>
                      <td className="px-4 py-2">{STEPS[stageIndex(p.stage)]?.label}</td>
                      <td className="px-4 py-2">{p.winner_solver ? p.winner_solver.replace(/_/g, " ") : ""}</td>
                      <td className="px-4 py-2 text-muted">{new Date(p.created_at).toLocaleString()}</td>
                      <td className="px-4 py-2 text-right">
                        <Button size="sm" variant="ghost" busy={busy === p.id} disabled={busy !== null} onClick={() => void remove(p)}>
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
