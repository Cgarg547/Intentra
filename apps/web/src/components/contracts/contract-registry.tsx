
"use client";

import { useEffect, useMemo, useState } from "react";
import { ContractInspector } from "./contract-inspector";

import { ContractCreateForm } from "./contract-create-form";

import { ContractOverview } from "./contract-overview";

import {
  Search,
  RefreshCw,
} from "lucide-react";

import { approveContract, createContract, listContracts, revokeContract } from "@/lib/contracts/client";
import type {
  ContractStatus,
  IntentContract,
} from "@/lib/contracts/types";

type Filter = "ALL" | ContractStatus;

function formatAmount(contract: IntentContract) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: contract.currency,
  }).format(Number(contract.maximum_amount));
}

export function ContractRegistry() {
  const [liveContracts, setLiveContracts] = useState<IntentContract[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [merchantId, setMerchantId] = useState("");
  const [maximumAmount, setMaximumAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

useEffect(() => {
  let active = true;

  async function fetchContracts() {
    try {
      const result = await listContracts(100, 0);

      if (!active) return;

      setLiveContracts(result.items);
      setTotal(result.total);
      setError(null);
    } catch (err) {
      if (!active) return;

      setLiveContracts([]);
      setTotal(0);
      setSelectedId(null);
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load contracts.",
      );
    } finally {
      if (active) {
        setLoading(false);
      }
    }
  }

  void fetchContracts();

  return () => {
    active = false;
  };
}, [refreshKey]);

  useEffect(() => {
    function onAuthChanged() {
      setSelectedId(null);
      setRefreshKey((value) => value + 1);
    }

    window.addEventListener("intentra:auth-changed", onAuthChanged);

    return () => {
      window.removeEventListener(
        "intentra:auth-changed",
        onAuthChanged,
      );
    };
  }, []);

  const contracts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return liveContracts.filter((contract) => {
      const matchesStatus =
        filter === "ALL" || contract.status === filter;

      const matchesSearch = [
        contract.id,
        contract.merchant_id,
        contract.currency,
        contract.status,
      ].some((value) => value.toLowerCase().includes(query));

      return matchesStatus && matchesSearch;
    });
  }, [liveContracts, search, filter]);

  const selected = liveContracts.find(
    (contract) => contract.id === selectedId,
  );

  function refreshContracts() {
    setLoading(true);
    setError(null);
    setRefreshKey((value) => value + 1);
  }

  async function submitContract(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setActionError(null);
    try {
      const created = await createContract({ merchant_id: merchantId.trim(), maximum_amount: maximumAmount, currency });
      setMerchantId(""); setMaximumAmount(""); setSelectedId(created.id); refreshContracts();
    } catch (err) { setActionError(err instanceof Error ? err.message : "Unable to create contract."); }
    finally { setSaving(false); }
  }

  async function updateContract(action: "approve" | "revoke") {
    if (!selected) return;
    if (action === "revoke" && !window.confirm(`Revoke the contract for ${selected.merchant_id}? New payments will be blocked.`)) return;
    setSaving(true); setActionError(null);
    try {
      if (action === "approve") await approveContract(selected.id, selected.version);
      else await revokeContract(selected.id, selected.version);
      refreshContracts();
    } catch (err) { setActionError(err instanceof Error ? err.message : "Unable to update contract."); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-6">
      <ContractOverview
        contracts={liveContracts}
        loading={loading}
        error={error}
      />

      <section className="rounded-2xl border border-border bg-surface p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              Contract registry
            </h2>

            <p className="mt-1 text-sm text-muted">
              Explore human-governed spending agreements
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-border px-3 py-1 text-xs text-muted">
              Authenticated account records
            </span>

            <button
              type="button"
              onClick={refreshContracts}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                aria-hidden="true"
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <label className="relative min-w-52 flex-1">
            <span className="sr-only">Search contracts</span>

            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted"
            />

            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search merchant, contract ID, status..."
              className="w-full rounded-xl border border-border bg-background py-2.5 pl-10 pr-3 text-sm text-foreground"
            />
          </label>

          <label>
            <span className="sr-only">
              Filter contracts by status
            </span>

            <select
              value={filter}
              onChange={(event) =>
                setFilter(event.target.value as Filter)
              }
              className="rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground"
            >
              <option value="ALL">All statuses</option>
              <option value="APPROVED">Approved</option>
              <option value="DRAFT">Draft</option>
              <option value="REVOKED">Revoked</option>
            </select>
          </label>
        </div>

        {loading && (
          <p role="status" className="mt-5 text-sm text-muted">
            Loading contracts...
          </p>
        )}

        {error && (
          <div
            role="alert"
            className="mt-5 rounded-xl border border-border p-4"
          >
            <p className="text-sm text-red-500">{error}</p>

            <div className="mt-3 flex gap-4 text-sm">
              <button
                type="button"
                onClick={refreshContracts}
                className="font-medium text-accent underline"
              >
                Try again
              </button>

              <a
                href="/account"
                className="font-medium text-foreground underline"
              >
                Account
              </a>
            </div>
          </div>
        )}

        {!loading && !error && (
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>
              Showing {contracts.length} matching contracts
              {total > liveContracts.length
                ? ` from the first ${liveContracts.length} of ${total} records`
                : ` of ${total} total records`}
            </span>

            {total > 100 && (
              <span>
                Search and status counts currently cover the first
                100 contracts only.
              </span>
            )}
          </div>
        )}

        {!error && (
          <div className="mt-5 overflow-x-auto">
            <table className="financial-table w-full min-w-[700px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-muted text-muted">
                  <th scope="col" className="px-3 py-3">
                    Merchant
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Maximum amount
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Version
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Created
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Details
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {!loading &&
                  contracts.map((contract) => (
                    <tr key={contract.id}>
                      <th
                        scope="row"
                        className="px-3 py-5 font-semibold text-foreground"
                      >
                        {contract.merchant_id}
                      </th>

                      <td className="px-3 py-5 font-semibold tabular-nums text-foreground">
                        {formatAmount(contract)}
                      </td>

                      <td className="px-3 py-4">
                        <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                          contract.status === "APPROVED"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                            : contract.status === "DRAFT"
                              ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                              : "border-rose-500/20 bg-rose-500/10 text-rose-700"
                        }`}>
                          {contract.status}
                        </span>
                      </td>

                      <td className="px-3 py-4 text-muted">
                        v{contract.version}
                      </td>

                      <td className="px-3 py-4 text-muted">
                        {new Date(
                          contract.created_at,
                        ).toLocaleDateString()}
                      </td>

                      <td className="px-3 py-4">
                        <button
                          type="button"
                          onClick={() => setSelectedId(contract.id)}
                          className="inline-flex items-center justify-center rounded-xl border border-border bg-surface px-4 py-2 text-xs font-semibold text-foreground hover:bg-surface-muted"
                          aria-label={`Inspect contract for ${contract.merchant_id}`}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>

            {!loading && contracts.length === 0 && (
              <p className="py-10 text-center text-sm text-muted">
                {liveContracts.length === 0
                  ? "No contracts have been created yet."
                  : "No contracts match your search or filter."}
              </p>
            )}
          </div>
        )}
      </section>

      <ContractCreateForm
        merchantId={merchantId}
        maximumAmount={maximumAmount}
        currency={currency}
        saving={saving}
        error={actionError}
        onMerchantChange={setMerchantId}
        onAmountChange={setMaximumAmount}
        onCurrencyChange={setCurrency}
        onSubmit={submitContract}
      />

      {!loading && !error && selected && (
        <ContractInspector
          contract={selected}
          saving={saving}
          onClose={() => setSelectedId(null)}
          onApprove={() => void updateContract("approve")}
          onRevoke={() => void updateContract("revoke")}
        />
      )}

    </div>
  );
}
