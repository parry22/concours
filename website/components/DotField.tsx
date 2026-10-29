// Halftone dot clusters at the left and right edges of the diagram band, fading out toward the centre.
// Noise from feTurbulence decides where dots appear; a second, larger dot layer shows only where the noise is
// strongest, which gives the uneven halftone of the reference.

export function DotField() {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
      <defs>
        <pattern id="dots-sm" width="9" height="9" patternUnits="userSpaceOnUse">
          <rect x="3" y="3" width="3" height="3" rx="0.7" fill="#34343a" />
        </pattern>
        <pattern id="dots-lg" width="9" height="9" patternUnits="userSpaceOnUse">
          <rect x="2" y="2" width="5" height="5" rx="1" fill="#404046" />
        </pattern>
        <filter id="dots-noise" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="3" seed="7" />
          <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  3.2 0 0 0 -1.25" />
        </filter>
        <filter id="dots-noise-hi" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="3" seed="7" />
          <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  6 0 0 0 -3.5" />
        </filter>
        <linearGradient id="dots-edges" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0.9" />
          <stop offset="0.2" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="0.33" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.67" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.8" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="dots-vertical" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.2" />
          <stop offset="0.25" stopColor="#fff" stopOpacity="1" />
          <stop offset="0.8" stopColor="#fff" stopOpacity="1" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.3" />
        </linearGradient>
        <mask id="dots-mask-edges" maskContentUnits="objectBoundingBox">
          <rect width="1" height="1" fill="url(#dots-edges)" />
        </mask>
        <mask id="dots-mask-vertical" maskContentUnits="objectBoundingBox">
          <rect width="1" height="1" fill="url(#dots-vertical)" />
        </mask>
        <mask id="dots-mask-noise">
          <rect width="100%" height="100%" filter="url(#dots-noise)" />
        </mask>
        <mask id="dots-mask-noise-hi">
          <rect width="100%" height="100%" filter="url(#dots-noise-hi)" />
        </mask>
      </defs>
      <g mask="url(#dots-mask-vertical)">
        <g mask="url(#dots-mask-edges)">
          <rect width="100%" height="100%" fill="url(#dots-sm)" mask="url(#dots-mask-noise)" />
          <rect width="100%" height="100%" fill="url(#dots-lg)" mask="url(#dots-mask-noise-hi)" />
        </g>
      </g>
    </svg>
  );
}
