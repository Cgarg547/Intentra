"use client";

import { useMemo, useState } from "react";
import { Search, ShieldCheck, FileClock, ShieldX } from "lucide-react";
import { demoContracts } from "@/lib/contracts/demo-contracts";
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
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const contracts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return demoContracts.filter((contract) => {
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
  }, [search, filter]);

  const selected = demoContracts.find(
    (contract) => contract.id === selectedId
  );

  return (
    <div className="space-y-6">
      <section
        aria-label="Contract status summary"
        className="grid gap-4 sm:grid-cols-3"
      >
        {(["APPROVED", "DRAFT", "REVOKED"] as const).map((status) => {
          const Icon = statusIcons[status];

          return (
            <article
              key={status}
              className="rounded-2xl border border-border bg-surface p-5"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted">{status}</span>
                <Icon aria-hidden="true" className="h-5 w-5 text-accent" />
              </div>

              <p className="mt-4 text-3xl font-semibold text-foreground">
                {demoContracts.filter(
                  (contract) => contract.status === status
                ).length}
              </p>
            </article>
          );
        })}
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

          <span className="rounded-full border border-border px-3 py-1 text-xs text-muted">
            Simulated records — read only
          </span>
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
            <span className="sr-only">Filter contracts by status</span>
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

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-muted">
                <th scope="col" className="px-3 py-3">Merchant</th>
                <th scope="col" className="px-3 py-3">Maximum amount</th>
                <th scope="col" className="px-3 py-3">Status</th>
                <th scope="col" className="px-3 py-3">Version</th>
                <th scope="col" className="px-3 py-3">Created</th>
                <th scope="col" className="px-3 py-3">Details</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {contracts.map((contract) => (
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
                    {new Date(contract.created_at).toLocaleDateString()}
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

          {contracts.length === 0 && (
            <p className="py-10 text-center text-sm text-muted">
              No contracts match your search.
            </p>
          )}
        </div>
      </section>

      {selected && (
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
              ["Created", new Date(selected.created_at).toLocaleString()],
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
            This is a synthetic contract. Approval and revocation actions
            are intentionally disabled until authenticated backend
            integration is implemented.
          </p>
        </section>
      )}
    </div>
  );
}
