"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProject } from "@/components/ProjectShell";
import { Loading } from "@/components/ui";
import { stepHref } from "@/lib/stages";

/** Older links: this screen became the overview tab. */
export default function Moved() {
  const { project } = useProject();
  const router = useRouter();
  useEffect(() => {
    router.replace(stepHref(project.id, "overview"));
  }, [project.id, router]);
  return <Loading label="Opening" />;
}
