"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProject } from "@/components/ProjectShell";
import { Loading } from "@/components/ui";
import { landing, stepHref } from "@/lib/stages";

export default function ProjectIndex() {
  const { project } = useProject();
  const router = useRouter();
  useEffect(() => {
    // A project with a model opens on its overview; one still in setup opens on its next setup step.
    router.replace(stepHref(project.id, landing(project)));
  }, [project, router]);
  return <Loading label="Opening the project" />;
}
