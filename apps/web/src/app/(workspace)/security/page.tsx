"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { loadSecurity, type SecuritySummary } from "@/lib/workspace/client";

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
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Security indicators">{[
        ["Current session", data.current_session_valid ? "Valid" : "Unavailable", "HttpOnly session cookie checked by the API"],
        ["Active sessions", String(data.active_session_count), "Unexpired, unrevoked sessions for this account"],
        ["Trusted merchant mappings", String(data.trusted_merchant_count), "Loaded from server-side configuration"],
        ["Uncertain payments", String(data.unresolved_attempts), "UNKNOWN outcomes remain held for reconciliation"],
      ].map(([title, value, note]) => <article key={title} className="rounded-2xl border border-border bg-surface p-5"><p className="text-sm text-muted">{title}</p><p className="mt-3 text-2xl font-semibold">{loading ? "—" : value}</p><p className="mt-2 text-xs leading-5 text-muted">{note}</p></article>)}</section>
      <section className="grid gap-4 lg:grid-cols-2"><article className="rounded-2xl border border-border bg-surface p-6"><h2 className="font-semibold">Contract authorization</h2><p className="mt-1 text-sm text-muted">Contracts remain owner-controlled and versioned.</p><dl className="mt-4 grid grid-cols-3 gap-3">{["APPROVED", "DRAFT", "REVOKED"].map((state) => <div key={state} className="rounded-xl bg-surface-muted p-3"><dt className="text-xs text-muted">{state}</dt><dd className="mt-1 text-lg font-semibold">{data.contracts[state] ?? 0}</dd></div>)}</dl></article><article className="rounded-2xl border border-border bg-surface p-6"><h2 className="font-semibold">Policy outcomes</h2><p className="mt-1 text-sm text-muted">Deterministic evaluations recorded for this account.</p><dl className="mt-4 grid grid-cols-3 gap-3">{["ALLOW", "BLOCK", "REVIEW"].map((state) => <div key={state} className="rounded-xl bg-surface-muted p-3"><dt className="text-xs text-muted">{state}</dt><dd className="mt-1 text-lg font-semibold">{data.policy_decisions[state] ?? 0}</dd></div>)}</dl></article></section>
      <div className="rounded-2xl border border-border bg-surface p-5 text-sm"><h2 className="font-semibold">Control boundaries</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-muted"><li>AI proposals cannot approve contracts or capture funds.</li><li>Buyer approval and explicit capture are separate payment steps.</li><li>This view does not run anomaly detection; it surfaces recorded states only.</li></ul><div className="mt-4 flex gap-4"><Link href="/audit" className="text-accent underline">Inspect audit events</Link><Link href="/account" className="text-accent underline">Manage this session</Link></div></div>
    </>}
  </section>;
}
