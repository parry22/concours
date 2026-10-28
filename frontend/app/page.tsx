"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CreditCard, Upload } from "lucide-react";
import { AppFrame } from "@/components/ProjectShell";
import { Alert, Button, Loading } from "@/components/ui";
import { api, errorText, type ProjectOut } from "@/lib/api";
import { home } from "@/lib/copy";
import { lastProject, rememberProject } from "@/lib/last-project";
import { stepHref } from "@/lib/stages";

/** Opens the project you had open last (else the newest). With no project yet, the two ways to start. */
export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"own" | "sample" | null>(null);

  useEffect(() => {
    api
      .projects()
      .then((list) => {
        if (list.length === 0) {
          setProjects(list);
          return;
        }
        const last = lastProject();
        const pick = list.find((p) => p.id === last) ?? [...list].sort((a, b) => (b.updated_at ?? b.created_at).localeCompare(a.updated_at ?? a.created_at))[0];
        router.replace(`/projects/${pick.id}`);
      })
      .catch((e) => setError(errorText(e)));
  }, [router]);

  async function create(sample: boolean) {
    setBusy(sample ? "sample" : "own");
    setError(null);
    try {
      const p = await api.createProject("fraud", undefined, sample);
      rememberProject(p.id);
      router.push(stepHref(p.id, "upload"));
    } catch (e) {
      setError(errorText(e));
      setBusy(null);
    }
  }

  return (
    <AppFrame>
      {error ? <Alert>{error}</Alert> : null}
      {projects === null && !error ? <Loading label={home.opening} /> : null}
      {projects?.length === 0 ? (
        <section className="mx-auto max-w-2xl pt-6 sm:pt-16">
          <h1 className="text-[30px] leading-[1.1] font-semibold tracking-[-0.025em] sm:text-[40px]">{home.h1}</h1>
          <p className="mt-3 text-[15px] leading-relaxed text-subtle sm:text-[16px]">{home.subhead}</p>
          <div className="mt-7 flex flex-col gap-2.5 sm:flex-row sm:items-center">
            <Button size="lg" busy={busy === "own"} disabled={busy !== null} onClick={() => void create(false)}>
              <Upload className="h-4 w-4" />
              {home.primary}
            </Button>
            <Button size="lg" variant="secondary" busy={busy === "sample"} disabled={busy !== null} onClick={() => void create(true)}>
              <CreditCard className="h-4 w-4" />
              {home.secondary}
            </Button>
          </div>
          <p className="mt-3 text-[12px] text-muted">{home.sampleNote}</p>
        </section>
      ) : null}
    </AppFrame>
  );
}
