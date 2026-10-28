"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProject } from "@/components/ProjectShell";
import { Loading } from "@/components/ui";
import { STAGES, reachedIndex, stepHref } from "@/lib/stages";

export default function ProjectIndex() {
  const { project } = useProject();
  const router = useRouter();
  useEffect(() => {
    // Open the step that matters now: a model that exists lands on Your model; an open contest on Improve.
    const idx = Math.min(reachedIndex(project), STAGES.indexOf(project.stage) >= STAGES.indexOf("model") ? STAGES.indexOf(project.stage) : reachedIndex(project));
    router.replace(stepHref(project.id, STAGES[idx]));
  }, [project, router]);
  return <Loading label="Opening the current step" />;
}
