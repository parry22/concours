"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, RotateCcw } from "lucide-react";
import { ActionBar, NextLink, useProject } from "@/components/ProjectShell";
import { Alert, Button, Card, PageHeader, cx } from "@/components/ui";
import { api, errorText, type IntakeMessage } from "@/lib/api";
import { questions as copy } from "@/lib/copy";
import { stageIndex, stepHref } from "@/lib/stages";

/** Three questions about the team, with defaults. Answers are parsed in code; nothing is guessed by a model. */
export default function QuestionsPage() {
  const { project, refresh } = useProject();
  const router = useRouter();
  const [qs, setQs] = useState<{ questions: string[]; suggested: string[] } | null>(null);
  const [history, setHistory] = useState<IntakeMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void Promise.all([api.fraudQuestions(), api.intakeHistory(project.id)])
      .then(([q, h]) => {
        setQs(q);
        setHistory(h);
      })
      .catch((e) => setError(errorText(e)));
  }, [project.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [history.length]);

  const answered = history.filter((m) => m.role === "user").length;
  const done = answered >= 3;
  const st = project.fraud_settings;
  const thread: IntakeMessage[] = history.length ? history : qs ? [{ role: "assistant", content: qs.questions[0] }] : [];

  async function send(message: string) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.intake(project.id, message);
      setHistory(r.history);
      setText("");
      const p = await refresh();
      if (r.done && p) router.push(stepHref(p.id, "protect"));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function restart() {
    await api.intakeReset(project.id);
    setHistory([]);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={copy.title}
        actions={
          history.length ? (
            <Button variant="ghost" onClick={() => void restart()} disabled={busy}>
              <RotateCcw className="h-3.5 w-3.5" />
              {copy.restart}
            </Button>
          ) : null
        }
      >
        {copy.sub}
      </PageHeader>
      {error ? <Alert>{error}</Alert> : null}

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8" pad={false}>
          <div className="space-y-3 p-4 sm:p-5">
            {thread.map((m, i) => (
              <div key={i} className={cx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cx(
                    "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed",
                    m.role === "user" ? "bg-foreground text-background" : "border border-border bg-card-2",
                  )}
                >
                  {m.role === "assistant" ? <div className="mb-0.5 text-[11px] font-medium text-muted">{copy.assistant}</div> : null}
                  {m.content}
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
          {!done ? (
            <div className="border-t border-border p-3 sm:p-4">
              {qs ? (
                <button
                  onClick={() => void send(qs.suggested[answered])}
                  disabled={busy}
                  className="mb-2 inline-flex h-8 items-center rounded-full border border-border-strong bg-card-2 px-3 text-[12px] text-subtle hover:text-foreground disabled:opacity-50"
                >
                  {qs.suggested[answered]}
                </button>
              ) : null}
              <form
                className="flex items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send(text.trim() || copy.useDefault);
                }}
              >
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder={copy.placeholder} disabled={busy}
                  className="h-11 min-w-0 flex-1 rounded-xl border border-border-strong bg-card-2 px-3.5 text-[14px] outline-none focus:border-foreground/40" />
                <Button type="submit" size="lg" busy={busy} aria-label={copy.send}>
                  <ArrowUp className="h-4 w-4" />
                </Button>
              </form>
              <p className="mt-2 text-[12px] text-muted">{copy.blank}</p>
            </div>
          ) : null}
        </Card>

        <Card className="lg:col-span-4" title={copy.settings}>
          <dl className="space-y-3 text-[13px]">
            <Row label={copy.capacity} value={st ? st.daily_capacity.toLocaleString("en-US") : "200"} set={answered >= 1} />
            <Row label={copy.reviewCost} value={st ? `$${st.review_cost.toFixed(2)}` : "$10.00"} set={answered >= 2} />
            <Row label={copy.fee} value={st ? `$${st.fraud_fee.toFixed(2)}` : "$0.00"} set={answered >= 2} />
            <Row label={copy.delay} value={st ? String(st.label_delay_days) : "30"} set={answered >= 3} />
          </dl>
        </Card>
      </div>

      <ActionBar hint={done ? copy.hintDone : copy.hintTodo}>
        <NextLink stage="protect" label={copy.next} disabled={stageIndex(project.stage) < stageIndex("protect")} />
      </ActionBar>
    </div>
  );
}

function Row({ label, value, set }: { label: string; value: string; set: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/70 pb-2.5 last:border-b-0 last:pb-0">
      <dt className="text-muted">{label}</dt>
      <dd className={cx("num font-medium", !set && "text-muted")}>{value}</dd>
    </div>
  );
}
