"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { getCurrentUser } from "@/lib/auth/client";
import { readWorkspacePreferences, saveWorkspacePreferences, type WorkspacePreferences } from "@/lib/workspace/preferences";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<WorkspacePreferences>({ analyticsCurrency: "ALL" });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { getCurrentUser().then((user) => { setOwnerId(user.id); setPrefs(readWorkspacePreferences(user.id)); }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Sign in to manage preferences.")); }, []);
  function updateCurrency(value: string) {
    const next = { analyticsCurrency: value };
    setPrefs(next); setSaved(false);
    if (ownerId) { try { saveWorkspacePreferences(ownerId, next); setSaved(true); } catch { setError("This browser could not save the preference."); } }
  }
  return <section className="space-y-6"><header><p className="page-kicker">Workspace preferences</p><h1 className="page-title mt-2 text-3xl">Settings</h1><p className="mt-2 max-w-2xl text-sm text-muted">Analytics currency is saved for your account in this browser; appearance is a browser preference. Neither changes contract currency, authorization, or payment amounts.</p></header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    <section className="divide-y divide-border rounded-2xl border border-border bg-surface"><div className="p-5"><h2 className="font-semibold">Appearance</h2><p className="mt-1 text-sm text-muted">Choose a visual theme; INTENTRA remembers the selection in this browser.</p><label className="mt-4 block max-w-sm space-y-1 text-sm"><span>Theme</span><select aria-label="Appearance preference" value={theme ?? "system"} onChange={(event) => setTheme(event.target.value)} className="w-full rounded-xl border border-border bg-background px-3 py-2.5"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option><option value="contrast">High contrast</option></select></label></div>
      <div className="p-5"><h2 className="font-semibold">Analytics display preference</h2><p className="mt-1 text-sm text-muted">Choose the default currency filter for transaction analytics. No exchange rate conversion is performed.</p><label className="mt-4 block max-w-sm space-y-1 text-sm"><span>Default analytics currency filter</span><select disabled={!ownerId} value={prefs.analyticsCurrency} onChange={(event) => updateCurrency(event.target.value)} className="w-full rounded-xl border border-border bg-background px-3 py-2.5 disabled:opacity-50"><option value="ALL">All currencies</option>{["USD", "CAD", "EUR", "GBP", "AUD", "JPY"].map((code) => <option key={code}>{code}</option>)}</select></label>{saved && <p role="status" className="mt-2 text-sm text-emerald-700 dark:text-emerald-300">Preference saved on this device for your account.</p>}</div>
      <div className="p-5"><h2 className="font-semibold">Notifications</h2><p className="mt-1 text-sm text-muted">No notification delivery channels are configured. INTENTRA does not show controls for unsupported preferences.</p></div>
    </section>
  </section>;
}
