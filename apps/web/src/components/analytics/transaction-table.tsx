"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { demoTransactions } from "@/lib/demo/financial-data";

type DecisionFilter = "All" | "Allowed" | "Blocked" | "Review";

export function TransactionTable() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<DecisionFilter>("All");

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();

    return demoTransactions.filter((transaction) => {
      const matchesDecision =
        filter === "All" || transaction.decision === filter;

      const matchesSearch = [
        transaction.id,
        transaction.agent,
        transaction.merchant,
        transaction.reason,
      ].some((value) => value.toLowerCase().includes(query));

      return matchesDecision && matchesSearch;
    });
  }, [search, filter]);

  return (
    <section className="rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Transaction intelligence
          </h2>
          <p className="mt-1 text-sm text-muted">
            Search and inspect simulated agent payment decisions
          </p>
        </div>

        <span className="rounded-full border border-border px-3 py-1 text-xs text-muted">
          Demo data
        </span>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <label className="relative min-w-52 flex-1">
          <span className="sr-only">Search transactions</span>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search transactions..."
            className="w-full rounded-xl border border-border bg-background py-2.5 pl-10 pr-3 text-sm text-foreground"
          />
        </label>

        <label>
          <span className="sr-only">Filter by decision</span>
          <select
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as DecisionFilter)
            }
            className="rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground"
          >
            <option value="All">All decisions</option>
            <option value="Allowed">Allowed</option>
            <option value="Blocked">Blocked</option>
            <option value="Review">Review</option>
          </select>
        </label>
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              <th scope="col" className="px-3 py-3 font-medium">Transaction</th>
              <th scope="col" className="px-3 py-3 font-medium">AI agent</th>
              <th scope="col" className="px-3 py-3 font-medium">Merchant</th>
              <th scope="col" className="px-3 py-3 text-right font-medium">Amount</th>
              <th scope="col" className="px-3 py-3 font-medium">Decision</th>
              <th scope="col" className="px-3 py-3 font-medium">Explanation</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-border">
            {filtered.map((transaction) => (
              <tr key={transaction.id}>
                <th scope="row" className="px-3 py-4 font-medium text-foreground">
                  {transaction.id}
                </th>
                <td className="px-3 py-4 text-muted">{transaction.agent}</td>
                <td className="px-3 py-4 text-muted">{transaction.merchant}</td>
                <td className="px-3 py-4 text-right font-medium text-foreground">
                  ${transaction.amount.toLocaleString("en-US")}
                </td>
                <td className="px-3 py-4">
                  <span className="rounded-md border border-border px-2 py-1 text-xs font-semibold text-foreground">
                    {transaction.decision}
                  </span>
                </td>
                <td className="px-3 py-4 text-muted">{transaction.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <p className="py-10 text-center text-sm text-muted">
            No transactions match your search or filters.
          </p>
        )}
      </div>

      <p className="mt-4 text-xs text-muted">
        Showing {filtered.length} of {demoTransactions.length} simulated transactions.
      </p>
    </section>
  );
}
