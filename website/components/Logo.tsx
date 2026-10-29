// The Concours mark, drawn exactly as Logo in frontend/components/ui.tsx: one cylinder of data split in two; the
// floating slice is the sealed holdout. `id` keeps gradient ids unique when the mark appears more than once.

export function LogoMark({ id, ...rest }: { id: string } & React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="5 2 22 28" fill="none" aria-hidden {...rest}>
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

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark id="nav-logo" className="h-[26px] w-[20px] overflow-visible" />
      <span className="text-[19px] font-semibold tracking-[-0.02em] text-foreground">Concours</span>
    </span>
  );
}
