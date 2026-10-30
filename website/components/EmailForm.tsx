"use client";

import { useState } from "react";
import { ArrowRight } from "./icons";

// The sign-up page reads this key and fills in the email (frontend/components/SignIn.tsx). Same origin, same tab.
const EMAIL_HANDOFF = "concours.signup-email";

// The main call to action: the typed work email goes on to the app's sign-up page.
export function EmailForm() {
  const [sent, setSent] = useState(false);

  return (
    <div className="relative mx-auto w-full max-w-[533px]">
      {/* Tray behind the lower half of the field, carrying the promise line. */}
      <div className="absolute inset-x-0 top-[32px] bottom-0 rounded-b-2xl rounded-t-xl bg-gradient-to-b from-card-2 to-card/40" />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const email = new FormData(e.currentTarget).get("email");
          try {
            sessionStorage.setItem(EMAIL_HANDOFF, String(email ?? ""));
          } catch {}
          setSent(true);
          window.location.assign("/app/signup");
        }}
        className="relative mx-[5px] flex flex-col gap-[5px] rounded-xl border border-border-strong bg-card-2 p-[5px] shadow-[0_10px_30px_-12px_rgb(129_140_248/0.35)] transition-[border-color,box-shadow] duration-150 focus-within:border-accent/60 focus-within:ring-[3px] focus-within:ring-accent/15 sm:h-[62px] sm:flex-row sm:items-center sm:pl-[18px]"
      >
        <label htmlFor="work-email" className="sr-only">
          Work email
        </label>
        <input
          id="work-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="Enter your work email"
          // Full width and fixed height when stacked; flex-1 only in the row, where it would otherwise squash the height.
          className="h-[52px] w-full min-w-0 bg-transparent px-4 text-[17px] tracking-[-0.01em] text-foreground outline-none placeholder:text-muted focus-visible:outline-none sm:h-full sm:w-auto sm:flex-1 sm:px-0"
        />
        <button
          type="submit"
          className="bg-brand-x inline-flex h-[50px] shrink-0 items-center justify-center gap-2 rounded-[10px] px-[22px] text-[16px] font-semibold tracking-[-0.01em] text-accent-ink transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.98]"
        >
          {sent ? "Opening sign-up" : "Get started"}
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
