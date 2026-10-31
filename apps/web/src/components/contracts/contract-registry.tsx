
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Search,
  ShieldCheck,
  FileClock,
  ShieldX,
  RefreshCw,
} from "lucide-react";

import { listContracts } from "@/lib/contracts/client";
import type {
  ContractStatus,
  IntentContract,
} from "@/lib/contracts/types";

type Filter = "ALL" | ContractStatus;

const statusIcons = {
  DRAFT: FileClock,
  APPROVED: ShieldCheck,
  REVOKED: ShieldX,
};

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

  return (
    <div className="space-y-6">
      <section
        aria-label="Contract status summary"
        className="grid gap-4 sm:grid-cols-3"
      >
        {(["APPROVED", "DRAFT", "REVOKED"] as const).map(
          (status) => {
            const Icon = statusIcons[status];

            const count = liveContracts.filter(
              (contract) => contract.status === status,
            ).length;

            return (
              <article
                key={status}
                className="rounded-2xl border border-border bg-surface p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">
                    {status}
                  </span>

                  <Icon
                    aria-hidden="true"
                    className="h-5 w-5 text-accent"
                  />
                </div>

                <p className="mt-4 text-3xl font-semibold text-foreground">
                  {loading ? "—" : error ? "—" : count}
                </p>
              </article>
            );
          },
        )}
      </section>

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
              Live PostgreSQL records — read only
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
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted">
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
                        className="px-3 py-4 font-medium text-foreground"
                      >
                        {contract.merchant_id}
                      </th>

                      <td className="px-3 py-4 text-foreground">
                        {formatAmount(contract)}
                      </td>

                      <td className="px-3 py-4">
                        <span className="rounded-md border border-border px-2 py-1 text-xs font-semibold text-foreground">
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
                          className="rounded-lg border border-border px-3 py-2 font-medium text-foreground hover:bg-surface-muted"
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

      {!loading && !error && selected && (
        <section
          aria-labelledby="contract-details-heading"
          className="rounded-2xl border border-border bg-surface p-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2
                id="contract-details-heading"
                className="text-xl font-semibold text-foreground"
              >
                Contract details
              </h2>

              <p className="mt-1 text-sm text-muted">
                Read-only policy inspection
              </p>
            </div>

            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="rounded-lg border border-border px-4 py-2 text-sm text-foreground"
            >
              Close details
            </button>
          </div>

          <dl className="mt-6 grid gap-5 sm:grid-cols-2">
            {[
              ["Contract ID", selected.id],
              ["Merchant", selected.merchant_id],
              ["Maximum amount", formatAmount(selected)],
              ["Lifecycle status", selected.status],
              ["Contract version", String(selected.version)],
              [
                "Created",
                new Date(selected.created_at).toLocaleString(),
              ],
              [
                "Approved",
                selected.approved_at
                  ? new Date(
                      selected.approved_at,
                    ).toLocaleString()
                  : "Not approved",
              ],
              [
                "Revoked",
                selected.revoked_at
                  ? new Date(
                      selected.revoked_at,
                    ).toLocaleString()
                  : "Not revoked",
              ],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-muted">{label}</dt>

                <dd className="mt-1 break-all text-sm font-medium text-foreground">
                  {value}
                </dd>
              </div>
            ))}
          </dl>

          <p className="mt-6 border-t border-border pt-4 text-xs text-muted">
            This contract is stored in PostgreSQL. Approval and
            revocation actions are not yet enabled in the frontend.
          </p>
        </section>
      )}
    </div>
  );
}
