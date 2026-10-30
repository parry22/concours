"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, Button, Logo, Spinner } from "@/components/ui";
import { api, errorText, type AuthConfig } from "@/lib/api";
import { auth as copy, brand } from "@/lib/copy";

// The work email typed on the website's hero form, handed over in this tab's sessionStorage (never in the URL).
// The website writes the same key (website/components/EmailForm.tsx).
const EMAIL_HANDOFF = "concours.signup-email";

export function SignIn({ start }: { start: "login" | "signup" }) {
  return (
    <Suspense fallback={null}>
      <Login start={start} />
    </Suspense>
  );
}

/**
 * Sign in, or create an account (/signup starts there). The very first visit creates the owner account; an invite
 * link (?invite=) creates a teammate's; with open sign-up (CONCOURS_SIGNUP=open) anyone creates their own workspace.
 */
function Login({ start }: { start: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get("invite");
  const next = params.get("next") || "/";
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [mode, setMode] = useState<"login" | "signup">(invite ? "signup" : start);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const handed = sessionStorage.getItem(EMAIL_HANDOFF);
      if (handed) setEmail(handed);
    } catch {}
  }, []);

  useEffect(() => {
    api
      .authConfig()
      .then((c) => {
        setCfg(c);
        if (c.auth === "off") router.replace(next);
        else if (c.first_run) setMode("signup");
        else if (!c.can_signup && !invite) setMode("login");
      })
      .catch((e) => setError(errorText(e)));
  }, [router, next, invite]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await api.login(email, password);
      else await api.signup({ email, password, name, org_name: org, invite });
      try {
        sessionStorage.removeItem(EMAIL_HANDOFF);
      } catch {}
      router.replace(next.startsWith("/") && !/^\/(login|signup)/.test(next) ? next : "/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  const first = cfg?.first_run;
  const canSignup = Boolean(invite) || cfg?.can_signup;

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-[380px]">
        <div className="mb-8 flex items-center gap-2">
          <Logo />
          <span className="text-[15px] font-semibold tracking-[-0.01em]">{brand.name}</span>
        </div>
        <h1 className="text-[24px] font-semibold tracking-[-0.02em]">{mode === "login" ? copy.signInTitle : first ? copy.firstTitle : copy.joinTitle}</h1>
        <p className="mt-1.5 text-[14px] leading-relaxed text-subtle">{mode === "login" ? copy.signInSub : first ? copy.firstSub : invite ? copy.joinSub : copy.openSub}</p>

        {!cfg && !error ? (
          <div className="mt-8 flex items-center gap-2 text-[13px] text-muted">
            <Spinner className="h-4 w-4" />
            {copy.loading}
          </div>
        ) : (
          <form onSubmit={submit} className="mt-7 space-y-3.5">
            {mode === "signup" ? (
              <>
                <Input label={copy.name} value={name} onChange={setName} autoComplete="name" />
                {!invite ? <Input label={copy.org} value={org} onChange={setOrg} placeholder={copy.orgPlaceholder} autoComplete="organization" /> : null}
              </>
            ) : null}
            <Input label={copy.email} value={email} onChange={setEmail} type="email" autoComplete="email" required />
            <Input
              label={copy.password}
              value={password}
              onChange={setPassword}
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              hint={mode === "signup" ? copy.passwordHint : undefined}
              minLength={mode === "signup" ? 10 : undefined}
            />
            {error ? <Alert>{error}</Alert> : null}
            <Button type="submit" size="lg" busy={busy} className="w-full">
              {mode === "login" ? copy.signIn : copy.create}
            </Button>
          </form>
        )}

        {cfg && !first && !invite ? (
          <p className="mt-6 text-[13px] text-muted">
            {mode === "login" ? (
              canSignup ? (
                <>
                  {copy.noAccount}{" "}
                  <button className="font-medium text-foreground underline underline-offset-2" onClick={() => setMode("signup")}>
                    {copy.create}
                  </button>
                </>
              ) : (
                copy.askOwner
              )
            ) : (
              <>
                {copy.haveAccount}{" "}
                <button className="font-medium text-foreground underline underline-offset-2" onClick={() => setMode("login")}>
                  {copy.signIn}
                </button>
              </>
            )}
          </p>
        ) : null}
      </div>
    </main>
  );
}

function Input({ label, value, onChange, hint, ...rest }: { label: string; value: string; onChange: (v: string) => void; hint?: string } & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-medium text-muted">{label}</span>
      <input
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full rounded-xl border border-border-strong bg-card-2 px-3.5 text-[14px] placeholder:text-muted hover:border-[#3a3a40] focus:border-accent/70"
      />
      {hint ? <span className="mt-1.5 block text-[12px] text-muted">{hint}</span> : null}
    </label>
  );
}
