import Link from "next/link";
import { Logo } from "./Logo";
import { ArrowRight } from "./icons";

const LINKS = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Review Queue", href: "#review-queue" },
  { label: "Results", href: "#results" },
  { label: "Security", href: "#security" },
  { label: "FAQ", href: "#faq" },
];

export function Nav() {
  return (
    <header className="border-b border-border bg-background">
      <div className="relative mx-auto flex h-[73px] max-w-[1190px] items-center justify-between px-4 min-[1222px]:px-0">
        <Link href="/" aria-label="Concours home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="absolute left-1/2 hidden -translate-x-1/2 lg:block">
          <ul className="flex items-center gap-[29px]">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  className="text-[15px] font-medium tracking-[-0.01em] text-subtle transition-colors duration-150 hover:text-foreground"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        {/* Primary button from the product: light fill on the dark canvas. */}
        <a
          href="#contact"
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-foreground pr-4 pl-5 text-[14px] font-medium text-background shadow-[inset_0_-1px_0_rgb(0_0_0/0.15),0_1px_0_rgb(255_255_255/0.08)] transition-[background-color,transform] duration-150 hover:bg-white active:scale-[0.98]"
        >
          Get in touch
          <ArrowRight className="size-4" />
        </a>
      </div>
    </header>
  );
}
