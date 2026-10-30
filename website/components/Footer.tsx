import { ArrowRight } from "./icons";
import { Logo, LogoMark } from "./Logo";

// Footer in the reference's layout. Links only point at sections that exist on this page; company details the
// repo does not record stay as visible placeholders, as the reference itself does. The reference's partner
// badges and "ask an AI about us" row are left out: Concours has neither.

const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Navigation",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Review queue", href: "#review-queue" },
      { label: "Results", href: "#results" },
      { label: "Security", href: "#security" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Get started",
    links: [
      { label: "Try with sample data", href: "/app/signup" },
      { label: "Start with your transactions", href: "/app/signup" },
      { label: "Sign in", href: "/app/login" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "[ Contact email ]", href: "#contact" },
      { label: "[ Company address ]", href: "#contact" },
      { label: "Privacy policy", href: "#" },
      { label: "Terms of service", href: "#" },
    ],
  },
];

/** Corner crosshair for the wordmark frame. */
function Cross({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 10 10" className={`absolute size-2.5 text-muted ${className}`} aria-hidden>
      <path d="M5 0v10M0 5h10" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

const TICKS_X = "bg-[repeating-linear-gradient(90deg,var(--border-strong)_0_1px,transparent_1px_6px)]";
const TICKS_Y = "bg-[repeating-linear-gradient(0deg,var(--border-strong)_0_1px,transparent_1px_6px)]";

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="grid gap-12 px-5 pt-12 pb-14 md:grid-cols-[1fr_auto] md:px-[54px] md:pt-[60px]">
        <div>
          <Logo />
          <p className="mt-10 max-w-[280px] text-[24px] leading-[1.2] font-semibold tracking-[-0.025em]">
            Fraud models that keep up with fraudsters.
          </p>
          <a
            href="/app/signup"
            className="bg-brand-x mt-7 inline-flex h-[50px] items-center gap-2 rounded-xl px-6 text-[16px] font-semibold text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
          >
            Get started
            <ArrowRight className="size-[17px]" />
          </a>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-14 gap-y-10 sm:grid-cols-3">
          {COLUMNS.map((c) => (
            <div key={c.title}>
              <h3 className="text-[16px] font-semibold">{c.title}</h3>
              <ul className="mt-5 space-y-3.5">
                {c.links.map((l) => (
                  <li key={l.label}>
                    <a href={l.href} className="text-[15px] text-subtle transition-colors duration-150 hover:text-foreground">
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>

      {/* Oversized wordmark in a ruled frame, fading out to the right as in the reference. */}
      <div className="border-t border-border px-3 py-3">
        <div className="relative px-4 py-8 md:px-10 md:py-12">
          <div aria-hidden className={`absolute inset-x-3 top-0 h-1.5 ${TICKS_X}`} />
          <div aria-hidden className={`absolute inset-x-3 bottom-0 h-1.5 ${TICKS_X}`} />
          <div aria-hidden className={`absolute inset-y-3 left-0 w-1.5 ${TICKS_Y}`} />
          <div aria-hidden className={`absolute inset-y-3 right-0 w-1.5 ${TICKS_Y}`} />
          <Cross className="-top-1 -left-1" />
          <Cross className="-top-1 -right-1" />
          <Cross className="-bottom-1 -left-1" />
          <Cross className="-right-1 -bottom-1" />
          <div className="flex items-center gap-[3vw] md:[mask-image:linear-gradient(90deg,#000_70%,transparent)]" aria-hidden>
            <LogoMark id="footer-logo" className="h-[clamp(40px,13vw,170px)] w-auto shrink-0 overflow-visible" />
            <span className="text-gradient text-[clamp(40px,15vw,200px)] leading-[0.9] font-semibold tracking-[-0.06em]">
              Concours
            </span>
          </div>
        </div>
      </div>
      <p className="border-t border-border px-5 py-5 text-center text-[13px] text-muted md:px-[54px]">
        © {new Date().getFullYear()} Concours
      </p>
    </footer>
  );
}
