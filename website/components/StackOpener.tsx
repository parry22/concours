"use client";

import { useEffect } from "react";

// Opens the hero stack once: after the visitor first scrolls, as soon as the diagram is on screen. It never closes
// again. Does nothing when the reveal script is not armed (reduced motion), since the stack is then drawn open.

export function StackOpener() {
  useEffect(() => {
    if (!document.documentElement.classList.contains("reveal-ready")) return;
    const svgs = Array.from(document.querySelectorAll<SVGSVGElement>("svg.stack-armed"));
    if (!svgs.length) return;

    let io: IntersectionObserver | null = null;
    const open = () => {
      svgs.forEach((s) => s.classList.add("stack-open"));
      io?.disconnect();
    };
    const watch = () => {
      io = new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && open(), { threshold: 0.25 });
      svgs.forEach((s) => io!.observe(s));
    };

    // A page restored mid-scroll counts as already scrolled.
    if (window.scrollY > 0) {
      watch();
    } else {
      window.addEventListener("scroll", watch, { once: true, passive: true });
    }
    return () => {
      window.removeEventListener("scroll", watch);
      io?.disconnect();
    };
  }, []);

  return null;
}
