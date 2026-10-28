"use client";

import Link from "next/link";
import { useId, type ReactNode } from "react";
import { fmtCell } from "@/lib/format";
import { brand, status as statusCopy, tooltips } from "@/lib/copy";

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
    warn: "bg-warn-soft text-[#fbd7a5] border-warn/20",
    info: "bg-accent-soft text-[#c4b5fd] border-accent/20",
    ok: "bg-ok-soft text-[#ddd6fe] border-ok/20",
  }[kind];
  const dot = { error: "bg-danger", warn: "bg-warn", info: "bg-brand", ok: "bg-brand" }[kind];
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

export function Badge({ tone = "neutral", children, className, dot, title }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex h-[22px] items-center gap-1.5 rounded-md px-2 text-[12px] font-medium whitespace-nowrap", toneStyles[tone], className)}>
      {dot ? <span className={cx("h-1.5 w-1.5 rounded-full", tone === "ok" || tone === "accent" ? "bg-brand" : "bg-current")} /> : null}
      {children}
    </span>
  );
}

/** "Improving", "Healthy" or "Slipping" next to a model version. */
export function StatusPill({ status, className }: { status: "improving" | "healthy" | "slipping" | "none"; className?: string }) {
  if (status === "none") return null;
  const tone: Tone = status === "slipping" ? "danger" : status === "improving" ? "accent" : "ok";
  return (
    <Badge tone={tone} dot className={className} title={tooltips[status]}>
      {statusCopy[status]}
    </Badge>
  );
}

/** The result figure that leads a screen: the big gradient number with a label above and a line under it. */
export function ResultFigure({ label, value, unit, line, delta, className }: { label: ReactNode; value: ReactNode; unit?: ReactNode; line?: ReactNode; delta?: ReactNode; className?: string }) {
  return (
    <div className={cx("min-w-0", className)}>
      <span className="inline-flex h-8 max-w-full items-center gap-2 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] font-medium">
        <span className="truncate">{label}</span>
      </span>
      <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="num pop-in text-gradient text-[44px] leading-none font-medium tracking-[-0.03em] sm:text-[56px]">
          {value}
          {unit ? <span className="ml-0.5 align-top text-[22px] sm:text-[26px]">{unit}</span> : null}
        </span>
        {delta ? <span>{delta}</span> : null}
      </div>
      {line ? <div className="mt-2 text-[13px] text-muted">{line}</div> : null}
    </div>
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
export function Stat({ label, value, hint, className, accent }: { label: ReactNode; value: ReactNode; hint?: ReactNode; className?: string; accent?: boolean }) {
  return (
    <div className={cx("min-w-0 rounded-2xl border border-border bg-card px-4 py-3.5", className)}>
      <div className="text-[12px] font-medium text-muted">{label}</div>
      <div className={cx("num mt-1.5 truncate text-[22px] font-medium leading-none sm:text-[26px]", accent && "text-gradient")}>{value}</div>
      {hint ? <div className="mt-2 text-[12px] leading-snug text-muted">{hint}</div> : null}
    </div>
  );
}

/** Horizontal progress bar, as in the reference's spending list. `className` sets its size (default h-2 w-full). `color="brand"` uses the textured gradient. */
export function Meter({ value, color = "brand", className }: { value: number; color?: string; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={cx("shrink-0 overflow-hidden rounded-full bg-card-3", className || "h-2 w-full")}>
      <div
        className={cx("h-full rounded-full transition-[width] duration-700 ease-out", color === "brand" && "bg-brand-x")}
        style={{ width: `${pct}%`, background: color === "brand" ? undefined : color }}
      />
    </div>
  );
}

/**
 * Segmented bar, as in the reference's payment score. Filled segments share one brand gradient across the whole bar;
 * the current segment shows its slice of it, dimmed.
 */
export function Segments({ total, filled, current, className, size = "md" }: { total: number; filled: number; current?: number; className?: string; size?: "md" | "sm" }) {
  return (
    <div className={cx("flex w-full gap-[3px]", className)} aria-hidden>
      {Array.from({ length: total }).map((_, i) => {
        const lit = i < filled || i === current;
        return (
          <span
            key={i}
            className={cx(
              "flex-1 rounded-[3px] transition-opacity duration-300",
              size === "md" ? "h-5" : "h-1.5",
              lit ? "bg-brand-x" : "bg-card-3",
              i === current && i >= filled && "opacity-45",
            )}
            style={
              lit
                ? {
                    backgroundSize: `100% 100%, ${total * 100}% 100%`,
                    backgroundPosition: `0 0, ${total > 1 ? (i / (total - 1)) * 100 : 0}% 0`,
                  }
                : undefined
            }
          />
        );
      })}
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

/**
 * Concours's mark: one cylinder of data cut in two. The lower body is the public data (a seam marks the thin leaderboard
 * band above the training rows); the floating slice with the glowing cap is the sealed private holdout, and light
 * leaks through the gap between them. No background. Same drawing as app/icon.svg, but the viewBox is cropped to the
 * artwork (22 x 28) so the mark sits flush beside text; size it by height with a width of about 0.79 of that.
 */
export function Logo({ className }: { className?: string; compact?: boolean }) {
  // Ids per instance: a gradient defined inside a hidden copy (the desktop sidebar on phones) would not paint elsewhere.
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="5 2 22 28" fill="none" className={cx("h-[22px] w-[17px] overflow-visible", className)} role="img" aria-label={brand.name}>
      <defs>
        <linearGradient id={`${id}fill`} gradientUnits="userSpaceOnUse" x1="0" y1="3" x2="0" y2="29.5">
          <stop offset="0" stopColor="#fbb39c" />
          <stop offset="0.3" stopColor="#f472b6" />
          <stop offset="0.62" stopColor="#c084fc" />
          <stop offset="1" stopColor="#818cf8" />
        </linearGradient>
        <linearGradient id={`${id}shade`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#000" stopOpacity="0.38" />
          <stop offset="0.3" stopColor="#fff" stopOpacity="0.18" />
          <stop offset="0.55" stopColor="#fff" stopOpacity="0.02" />
          <stop offset="1" stopColor="#000" stopOpacity="0.42" />
        </linearGradient>
        <radialGradient id={`${id}cap`} cx="0.42" cy="0.4" r="0.62">
          <stop offset="0" stopColor="#fffaf6" />
          <stop offset="0.45" stopColor="#ffd9c9" />
          <stop offset="1" stopColor="#f9a58b" />
        </radialGradient>
        <radialGradient id={`${id}face`} cx="0.5" cy="0.45" r="0.6">
          <stop offset="0" stopColor="#f472b6" stopOpacity="0.9" />
          <stop offset="0.55" stopColor="#a855f7" stopOpacity="0.55" />
          <stop offset="1" stopColor="#2a1640" stopOpacity="0.9" />
        </radialGradient>
        <filter id={`${id}blur`} x="-50%" y="-200%" width="200%" height="500%">
          <feGaussianBlur stdDeviation="0.9" />
        </filter>
      </defs>
      {/* Lower body: the public data. A seam marks the thin leaderboard band above the training rows. */}
      <rect x="7" y="14" width="18" height="15.5" rx="9" ry="3.2" fill={`url(#${id}fill)`} />
      <rect x="7" y="14" width="18" height="15.5" rx="9" ry="3.2" fill={`url(#${id}shade)`} />
      <path d="M7.35 20.6a8.65 3.05 0 0 0 17.3 0" stroke="#0a0a0b" strokeOpacity="0.38" strokeWidth="0.7" fill="none" />
      <path d="M7.35 21.3a8.65 3.05 0 0 0 17.3 0" stroke="#fff" strokeOpacity="0.3" strokeWidth="0.45" fill="none" />
      <path d="M7.35 26.3a8.65 3.05 0 0 0 17.3 0" stroke="#0a0a0b" strokeOpacity="0.35" strokeWidth="0.7" fill="none" />
      <rect x="10.4" y="18.6" width="1.1" height="9.6" rx="0.55" fill="#fff" opacity="0.2" />
      {/* Cut face, lit from the gap by the sealed slice above. */}
      <ellipse cx="16" cy="17.2" rx="9" ry="3.2" fill={`url(#${id}face)`} />
      <ellipse cx="16" cy="17.2" rx="5.6" ry="1.7" fill="#f9a8d4" opacity="0.55" filter={`url(#${id}blur)`} />
      <ellipse cx="16" cy="17.2" rx="8.75" ry="3" stroke="#fff" strokeOpacity="0.32" strokeWidth="0.5" fill="none" />
      {/* Glow leaking through the gap. */}
      <ellipse cx="16" cy="12.6" rx="7.5" ry="1.4" fill="#fbb39c" opacity="0.5" filter={`url(#${id}blur)`} />
      {/* The sealed holdout slice, floating, with the glowing cap. */}
      <rect x="7" y="3" width="18" height="8.4" rx="9" ry="3.2" fill={`url(#${id}fill)`} />
      <rect x="7" y="3" width="18" height="8.4" rx="9" ry="3.2" fill={`url(#${id}shade)`} />
      <path d="M7.35 8.2a8.65 3.05 0 0 0 17.3 0" stroke="#0a0a0b" strokeOpacity="0.3" strokeWidth="0.6" fill="none" />
      <rect x="10.4" y="6.8" width="1.1" height="3.6" rx="0.55" fill="#fff" opacity="0.28" />
      <ellipse cx="16" cy="6.2" rx="9" ry="3.2" fill={`url(#${id}cap)`} />
      <ellipse cx="16" cy="6.2" rx="8.75" ry="3" stroke="#fff" strokeOpacity="0.75" strokeWidth="0.5" fill="none" />
      <ellipse cx="13.6" cy="5.4" rx="3.6" ry="1.05" fill="#fff" opacity="0.7" />
      <circle cx="21.4" cy="5.1" r="0.55" fill="#fff" opacity="0.9" />
    </svg>
  );
}
