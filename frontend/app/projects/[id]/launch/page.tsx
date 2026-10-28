"use client";

import { useEffect, useState } from "react";
import { useProject } from "@/components/ProjectShell";
import { Alert, Badge, Button, Card, Empty, Loading, Spinner, cx } from "@/components/ui";
import { api, errorText, type PackageOut } from "@/lib/api";
import { fmtMoney } from "@/lib/format";

const PLATFORM_FEE = 0.15;

export default function LaunchPage() {
  const { project, refresh } = useProject();
  const [pkg, setPkg] = useState<PackageOut | null | undefined>(undefined);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [bounty, setBounty] = useState(5000);

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

  async function open(path: string) {
    setSelected(path);
    setFileBusy(true);
    setContent(null);
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Launch on Apex</h1>
        <p className="mt-1 max-w-2xl text-muted">
          Everything below goes to Apex, a competition network on Bittensor, where global solvers compete on your protected data.
          Nothing is launched from here. You download the handoff package and submit it.
        </p>
      </div>

      {error ? <Alert>{error}</Alert> : null}

      {pkg === undefined ? (
        <Loading label="Checking for a package" />
      ) : pkg === null ? (
        <Card title="Build the competition package" subtitle="Needed before the handoff. Runs the Apex toolkit checks as part of the build.">
          <Button busy={building} onClick={() => void build()} disabled={!project.protect}>
            Build package
          </Button>
          {!project.protect ? <p className="mt-2 text-xs text-muted">Run data protection first.</p> : null}
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card
            className="lg:col-span-2"
            title="What will be submitted"
            subtitle={
              <span className="flex items-center gap-2">
                Toolkit validation
                <Badge tone={validation === "pass" ? "ok" : validation === "fail" ? "danger" : "neutral"}>{validation === "not_run" ? "not run" : validation}</Badge>
              </span>
            }
            actions={
              <Button size="sm" variant="ghost" busy={building} onClick={() => void build()}>
                Rebuild
              </Button>
            }
          >
            <FileTree files={pkg.files} selected={selected} onSelect={(p) => void open(p)} />
            <p className="mt-3 text-xs text-muted">The zip leaves out the private holdout and its labels (referee/data/holdout.csv and holdout_labels.csv). Their checksums are included, so Apex can verify the copy you transfer separately.</p>
          </Card>

          <Card className="lg:col-span-3" title={selected || "File"} subtitle="Read only.">
            {fileBusy ? (
              <div className="flex items-center gap-2 text-sm text-muted">
                <Spinner className="h-4 w-4" /> Loading
              </div>
            ) : content !== null ? (
              <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-xl bg-stone-50 p-4 font-mono text-xs leading-relaxed text-stone-800">{content}</pre>
            ) : (
              <Empty>Pick a file on the left.</Empty>
            )}
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Pricing estimate" subtitle="Illustrative, no payment is taken.">
          <label className="block">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">Bounty for the winning solver</span>
              <span className="text-lg font-semibold tabular-nums">{fmtMoney(bounty)}</span>
            </div>
            <input type="range" min={1000} max={50000} step={500} value={bounty} onChange={(e) => setBounty(Number(e.target.value))} className="mt-3 w-full accent-[var(--accent)]" />
            <div className="mt-1 flex justify-between text-xs text-muted">
              <span>{fmtMoney(1000)}</span>
              <span>{fmtMoney(50000)}</span>
            </div>
          </label>
          <dl className="mt-5 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Bounty</dt>
              <dd className="tabular-nums">{fmtMoney(bounty)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Platform fee ({Math.round(PLATFORM_FEE * 100)}%)</dt>
              <dd className="tabular-nums">{fmtMoney(fee)}</dd>
            </div>
            <div className="flex justify-between border-t border-border pt-2 font-medium">
              <dt>Estimated total</dt>
              <dd className="tabular-nums">{fmtMoney(bounty + fee)}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-muted">These numbers are illustrative. No payment is taken. Final terms are agreed when the competition is submitted.</p>
        </Card>

        <Card title="Terms summary" subtitle="What you keep and what solvers see.">
          <ul className="space-y-3 text-sm">
            {[
              ["Private competition", "Only invited solvers take part. The problem is not listed publicly."],
              ["You own the winning artifact", "The winning model and its code are transferred to you."],
              ["Results hidden during the round", "Private scores stay sealed until the round closes, so nobody can tune to the holdout."],
              ["Solutions revealed to other solvers after 7 days", "After the round, submissions are shared among the solvers who took part, which keeps the network improving."],
            ].map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <div>
                  <div className="font-medium">{t}</div>
                  <div className="text-muted">{d}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Handoff package" subtitle="A zip with the competition folder, the data protection report and a HANDOFF.md that explains the problem, the scoring rule and the terms above.">
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={api.handoffUrl(project.id)}
            className={cx(
              "inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium",
              pkg ? "bg-foreground text-white hover:bg-stone-700" : "pointer-events-none bg-stone-200 text-stone-400",
            )}
            aria-disabled={!pkg}
            download
          >
            Download handoff package
          </a>
          {!pkg ? <span className="text-xs text-muted">Build the package first.</span> : null}
        </div>
      </Card>
    </div>
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

function FileTree({ files, selected, onSelect }: { files: string[]; selected: string | null; onSelect: (p: string) => void }) {
  const tree = buildTree(files);
  return (
    <div className="max-h-[480px] overflow-auto rounded-xl border border-border p-2 font-mono text-xs">
      <TreeLevel nodes={tree} depth={0} selected={selected} onSelect={onSelect} />
    </div>
  );
}

function TreeLevel({ nodes, depth, selected, onSelect }: { nodes: Node[]; depth: number; selected: string | null; onSelect: (p: string) => void }) {
  return (
    <ul>
      {nodes.map((n) => (
        <li key={n.path}>
          {n.children ? (
            <>
              <div className="px-2 py-1 text-muted" style={{ paddingLeft: 8 + depth * 14 }}>
                {n.name}/
              </div>
              <TreeLevel nodes={n.children} depth={depth + 1} selected={selected} onSelect={onSelect} />
            </>
          ) : (
            <button
              onClick={() => onSelect(n.path)}
              className={cx("block w-full rounded-md px-2 py-1 text-left hover:bg-stone-100", selected === n.path && "bg-accent-soft text-accent")}
              style={{ paddingLeft: 8 + depth * 14 }}
            >
              {n.name}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
