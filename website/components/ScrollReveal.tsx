"use client";

import { useEffect } from "react";

// Fades each section's blocks in as they enter the viewport, with a short stagger inside a section. Elements are
// hidden only once html has .reveal-ready (set by an inline script before paint), so without JavaScript, or with
// reduced motion, everything stays visible.

export function ScrollReveal() {
  useEffect(() => {
    const root = document.documentElement;
    if (!root.classList.contains("reveal-ready")) return;

    const targets = Array.from(document.querySelectorAll<HTMLElement>("main section > *"));
    const bySection = new Map<Element, number>();
    for (const el of targets) {
      const section = el.parentElement!;
      const i = bySection.get(section) ?? 0;
      bySection.set(section, i + 1);
      el.style.setProperty("--reveal-delay", `${Math.min(i, 4) * 70}ms`);
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    targets.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return null;
}
