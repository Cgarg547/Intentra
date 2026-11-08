"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadMerchants, type MerchantItem } from "@/lib/workspace/client";
import { MerchantRegistry } from "@/components/merchants/merchant-registry";

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
  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Payment governance
          </p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Trusted Merchants
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Manage visibility into server-controlled merchant
            identities and trusted PayPal recipient mappings.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded-xl border border-border bg-surface px-5 py-3 text-sm font-semibold transition-colors hover:bg-surface-muted disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh registry"}
        </button>
      </header>

      {error && (
        <p
          role="alert"
          className="rounded-xl border border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600"
        >
          {error}
        </p>
      )}

      <MerchantRegistry
        items={items}
        filtered={filtered}
        configured={configured}
        loading={loading}
        query={query}
        onQueryChange={setQuery}
      />
    </section>
  );
}
