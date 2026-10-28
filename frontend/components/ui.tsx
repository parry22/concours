"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { fmtCell } from "@/lib/format";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "lg" | "md" | "sm";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  busy?: boolean;
};

const variants: Record<Variant, string> = {
  primary:
    "bg-foreground text-background shadow-[inset_0_-1px_0_rgb(0_0_0/0.15),0_1px_0_rgb(255_255_255/0.08)] hover:bg-white disabled:bg-card-3 disabled:text-muted disabled:shadow-none",
  secondary: "bg-card-2 text-foreground border border-border-strong hover:bg-card-3 hover:border-[#3a3a40] disabled:text-muted",
  ghost: "bg-transparent text-subtle hover:bg-card-2 hover:text-foreground disabled:text-muted",
  danger: "bg-danger-soft text-danger border border-danger/25 hover:bg-danger/20 disabled:text-muted",
};

const sizes: Record<Size, string> = {
  lg: "h-11 px-5 text-[14px] rounded-xl",
  md: "h-9 px-3.5 text-[13px] rounded-lg",
  sm: "h-8 px-3 text-[13px] rounded-lg",
};

const base =
  "inline-flex shrink-0 items-center justify-center gap-2 font-medium whitespace-nowrap transition-[background-color,border-color,color,transform] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100";

export function Button({ variant = "primary", size = "md", busy, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button {...rest} disabled={disabled || busy} className={cx(base, sizes[size], variants[variant], className)}>
      {busy ? <Spinner className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  children,
  variant = "primary",
  size = "md",
  className,
  download,
  external,
}: {
  href: string;
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
  download?: boolean | string;
  external?: boolean;
}) {
  const cls = cx(base, sizes[size], variants[variant], className);
  if (external || download)
    return (
      <a href={href} className={cls} download={download === true ? "" : download || undefined}>
        {children}
      </a>
    );
  return (
    <Link href={href} className={cls}>
      {children}
    </Link>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx("animate-spin", className || "h-5 w-5")} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" className="opacity-20" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export function Card({
  children,
  className,
  title,
  subtitle,
  actions,
  pad = true,
}: {
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  pad?: boolean;
}) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-border bg-card", pad && "p-4 sm:p-5", className)}>
      {title || actions ? (
        <header className={cx("mb-4 flex items-start justify-between gap-3", !pad && "px-4 pt-4 sm:px-5 sm:pt-5")}>
          <div className="min-w-0">
            {title ? <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{title}</h2> : null}
            {subtitle ? <div className="mt-1 text-[13px] leading-relaxed text-muted">{subtitle}</div> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function Alert({ kind = "error", children, className }: { kind?: "error" | "warn" | "info" | "ok"; children: ReactNode; className?: string }) {
  const styles = {
    error: "bg-danger-soft text-[#fca5a5] border-danger/20",
    warn: "bg-warn-soft text-[#fcd34d] border-warn/20",
    info: "bg-accent-soft text-[#c4b5fd] border-accent/20",
    ok: "bg-ok-soft text-[#86efac] border-ok/20",
  }[kind];
  const dot = { error: "bg-danger", warn: "bg-warn", info: "bg-accent", ok: "bg-ok" }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={cx("flex gap-3 rounded-xl border px-3.5 py-3 text-[13px] leading-relaxed", styles, className)}>
      <span className={cx("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", dot)} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

const toneStyles: Record<Tone, string> = {
  neutral: "bg-card-3 text-subtle",
  accent: "bg-accent-soft text-[#c4b5fd]",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
};

export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cx("inline-flex h-[22px] items-center gap-1.5 rounded-md px-2 text-[12px] font-medium whitespace-nowrap", toneStyles[tone], className)}>
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}

export function Pill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex h-7 items-center gap-1.5 rounded-full border border-border-strong bg-card-2 px-3 text-[12px] font-medium text-subtle", className)}>
      {children}
    </span>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-[13px] text-muted">
      <Spinner className="h-4 w-4" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("shimmer rounded-lg", className)} />;
}

export function Empty({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border-strong px-6 py-10 text-center text-[13px] text-muted">
      {icon ? <div className="text-subtle">{icon}</div> : null}
      <div className="max-w-sm leading-relaxed">{children}</div>
    </div>
  );
}

/** KPI tile: small label, large monospace figure. */
export function Stat({ label, value, hint, className }: { label: ReactNode; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={cx("min-w-0 rounded-2xl border border-border bg-card px-4 py-3.5", className)}>
      <div className="text-[12px] font-medium text-muted">{label}</div>
      <div className="num mt-1.5 truncate text-[22px] font-medium leading-none sm:text-[26px]">{value}</div>
      {hint ? <div className="mt-2 text-[12px] leading-snug text-muted">{hint}</div> : null}
    </div>
  );
}

/** Horizontal progress bar, as in the reference's spending list. `className` sets its size (default h-2 w-full). */
export function Meter({ value, color = "var(--c-violet)", className }: { value: number; color?: string; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={cx("shrink-0 overflow-hidden rounded-full bg-card-3", className || "h-2 w-full")}>
      <div className="h-full rounded-full transition-[width] duration-700 ease-out" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

/** Segmented bar, as in the reference's payment score. */
export function Segments({ total, filled, current, className, size = "md" }: { total: number; filled: number; current?: number; className?: string; size?: "md" | "sm" }) {
  return (
    <div className={cx("flex w-full gap-[3px]", className)} aria-hidden>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={cx(
            "flex-1 rounded-[3px] transition-colors duration-300",
            size === "md" ? "h-5" : "h-1.5",
            i === current ? "bg-foreground" : i < filled ? "bg-ok" : "bg-card-3",
          )}
        />
      ))}
    </div>
  );
}

export function DataTable({ columns, rows, className, highlight }: { columns: string[]; rows: Record<string, unknown>[]; className?: string; highlight?: string[] }) {
  return (
    <div className={cx("scroll-thin overflow-auto rounded-xl border border-border", className)}>
      <table className="min-w-full border-separate border-spacing-0 text-left text-[12px]">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th
                key={c}
                className={cx(
                  "border-b border-border bg-card-2 px-3 py-2.5 font-medium whitespace-nowrap text-muted",
                  i === 0 && "sticky left-0 z-10",
                  highlight?.includes(c) && "text-foreground",
                )}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="group">
              {columns.map((c, i) => (
                <td
                  key={c}
                  className={cx(
                    "num border-b border-border/60 px-3 py-2 whitespace-nowrap text-subtle group-last:border-b-0",
                    i === 0 && "sticky left-0 z-10 bg-card text-foreground",
                    highlight?.includes(c) && "text-foreground",
                  )}
                >
                  {fmtCell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-[12px] font-medium text-muted">{label}</span>
      {children}
      {hint ? <span className="mt-1.5 block text-[12px] text-muted">{hint}</span> : null}
    </label>
  );
}

export const inputClass =
  "h-10 w-full min-w-0 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted hover:border-[#3a3a40] focus:border-accent/70 focus:ring-2 focus:ring-accent/20 disabled:opacity-50";

export function Dot({ className }: { className?: string }) {
  return <span className={cx("inline-block h-2 w-2 shrink-0 rounded-full", className)} />;
}

/** Page heading used by every step. */
export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: ReactNode; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? <div className="mb-2 text-[12px] font-medium text-muted">{eyebrow}</div> : null}
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] sm:text-[26px]">{title}</h1>
        {children ? <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-subtle">{children}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Small logo mark: a four-point star in a rounded square, after the reference. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cx("h-8 w-8", className)} aria-label="Brief">
      <rect width="32" height="32" rx="9" fill="#ededef" />
      <path d="M16 6.5c.6 4.6 4.9 8.9 9.5 9.5-4.6.6-8.9 4.9-9.5 9.5-.6-4.6-4.9-8.9-9.5-9.5 4.6-.6 8.9-4.9 9.5-9.5Z" fill="#0a0a0b" />
    </svg>
  );
}
