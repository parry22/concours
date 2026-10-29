"use client";

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Card, PageHeader, Skeleton } from "@/components/ui";
import { api, errorText, type TrustOut } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { trust as copy } from "@/lib/copy";

/** One page that answers the buyer's security questions from the project's own facts. */
export default function TrustPage() {
  const { project } = useProject();
  const [t, setT] = useState<TrustOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.trust(project.id).then(setT).catch((e) => setError(errorText(e)));
  }, [project.id, project.protect]);

  return (
    <div className="space-y-5">
      <PageHeader title={copy.title}>{copy.sub}</PageHeader>
      {error ? <Alert>{error}</Alert> : null}
      {!t && !error ? <Skeleton className="h-64 w-full rounded-2xl" /> : null}
      {t ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={copy.leaves} actions={<Lock className="icon-brand h-4 w-4" />}>
            <ul className="space-y-2.5 text-[13px] leading-relaxed">
              <li>{copy.leavesNone}</li>
              <li>{t.package_built ? copy.leavesPackage : copy.leavesNoPackage}</li>
              <li>{copy.leavesHoldout(t.holdout ? fmtInt(t.holdout.rows ?? 0) : "0")}</li>
              <li>
                <Badge tone={t.apex.live ? "accent" : "neutral"} dot={t.apex.live}>
                  {copy.apexModes[t.apex.mode]}
                </Badge>{" "}
                <span className="text-muted">{copy.apexDetail[t.apex.mode]}</span>
              </li>
            </ul>
          </Card>
          <Card title={copy.who}>
            <ul className="space-y-2.5 text-[13px] leading-relaxed">
              <li>{copy.whoYou}</li>
              <li>{copy.whoSolvers(t.kept_columns.join(", ") || "none yet", t.hashed_columns.join(", ") || "none")}</li>
              <li>{copy.whoReferee}</li>
              <li>{copy.whoAnalysts(t.analyst_labels)}</li>
            </ul>
          </Card>
          <Card title={copy.held}>
            <ul className="space-y-2.5 text-[13px] leading-relaxed">
              <li>{copy.heldEncrypted(t.encryption_key_location)}</li>
              <li>{copy.heldRaw}</li>
              <li>{copy.heldCards(t.card_columns_dropped)}</li>
              <li>{copy.heldLeaks(t.leak_columns_dropped)}</li>
              <li>{copy.heldRetention}</li>
            </ul>
          </Card>
          <Card title={copy.what}>
            <ul className="space-y-2.5 text-[13px] leading-relaxed">
              <li>{copy.whatRows(fmtInt(t.rows ?? 0), t.columns_uploaded ?? 0, t.kept_columns.length)}</li>
              <li>{copy.whatLate(t.label_delay_days ?? 30)}</li>
              <li>{copy.whatBatch}</li>
              <li>{copy.whatNoNumbers}</li>
            </ul>
          </Card>
        </div>
      ) : null}
      <ActionBar>
        <NextLink stage="launch" label={copy.next} />
      </ActionBar>
    </div>
  );
}
