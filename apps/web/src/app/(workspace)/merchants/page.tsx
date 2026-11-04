"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadMerchants, type MerchantItem } from "@/lib/workspace/client";

export default function MerchantsPage() {
  const [items, setItems] = useState<MerchantItem[]>([]);
  const [configured, setConfigured] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { const result = await loadMerchants(); setItems(result.items); setConfigured(result.configured); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Trusted merchant mappings unavailable."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    loadMerchants().then((result) => { if (active) { setItems(result.items); setConfigured(result.configured); } })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Trusted merchant mappings unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const filtered = useMemo(() => items.filter((item) => `${item.internal_merchant_id} ${item.paypal_merchant_id}`.toLowerCase().includes(query.toLowerCase())), [items, query]);
  return <section className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-accent">Server-controlled identities</p><h1 className="mt-2 text-3xl font-semibold">Trusted Merchants</h1><p className="mt-2 max-w-2xl text-sm text-muted">Payment payees are resolved from protected server configuration. Proposal or browser input cannot replace this mapping.</p></div><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-xl border border-border px-4 py-2 text-sm">Refresh</button></header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    <section className="rounded-2xl border border-border bg-surface p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Trusted mapping status</h2><p className="mt-1 text-sm text-muted">{configured ? `${items.length} server-configured mapping${items.length === 1 ? "" : "s"}.` : "No valid trusted merchant registry is configured."}</p></div><span className={`rounded-full border px-3 py-1 text-xs font-semibold ${configured ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-300" : "border-amber-500/40 text-amber-700 dark:text-amber-300"}`}>{configured ? "CONFIGURED" : "UNAVAILABLE"}</span></div></section>
    <label className="block max-w-md space-y-1 text-sm"><span>Search trusted mappings</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Internal or PayPal merchant ID" className="w-full rounded-xl border border-border bg-background px-3 py-2.5" /></label>
    {loading ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Loading merchant registry…</p> : filtered.length === 0 ? <div className="rounded-2xl border border-border bg-surface p-6"><p className="font-semibold">{configured ? "No mappings match" : "No trusted merchants configured"}</p><p className="mt-2 text-sm text-muted">Registry updates are managed through protected API environment configuration, not this browser.</p></div> : <div className="overflow-x-auto rounded-2xl border border-border bg-surface"><table className="w-full min-w-[620px] text-left text-sm"><thead><tr className="border-b border-border text-muted"><th className="px-4 py-3">Internal merchant ID</th><th className="px-4 py-3">PayPal merchant ID</th><th className="px-4 py-3">Trust source</th><th className="px-4 py-3">Provider verification</th></tr></thead><tbody className="divide-y divide-border">{filtered.map((item) => <tr key={item.internal_merchant_id}><th scope="row" className="px-4 py-4 font-medium">{item.internal_merchant_id}</th><td className="px-4 py-4 font-mono text-xs">{item.paypal_merchant_id}</td><td className="px-4 py-4">Server configuration</td><td className="px-4 py-4">{item.provider_live_verified ? "Live verified" : "Mapping configured; not reverified here"}</td></tr>)}</tbody></table></div>}
  </section>;
}
