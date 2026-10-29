"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronRight, Download, File, Folder, Package, RotateCcw, ShieldCheck, X } from "lucide-react";
import { ActionBar, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, LinkButton, PageHeader, Segments, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type ApexStatus, type PackageOut, type PlanOut } from "@/lib/api";
import { fmtMoney, fmtPct } from "@/lib/format";
import { apexStatus as apexCopy, launch as copy } from "@/lib/copy";

export default function LaunchPage() {
  const { project, refresh } = useProject();
  const [pkg, setPkg] = useState<PackageOut | null | undefined>(undefined);
  const [plan, setPlan] = useState<PlanOut | null>(null);
  const [apex, setApex] = useState<ApexStatus | null>(null);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const viewerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.packageGet(project.id).then(setPkg).catch(() => setPkg(null));
    api.plan(project.id).then(setPlan).catch(() => setPlan(null));
    api.apexStatus().then(setApex).catch(() => setApex(null));
  }, [project.id]);

  async function build() {
    setBuilding(true);
    setError(null);
    try {
      const p = await api.packageBuild(project.id);
      setPkg(p);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBuilding(false);
    }
  }

  async function open(path: string, scroll = false) {
    setSelected(path);
    setFileBusy(true);
    setContent(null);
    if (scroll && window.matchMedia("(max-width: 1023px)").matches) viewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const f = await api.packageFile(project.id, path);
      setContent(f.content);
    } catch (e) {
      setContent(copy.couldNotLoad(path, errorText(e)));
    } finally {
      setFileBusy(false);
    }
  }

  useEffect(() => {
    if (pkg && !selected && pkg.files.includes("HANDOFF.md")) void open("HANDOFF.md");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pkg]);

  const validation = pkg?.validation ?? project.apex_validation;
  const ready = [Boolean(pkg), validation === "pass", Boolean(pkg)];
  const readyCount = ready.filter(Boolean).length;

  return (
    <div className="space-y-5">
      <PageHeader title={copy.title}>{copy.sub}</PageHeader>

      {error ? <Alert>{error}</Alert> : null}

      <Card title={copy.ready} subtitle={copy.readySub} actions={<span className="num text-[12px] text-muted">{readyCount}/3</span>}>
        <Segments total={3} filled={readyCount} size="sm" />
        <ol className="mt-4 grid gap-2 md:grid-cols-3">
          <Check3 n={1} state={building ? "busy" : pkg ? "done" : "todo"} title={copy.built} detail={pkg ? copy.builtDetail(pkg.files.length, pkg.competition_id) : copy.builtTodo} />
          <Check3
            n={2}
            state={building ? "busy" : validation === "pass" ? "done" : validation === "fail" ? "fail" : "todo"}
            title={copy.validation}
            detail={validation === "pass" ? copy.validationPass : validation === "fail" ? copy.validationFail : copy.validationTodo}
          />
          <Check3 n={3} state={pkg ? "done" : "todo"} title={copy.zip} detail={pkg ? copy.zipDone : copy.zipTodo} />
        </ol>
        {apex ? (
          <div className="mt-4 flex flex-col gap-1.5 border-t border-border pt-3 text-[12px] text-muted sm:flex-row sm:items-start sm:gap-3">
            <Badge tone={apex.live ? "accent" : "neutral"} dot={apex.live} className="shrink-0">
              {apexCopy.modes[apex.mode]}
            </Badge>
            <span className="leading-relaxed">
              {apexCopy.detail[apex.mode]}
              {apex.live && apex.dashboard_url ? (
                <>
                  {" "}
                  <a href={apex.dashboard_url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                    {apexCopy.dashboard}
                  </a>
                </>
              ) : null}
            </span>
          </div>
        ) : null}
        {pkg && pkg.steps.length > 0 ? (
          <details className="group mt-4 border-t border-border pt-3">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[13px] text-subtle [&::-webkit-details-marker]:hidden">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              {copy.stepsTitle}
            </summary>
            <ol className="mt-3 space-y-2">
              {pkg.steps.map((s) => (
                <li key={s.name} className="rounded-xl border border-border bg-card-2">
                  <details className="group/step">
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3.5 py-2.5 [&::-webkit-details-marker]:hidden">
                      <span className="text-[13px] font-medium">{s.name}</span>
                      <Badge tone={s.status === "pass" ? "ok" : s.status === "fail" ? "danger" : "neutral"} dot>
                        {s.status.replace("_", " ")}
                      </Badge>
                    </summary>
                    {s.log ? <pre className="scroll-thin mx-3.5 mb-3 max-h-48 overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-subtle [overflow-wrap:anywhere]">{s.log}</pre> : null}
                  </details>
                </li>
              ))}
            </ol>
          </details>
        ) : null}
      </Card>

      {pkg === undefined ? (
        <Skeleton className="h-72 rounded-2xl" />
      ) : pkg === null ? (
        <Empty icon={<Package className="icon-brand h-6 w-6" />}>{project.protect ? copy.buildToSee : copy.protectFirst}</Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-12">
          <Card pad={false} className="lg:col-span-4" title={copy.whatSubmitted} subtitle={copy.tapFile}>
            <div className="scroll-thin max-h-[440px] overflow-auto border-t border-border p-2">
              <TreeLevel nodes={buildTree(pkg.files)} depth={0} selected={selected} onSelect={(p) => void open(p, true)} />
            </div>
            <p className="border-t border-border px-4 py-3 text-[12px] leading-relaxed text-muted sm:px-5">{copy.zipNote}</p>
          </Card>
          <div ref={viewerRef} className="min-w-0 scroll-mt-20 lg:col-span-8">
            <Card pad={false} className="h-full" title={<span className="num text-[13px]">{selected || copy.file}</span>} actions={<Badge>{copy.readOnly}</Badge>}>
              <div className="border-t border-border">
                {fileBusy ? (
                  <div className="space-y-2 p-4">
                    <Skeleton className="h-3 w-2/3" />
                    <Skeleton className="h-3 w-1/2" />
                    <Skeleton className="h-3 w-3/4" />
                  </div>
                ) : content !== null ? (
                  <pre className="scroll-thin max-h-[480px] overflow-auto p-4 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-subtle [overflow-wrap:anywhere] sm:p-5">{content}</pre>
                ) : (
                  <p className="p-5 text-[13px] text-muted">{copy.pickFile}</p>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={copy.plan} subtitle={copy.planSub} actions={<Badge tone="warn">{copy.planSub.split(".")[0]}</Badge>}>
          {plan ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[12px] text-muted">{copy.subscription}</div>
                  <div className="num mt-1 text-[28px] leading-none font-medium tracking-[-0.02em]">{fmtMoney(plan.subscription_per_month)}</div>
                  <div className="mt-1 text-[11px] text-muted">{copy.perMonth}</div>
                </div>
                <div>
                  <div className="text-[12px] text-muted">{copy.feeNow}</div>
                  <div className="num text-gradient mt-1 text-[28px] leading-none font-medium tracking-[-0.02em]">{plan.success_fee_per_month != null ? fmtMoney(plan.success_fee_per_month) : "–"}</div>
                  <div className="mt-1 text-[11px] text-muted">{plan.success_fee_per_month != null ? copy.perMonth : copy.feeNone}</div>
                </div>
              </div>
              <dl className="mt-5 space-y-2.5 border-t border-border pt-4 text-[13px]">
                <Row label={copy.successFee} value={`${Math.round(plan.success_fee_share * 100)}% of value gained over v1`} />
                <Row label={copy.improvementNow} value={plan.improvement_rel != null ? `${plan.improvement_rel >= 0 ? "+" : ""}${fmtPct(plan.improvement_rel, 0)}` : "–"} />
              </dl>
              <ul className="mt-4 space-y-1.5 text-[12px] leading-relaxed text-muted">
                {plan.lines.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </>
          ) : (
            <Skeleton className="h-24" />
          )}
        </Card>

        <Card title={copy.terms} subtitle={copy.termsSub}>
          <ul className="space-y-3.5">
            {copy.termList.map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <ShieldCheck className="icon-brand mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden />
                <div className="text-[13px] leading-relaxed">
                  <div className="font-medium">{t}</div>
                  <div className="text-muted">{d}</div>
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-5 border-t border-border pt-4">
            <div className="text-[13px] font-medium">{copy.howApex}</div>
            <p className="mt-1 text-[12px] leading-relaxed text-muted">{copy.howApexSub}</p>
          </div>
        </Card>
      </div>

      <p className="text-center text-[18px] font-semibold tracking-[-0.02em] text-subtle sm:text-[22px]">{copy.closing}</p>

      <ActionBar
        hint={pkg ? copy.hintBuilt : copy.hintBuild}
        secondary={
          pkg ? (
            <Button size="lg" variant="secondary" busy={building} onClick={() => void build()}>
              {building ? null : <RotateCcw className="h-4 w-4" />}
              {copy.rebuild}
            </Button>
          ) : null
        }
      >
        {pkg ? (
          <LinkButton href={api.handoffUrl(project.id)} download size="lg">
            <Download className="h-4 w-4" />
            {copy.download}
          </LinkButton>
        ) : (
          <Button size="lg" busy={building} disabled={!project.protect} onClick={() => void build()}>
            {building ? null : <Package className="h-4 w-4" />}
            {building ? copy.building : copy.build}
          </Button>
        )}
      </ActionBar>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="num text-right">{value}</dd>
    </div>
  );
}

function Check3({ n, state, title, detail }: { n: number; state: "todo" | "busy" | "done" | "fail"; title: string; detail: ReactNode }) {
  return (
    <li className={cx("flex gap-3 rounded-xl border px-3.5 py-3", state === "done" ? "border-border-strong bg-card-2" : state === "fail" ? "border-danger/30 bg-danger-soft" : "border-dashed border-border")}>
      <span
        className={cx(
          "num mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px]",
          state === "done" ? "bg-brand text-background" : state === "fail" ? "bg-danger text-background" : "border border-dashed border-[#4a4a50] text-muted",
        )}
      >
        {state === "done" ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : state === "fail" ? <X className="h-3.5 w-3.5" strokeWidth={3} /> : state === "busy" ? <Spinner className="h-3.5 w-3.5" /> : n}
      </span>
      <div className="min-w-0">
        <div className="text-[13px] font-medium">{title}</div>
        <div className="mt-0.5 text-[12px] leading-snug break-words text-muted">{detail}</div>
      </div>
    </li>
  );
}

type Node = { name: string; path: string; children?: Node[] };

function buildTree(files: string[]): Node[] {
  const root: Node[] = [];
  for (const f of files.slice().sort()) {
    const parts = f.split("/");
    let level = root;
    let acc = "";
    for (let i = 0; i < parts.length; i++) {
      acc = acc ? `${acc}/${parts[i]}` : parts[i];
      const isFile = i === parts.length - 1;
      let node = level.find((n) => n.name === parts[i]);
      if (!node) {
        node = { name: parts[i], path: acc, children: isFile ? undefined : [] };
        level.push(node);
      }
      if (!isFile) level = node.children!;
    }
  }
  const sort = (nodes: Node[]) => {
    nodes.sort((a, b) => Number(Boolean(b.children)) - Number(Boolean(a.children)) || a.name.localeCompare(b.name));
    nodes.forEach((n) => n.children && sort(n.children));
  };
  sort(root);
  return root;
}

function TreeLevel({ nodes, depth, selected, onSelect }: { nodes: Node[]; depth: number; selected: string | null; onSelect: (p: string) => void }) {
  return (
    <ul>
      {nodes.map((n) => (
        <li key={n.path}>
          {n.children ? (
            <>
              <div className="flex items-center gap-2 px-2 py-1.5 text-[12px] text-muted" style={{ paddingLeft: 8 + depth * 14 }}>
                <Folder className="h-3.5 w-3.5 shrink-0" />
                <span className="num truncate">{n.name}</span>
              </div>
              <TreeLevel nodes={n.children} depth={depth + 1} selected={selected} onSelect={onSelect} />
            </>
          ) : (
            <button
              onClick={() => onSelect(n.path)}
              className={cx("flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] transition-colors", selected === n.path ? "bg-card-3 text-foreground" : "text-subtle hover:bg-card-2 hover:text-foreground")}
              style={{ paddingLeft: 8 + depth * 14 }}
            >
              <File className={cx("h-3.5 w-3.5 shrink-0", selected === n.path ? "icon-brand" : "text-muted")} />
              <span className="num truncate">{n.name}</span>
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
