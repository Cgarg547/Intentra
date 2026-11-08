"use client";

import { useCallback, useEffect, useState } from "react";
import { loadSecurity, type SecuritySummary } from "@/lib/workspace/client";
import { SecurityOverview } from "@/components/security/security-overview";
import { SecurityControlPanels } from "@/components/security/security-control-panels";
import { SecurityBoundaries } from "@/components/security/security-boundaries";

export default function SecurityPage() {
  const [data, setData] = useState<SecuritySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await loadSecurity()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Security summary unavailable."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    loadSecurity().then((result) => { if (active) setData(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Security summary unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  return <section className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-accent">Access and controls</p><h1 className="mt-2 text-3xl font-semibold">Security Center</h1><p className="mt-2 max-w-2xl text-sm text-muted">Live account-scoped indicators from authentication, contracts, merchant configuration, policy decisions, and payment states.</p></div><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-xl border border-border px-4 py-2 text-sm">Refresh</button></header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    {loading && !data ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Loading security state…</p> : data && <>
      <SecurityOverview data={data} />
      <SecurityControlPanels data={data} />
      <SecurityBoundaries />
    </>}
  </section>;
}
