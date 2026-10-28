"use client";

import { useEffect, useState } from "react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { LeakCards, MaturityCard, ProtectionDetails } from "@/components/ProtectionReport";
import { Alert, PageHeader, Skeleton } from "@/components/ui";
import { api, errorText, type ProtectReport } from "@/lib/api";
import { data as copy } from "@/lib/copy";

export default function DataPage() {
  const { project } = useProject();
  const [report, setReport] = useState<ProtectReport | null>(project.protect ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (project.protect) {
      setReport(project.protect);
      return;
    }
    api
      .protectReport(project.id)
      .then(setReport)
      .catch((e) => setError(errorText(e)));
  }, [project.id, project.protect]);

  return (
    <div className="space-y-5">
      <PageHeader title={copy.title}>{copy.sub}</PageHeader>
      {error ? <Alert>{error}</Alert> : null}
      {!report && !error ? <Skeleton className="h-64 w-full rounded-2xl" /> : null}
      {report ? (
        <>
          {report.maturity ? <MaturityCard m={report.maturity} trainStart={report.parts.find((x) => x.name === "train")?.time_min} /> : null}
          <LeakCards report={report} />
          <ProtectionDetails report={report} projectId={project.id} version={project.active_model?.version ?? null} />
        </>
      ) : null}
      <ActionBar>
        <NextLink stage="launch" label={copy.next} />
      </ActionBar>
    </div>
  );
}
