"use client";

import { PolicyEvaluationsChart } from "@/components/analytics/policy-evaluations-chart";

import { PaymentOutcomesChart } from "@/components/analytics/payment-outcomes-chart";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnalyticsOverview } from "@/components/analytics/analytics-overview";
import { loadAnalytics, type AnalyticsSummary } from "@/lib/workspace/client";
import { getCurrentUser } from "@/lib/auth/client";
import { readWorkspacePreferences } from "@/lib/workspace/preferences";
import { CapturedTrendsChart } from "@/components/analytics/captured-trends-chart";
import { BudgetUtilization } from "@/components/analytics/budget-utilization";
import { TransactionIntelligence } from "@/components/analytics/transaction-intelligence";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("ALL");
  const [currency, setCurrency] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { setLoading(true); setError(null); try { setData(await loadAnalytics()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Analytics unavailable."); } finally { setLoading(false); } }, []);
  useEffect(() => {
    let active = true;
    loadAnalytics().then((result) => { if (active) setData(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Analytics unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => { let active = true; getCurrentUser().then((user) => { if (active) setCurrency(readWorkspacePreferences(user.id).analyticsCurrency); }).catch(() => {}); return () => { active = false; }; }, []);
  const transactions = useMemo(() => (data?.transactions ?? []).filter((item) =>
    (stateFilter === "ALL" || item.state === stateFilter) && (currency === "ALL" || item.currency === currency)
    && `${item.attempt_id} ${item.merchant_id} ${item.state} ${item.reservation_state}`.toLowerCase().includes(query.toLowerCase())), [data, stateFilter, currency, query]);
  const currencies = [...new Set((data?.transactions ?? []).map((item) => item.currency))];
  return <section className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-accent">Owner-scoped records</p><h1 className="mt-2 text-3xl font-semibold">Analytics & transaction intelligence</h1><p className="mt-2 max-w-2xl text-sm text-muted">Aggregates come from saved reservations, payment outcomes, contract evaluations, and proposals. Amounts stay in their recorded currencies; no FX conversion is applied.</p></div><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-xl border border-border px-4 py-2 text-sm">Refresh</button></header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    {loading && !data ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Loading financial records…</p> : data && <>
      <AnalyticsOverview data={data} loading={loading} />
      <div className="grid gap-4 lg:grid-cols-2"><PaymentOutcomesChart rows={data.payment_states} /><PolicyEvaluationsChart decisions={data.policy_decisions} /></div>
      <BudgetUtilization budgets={data.budget_by_contract} />
      <CapturedTrendsChart rows={data.daily_captured} currency={currency} />
      <section className="overflow-hidden rounded-3xl border border-border bg-surface">
        <div className="border-b border-border px-6 py-6 sm:px-8">
          <p className="page-kicker">Transaction records</p>

          <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">
                Transaction intelligence
              </h2>

              <p className="mt-2 text-sm text-muted">
                Search and review persisted payment attempts.
                Amounts remain in their recorded currencies.
              </p>
            </div>

            <span className="rounded-full bg-surface-muted px-4 py-2 text-xs font-semibold text-muted">
              {data.transactions.length} recorded attempts
            </span>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <label className="min-w-56 flex-1 space-y-2">
              <span className="text-xs font-semibold text-muted">
                Search payment history
              </span>

              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Attempt, merchant, state"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm"
              />
            </label>

            <label className="space-y-2">
              <span className="block text-xs font-semibold text-muted">
                Currency
              </span>

              <select
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
                className="rounded-xl border border-border bg-background px-4 py-3 text-sm"
              >
                <option value="ALL">All currencies</option>
                {currencies.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="block text-xs font-semibold text-muted">
                Payment state
              </span>

              <select
                value={stateFilter}
                onChange={(event) => setStateFilter(event.target.value)}
                className="rounded-xl border border-border bg-background px-4 py-3 text-sm"
              >
                <option value="ALL">All states</option>
                {["PENDING", "UNKNOWN", "SUCCEEDED", "FAILED"].map(
                  (state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  )
                )}
              </select>
            </label>
          </div>
        </div>

        <div className="px-6 py-6 sm:px-8">
          <TransactionIntelligence
            transactions={transactions}
            total={data.transactions.length}
          />
        </div>
      </section>
    </>}
  </section>;
}
