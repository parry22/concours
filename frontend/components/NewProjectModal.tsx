"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CreditCard, Upload, X } from "lucide-react";
import { Alert, Spinner, cx } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { newProject as copy } from "@/lib/copy";
import { rememberProject } from "@/lib/last-project";
import { stepHref } from "@/lib/stages";

/** Name the project, then start from your own transactions or from the sample. */
export function NewProjectModal({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<"own" | "sample" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose, busy]);

  async function create(sample: boolean) {
    setBusy(sample ? "sample" : "own");
    setError(null);
    try {
      const p = await api.createProject("fraud", name.trim() || undefined, sample);
      rememberProject(p.id);
      onClose();
      router.push(stepHref(p.id, "upload"));
    } catch (e) {
      setError(errorText(e));
      setBusy(null);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" role="dialog" aria-modal aria-labelledby="new-project-title">
      <button className="fade-in absolute inset-0 bg-black/65 backdrop-blur-[2px]" aria-label={copy.close} onClick={() => !busy && onClose()} />
      <div className="sheet-in relative w-full max-w-[440px] rounded-t-[24px] border border-border-strong bg-card p-5 pb-[calc(20px+var(--safe-bottom))] sm:rounded-2xl sm:pb-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="new-project-title" className="text-[16px] font-semibold tracking-[-0.01em]">
              {copy.title}
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{copy.sub}</p>
          </div>
          <button onClick={onClose} disabled={busy !== null} className="-mt-1 -mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-card-2 hover:text-foreground" aria-label={copy.close}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <label className="mt-5 block">
          <span className="mb-1.5 block text-[12px] font-medium text-muted">{copy.name}</span>
          <input
            ref={input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={copy.namePlaceholder}
            maxLength={80}
            className="h-11 w-full rounded-xl border border-border-strong bg-card-2 px-3.5 text-[14px] placeholder:text-muted hover:border-[#3a3a40] focus:border-accent/70"
          />
        </label>

        {error ? <Alert className="mt-4">{error}</Alert> : null}

        <div className="mt-5 grid gap-2">
          <Choice icon={<Upload className="h-4 w-4" />} title={copy.own} line={copy.ownLine} busy={busy === "own"} disabled={busy !== null} onClick={() => void create(false)} />
          <Choice icon={<CreditCard className="h-4 w-4" />} title={copy.sample} line={copy.sampleLine} busy={busy === "sample"} disabled={busy !== null} onClick={() => void create(true)} />
        </div>
      </div>
    </div>
  );
}

function Choice({ icon, title, line, busy, disabled, onClick }: { icon: React.ReactNode; title: string; line: string; busy: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "flex w-full items-center gap-3 rounded-xl border border-border-strong bg-card-2 px-3.5 py-3 text-left transition-[border-color,background-color] duration-150",
        "hover:border-[#3a3a40] hover:bg-card-3 disabled:cursor-not-allowed disabled:opacity-60",
      )}
    >
      <span className="icon-brand flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-card">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-medium">{title}</span>
        <span className="block text-[12px] leading-snug text-muted">{line}</span>
      </span>
      {busy ? <Spinner className="h-4 w-4 text-muted" /> : null}
    </button>
  );
}
