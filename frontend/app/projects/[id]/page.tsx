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
    router.replace(stepHref(project.id, STAGES[reachedIndex(project)]));
  }, [project, router]);
  return <Loading label="Opening the current step" />;
}
