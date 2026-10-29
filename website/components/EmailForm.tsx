"use client";

import { useState } from "react";
import { ArrowRight } from "./icons";

// Not wired to a backend yet: submitting only confirms locally.
export function EmailForm() {
  const [sent, setSent] = useState(false);

  return (
    <div className="relative mx-auto w-full max-w-[533px]">
      {/* Tray behind the lower half of the field, carrying the promise line. */}
      <div className="absolute inset-x-0 top-[32px] bottom-0 rounded-b-2xl rounded-t-xl bg-gradient-to-b from-card-2 to-card/40" />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSent(true);
        }}
        className="relative mx-[5px] flex flex-col gap-[5px] rounded-xl border border-border-strong bg-card-2 p-[5px] shadow-[0_10px_30px_-12px_rgb(129_140_248/0.35)] transition-colors duration-150 focus-within:border-[#3a3a40] sm:h-[62px] sm:flex-row sm:items-center sm:pl-[18px]"
      >
        <label htmlFor="work-email" className="sr-only">
          Work email
        </label>
        <input
          id="work-email"
          type="email"
          required
          autoComplete="email"
          placeholder="Enter your work email"
          className="h-12 min-w-0 flex-1 bg-transparent px-3 sm:h-full sm:px-0 text-[17px] tracking-[-0.01em] text-foreground outline-none placeholder:text-muted"
        />
        <button
          type="submit"
          className="bg-brand-x inline-flex h-[50px] shrink-0 items-center justify-center gap-2 rounded-[10px] px-[22px] text-[16px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          {sent ? "Thanks, we'll be in touch" : "Book a demo"}
          {!sent && <ArrowRight className="size-[17px]" />}
        </button>
      </form>
      <p className="relative px-4 pt-[16px] pb-[18px] text-center text-[13.5px] text-muted">
        Your first model and review queue <span className="font-medium text-foreground">on day one,</span> from your
        own transactions.
      </p>
    </div>
  );
}
