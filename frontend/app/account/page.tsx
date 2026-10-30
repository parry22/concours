"use client";

import { useEffect, useState } from "react";
import { Copy, KeyRound, LogOut, Trash2, UserPlus } from "lucide-react";
import { AppFrame } from "@/components/ProjectShell";
import { Alert, Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api, BASE_PATH, errorText, type ApiKey, type Me } from "@/lib/api";
import { account as copy } from "@/lib/copy";
import { fmtAgo } from "@/lib/format";

/** Who you are, API keys for the CLI, and (for owners) invites. */
export default function AccountPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [fresh, setFresh] = useState<ApiKey | null>(null);
  const [name, setName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const m = await api.me();
      setMe(m);
      setKeys(m.auth === "off" ? [] : await api.keys());
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function act(tag: string, fn: () => Promise<void>) {
    setBusy(tag);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <AppFrame>
      <div className="space-y-5">
        <PageHeader
          title={copy.title}
          actions={
            me?.auth === "required" ? (
              <Button variant="secondary" busy={busy === "logout"} onClick={() => void act("logout", async () => {
                await api.logout();
                window.location.assign(`${BASE_PATH}/login`);
              })}>
                <LogOut className="h-3.5 w-3.5" />
                {copy.signOut}
              </Button>
            ) : null
          }
        >
          {me ? copy.sub(me.email ?? copy.local, me.org_name) : null}
        </PageHeader>
        {error ? <Alert>{error}</Alert> : null}

        <Card title={copy.keysTitle} subtitle={copy.keysSub}>
          {!keys ? (
            <Skeleton className="h-24" />
          ) : me?.auth === "off" ? (
            <p className="text-[13px] text-muted">{copy.authOff}</p>
          ) : (
            <>
              {fresh?.token ? (
                <div className="mb-4 rounded-xl border border-border-strong bg-card-2 p-3.5">
                  <div className="text-[12px] font-medium">{copy.freshTitle}</div>
                  <div className="mt-2 flex items-center gap-2">
                    <code className="num min-w-0 flex-1 truncate rounded-lg bg-background px-2.5 py-2 text-[12px]">{fresh.token}</code>
                    <Button size="sm" variant="secondary" onClick={() => void navigator.clipboard?.writeText(fresh.token ?? "")}>
                      <Copy className="h-3.5 w-3.5" />
                      {copy.copy}
                    </Button>
                  </div>
                  <p className="num mt-2 text-[12px] text-muted">{copy.cliHint(origin)}</p>
                </div>
              ) : null}
              <ul className="divide-y divide-border">
                {keys.length === 0 ? <li className="py-2 text-[13px] text-muted">{copy.noKeys}</li> : null}
                {keys.map((k) => (
                  <li key={k.id} className="flex items-center gap-3 py-2.5">
                    <KeyRound className="h-4 w-4 shrink-0 text-muted" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-medium">{k.name}</span>
                      <span className="num block text-[11px] text-muted">
                        {k.prefix}… · {k.last_used_at ? copy.used(fmtAgo(k.last_used_at)) : copy.neverUsed}
                      </span>
                    </span>
                    <Button size="sm" variant="ghost" busy={busy === k.id} onClick={() => void act(k.id, async () => {
                      await api.revokeKey(k.id);
                      setKeys(await api.keys());
                    })} aria-label={copy.revoke}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
              <form
                className="mt-4 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void act("create", async () => {
                    setFresh(await api.createKey(name.trim() || "CLI"));
                    setName("");
                    setKeys(await api.keys());
                  });
                }}
              >
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder={copy.keyName}
                  className="h-9 min-w-0 flex-1 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] placeholder:text-muted" />
                <Button type="submit" busy={busy === "create"}>{copy.createKey}</Button>
              </form>
            </>
          )}
        </Card>

        {me?.role === "owner" && me.auth === "required" ? (
          <Card title={copy.inviteTitle} subtitle={copy.inviteSub}>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void act("invite", async () => {
                  const inv = await api.invite(inviteEmail.trim());
                  setInviteLink(`${origin}/login?invite=${encodeURIComponent(inv.token)}`);
                });
              }}
            >
              <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} type="email" placeholder={copy.inviteEmail}
                className="h-9 min-w-0 flex-1 rounded-lg border border-border-strong bg-card-2 px-3 text-[13px] placeholder:text-muted" />
              <Button type="submit" busy={busy === "invite"}>
                <UserPlus className="h-3.5 w-3.5" />
                {copy.invite}
              </Button>
            </form>
            {inviteLink ? (
              <div className="mt-3 flex items-center gap-2">
                <code className="num min-w-0 flex-1 truncate rounded-lg bg-card-2 px-2.5 py-2 text-[12px]">{inviteLink}</code>
                <Button size="sm" variant="secondary" onClick={() => void navigator.clipboard?.writeText(inviteLink)}>
                  <Copy className="h-3.5 w-3.5" />
                  {copy.copy}
                </Button>
              </div>
            ) : null}
          </Card>
        ) : null}
      </div>
    </AppFrame>
  );
}
