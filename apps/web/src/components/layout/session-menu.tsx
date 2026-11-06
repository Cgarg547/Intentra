"use client";

import Link from "next/link";
import { LogOut, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, getCurrentUser, logout, type AuthUser } from "@/lib/auth/client";

function initials(email: string) {
  return email.slice(0, 2).toUpperCase();
}

export function SessionMenu() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const load = () => getCurrentUser()
      .then((result) => { if (active) setUser(result); })
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) setUser(null);
        else setError("Account status is unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    void load();
    window.addEventListener("intentra:auth-changed", load);
    return () => { active = false; window.removeEventListener("intentra:auth-changed", load); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const closeOnOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", closeOnOutside); document.removeEventListener("keydown", closeOnEscape); };
  }, [open]);

  async function signOut() {
    setWorking(true);
    setError("");
    try {
      await logout();
      setUser(null);
      setOpen(false);
      window.dispatchEvent(new Event("intentra:auth-changed"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign out.");
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <div className="h-9 w-24 animate-pulse rounded-full bg-surface-muted" aria-label="Loading account" />;
  if (!user) return <Link href="/account" aria-label="Open account" className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-border bg-surface p-2 text-sm font-medium hover:bg-surface-muted sm:px-3"><UserRound size={16} aria-hidden="true" /><span className="hidden sm:inline">Sign in</span></Link>;

  return <div ref={menuRef} className="relative">
    <button type="button" aria-label={`Account menu for ${user.email}`} aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((value) => !value)} className="flex max-w-48 items-center gap-2 rounded-xl border border-border bg-surface py-1.5 pl-1.5 pr-1.5 text-left text-sm hover:bg-surface-muted sm:pr-3">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent text-[10px] font-bold text-accent-foreground">{initials(user.email)}</span>
      <span className="hidden truncate sm:inline">{user.email}</span>
    </button>
    {open && <div role="menu" className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-64 rounded-2xl border border-border bg-surface p-2 shadow-xl shadow-black/10">
      <div className="border-b border-border px-3 py-2.5"><p className="text-xs text-muted">Signed in as</p><p className="mt-1 truncate text-sm font-semibold">{user.email}</p></div>
      <Link role="menuitem" href="/account" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-surface-muted"><UserRound size={16} aria-hidden="true" />Account access</Link>
      <button type="button" role="menuitem" onClick={() => void signOut()} disabled={working} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-surface-muted disabled:opacity-50"><LogOut size={16} aria-hidden="true" />{working ? "Signing out…" : "Sign out"}</button>
      {error && <p role="alert" className="px-3 py-2 text-xs text-danger">{error}</p>}
    </div>}
  </div>;
}
