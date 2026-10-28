"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronRight, Download, File, Folder, Package, RotateCcw, ShieldCheck, X } from "lucide-react";
import { ActionBar, useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, LinkButton, PageHeader, Segments, Skeleton, Spinner, cx } from "@/components/ui";
import { api, errorText, type PackageOut } from "@/lib/api";
import { fmtMoney } from "@/lib/format";

const PLATFORM_FEE = 0.15;

const TERMS: [string, string][] = [
  ["Private competition", "Only invited solvers take part. The problem is not listed publicly."],
  ["You own the winning artifact", "The winning model and its code are transferred to you."],
  ["Results hidden during the round", "Private scores stay sealed until the round closes, so nobody can tune to the holdout."],
  ["Solutions shared after 7 days", "After the round, submissions are shared among the solvers who took part, which keeps the network improving."],
];

export default function LaunchPage() {
  const { project, refresh } = useProject();
  const [pkg, setPkg] = useState<PackageOut | null | undefined>(undefined);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [bounty, setBounty] = useState(5000);
  const viewerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.packageGet(project.id).then(setPkg).catch(() => setPkg(null));
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
      setContent(`Could not load ${path}: ${errorText(e)}`);
    } finally {
      setFileBusy(false);
    }
  }

  useEffect(() => {
    if (pkg && !selected && pkg.files.includes("HANDOFF.md")) void open("HANDOFF.md");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pkg]);

  const fee = bounty * PLATFORM_FEE;
  const validation = pkg?.validation ?? project.apex_validation;
  const ready = [Boolean(pkg), validation === "pass", Boolean(pkg)];
  const readyCount = ready.filter(Boolean).length;

  return (
    <div className="space-y-5">
      <PageHeader title="Launch on Apex">
        Package the competition for Apex, the solver network on Bittensor. Nothing launches from here: you download the handoff and submit it.
      </PageHeader>

      {error ? <Alert>{error}</Alert> : null}

      <Card
        title="Ready for Apex"
        subtitle="Building the package also runs the Apex toolkit checks."
        actions={<span className="num text-[12px] text-muted">{readyCount}/3</span>}
      >
        <Segments total={3} filled={readyCount} size="sm" />
        <ol className="mt-4 grid gap-2 md:grid-cols-3">
          <Check3 n={1} state={building ? "busy" : pkg ? "done" : "todo"} title="Package built" detail={pkg ? `${pkg.files.length} files · ${pkg.competition_id}` : "Competition folder in apex.competition.v1 format"} />
          <Check3
            n={2}
            state={building ? "busy" : validation === "pass" ? "done" : validation === "fail" ? "fail" : "todo"}
            title="Toolkit validation"
            detail={validation === "pass" ? "Preflight, screen and a local referee run passed" : validation === "fail" ? "A check failed. See the steps below" : "Runs with the build, about 20 seconds"}
          />
          <Check3 n={3} state={pkg ? "done" : "todo"} title="Handoff zip" detail={pkg ? "Private holdout excluded, checksums included" : "Available once the package is built"} />
        </ol>
        {pkg && pkg.steps.length > 0 ? (
          <details className="group mt-4 border-t border-border pt-3">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[13px] text-subtle [&::-webkit-details-marker]:hidden">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              Validation steps
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
                    {s.log ? (
                      <pre className="scroll-thin mx-3.5 mb-3 max-h-48 overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-subtle [overflow-wrap:anywhere]">
                        {s.log}
                      </pre>
                    ) : null}
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
        <Empty icon={<Package className="icon-brand h-6 w-6" />}>
          {project.protect ? "Build the package to see every file that will be submitted." : "Run data protection first, then build the package."}
        </Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-12">
          <Card pad={false} className="lg:col-span-4" title="What will be submitted" subtitle="Tap a file to read it.">
            <div className="scroll-thin max-h-[440px] overflow-auto border-t border-border p-2">
              <TreeLevel nodes={buildTree(pkg.files)} depth={0} selected={selected} onSelect={(p) => void open(p, true)} />
            </div>
            <p className="border-t border-border px-4 py-3 text-[12px] leading-relaxed text-muted sm:px-5">
              The zip leaves out the private holdout and its labels. Their checksums are included so Apex can verify the copy you transfer
              separately.
            </p>
          </Card>
          <div ref={viewerRef} className="min-w-0 scroll-mt-20 lg:col-span-8">
            <Card pad={false} className="h-full" title={<span className="num text-[13px]">{selected || "File"}</span>} actions={<Badge>read only</Badge>}>
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
                  <p className="p-5 text-[13px] text-muted">Pick a file.</p>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pricing estimate" subtitle="Illustrative. No payment is taken.">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[13px] text-subtle">Bounty for the winning solver</span>
            <span className="num text-[28px] leading-none font-medium tracking-[-0.02em]">{fmtMoney(bounty)}</span>
          </div>
          <input
            type="range"
            min={1000}
            max={50000}
            step={500}
            value={bounty}
            onChange={(e) => setBounty(Number(e.target.value))}
            aria-label="Bounty"
            className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-card-3 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-foreground [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-foreground [&::-webkit-slider-thumb]:shadow-[0_0_0_4px_rgb(255_255_255/0.08)]"
            style={{ background: `linear-gradient(90deg, var(--c-peach), var(--c-pink) ${((bounty - 1000) / 49000) * 50}%, var(--c-violet) ${((bounty - 1000) / 49000) * 100}%, var(--card-3) ${((bounty - 1000) / 49000) * 100}%)` }}
          />
          <div className="num mt-2 flex justify-between text-[11px] text-muted">
            <span>{fmtMoney(1000)}</span>
            <span>{fmtMoney(50000)}</span>
          </div>
          <dl className="mt-5 space-y-2.5 border-t border-border pt-4 text-[13px]">
            <Row label="Bounty" value={fmtMoney(bounty)} />
            <Row label={`Platform fee (${Math.round(PLATFORM_FEE * 100)}%)`} value={fmtMoney(fee)} />
            <div className="flex items-baseline justify-between border-t border-dashed border-border-strong pt-2.5">
              <dt className="font-medium">Estimated total</dt>
              <dd className="num text-[16px] font-medium">{fmtMoney(bounty + fee)}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Terms summary" subtitle="What you keep and what solvers see.">
          <ul className="space-y-3.5">
            {TERMS.map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft">
                  <ShieldCheck className="icon-brand h-3 w-3" />
                </span>
                <div className="text-[13px] leading-relaxed">
                  <div className="font-medium">{t}</div>
                  <div className="text-muted">{d}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <ActionBar
        hint={pkg ? "The zip holds the competition folder, the protection report and HANDOFF.md." : "Build once: it packages the competition and validates it with the Apex toolkit."}
        secondary={
          pkg ? (
            <Button size="lg" variant="secondary" busy={building} onClick={() => void build()}>
              {building ? null : <RotateCcw className="h-4 w-4" />}
              Rebuild
            </Button>
          ) : null
        }
      >
        {pkg ? (
          <LinkButton href={api.handoffUrl(project.id)} download size="lg">
            <Download className="h-4 w-4" />
            Download handoff
          </LinkButton>
        ) : (
          <Button size="lg" busy={building} disabled={!project.protect} onClick={() => void build()}>
            {building ? null : <Package className="h-4 w-4" />}
            {building ? "Building and validating" : "Build and validate"}
          </Button>
        )}
      </ActionBar>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className="num">{value}</dd>
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
              className={cx(
                "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] transition-colors",
                selected === n.path ? "bg-card-3 text-foreground" : "text-subtle hover:bg-card-2 hover:text-foreground",
              )}
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
