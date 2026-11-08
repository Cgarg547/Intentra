"use client";

import { ArrowUpRight, CreditCard, ShieldCheck } from "lucide-react";
import type { AnalyticsSummary } from "@/lib/workspace/client";

type Transaction = AnalyticsSummary["transactions"][number];

type Props = {
  transactions: Transaction[];
  total: number;
};

function formatMoney(amount: string, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(Number(amount));
  } catch {
    return `${amount} ${currency}`;
  }
}

function StatusBadge({ status }: { status: string | null }) {
  const value = status ?? "NOT_STARTED";

  const styles: Record<string, string> = {
    SUCCEEDED: "bg-emerald-500/10 text-emerald-700",
    CAPTURED: "bg-emerald-500/10 text-emerald-700",
    APPROVED: "bg-emerald-500/10 text-emerald-700",
    PENDING: "bg-amber-500/10 text-amber-700",
    EXECUTION_PENDING: "bg-amber-500/10 text-amber-700",
    UNKNOWN: "bg-orange-500/10 text-orange-700",
    FAILED: "bg-red-500/10 text-red-700",
    REVOKED: "bg-red-500/10 text-red-700",
    RESERVED: "bg-violet-500/10 text-violet-700",
  };

  return (
    <span
      className={`inline-flex max-w-full items-center rounded-full px-3 py-1.5 text-xs font-semibold ${
        styles[value] ?? "bg-surface-muted text-muted"
      }`}
      title={value}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function TransactionIntelligence({
  transactions,
  total,
}: Props) {
  return (
    <div>
      {transactions.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl bg-surface-muted px-6 py-14 text-center">
          <CreditCard
            size={28}
            className="text-muted"
            aria-hidden="true"
          />

          <h3 className="mt-4 text-base font-semibold">
            No matching transactions
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-muted">
            No stored payment attempts match your current
            search or filters.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="financial-table w-full min-w-[850px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-muted">
                <th scope="col" className="px-4 py-4">
                  Transaction
                </th>
                <th scope="col" className="px-4 py-4">
                  Merchant
                </th>
                <th scope="col" className="px-4 py-4">
                  Amount
                </th>
                <th scope="col" className="px-4 py-4">
                  Payment
                </th>
                <th scope="col" className="px-4 py-4">
                  Reservation
                </th>
                <th scope="col" className="px-4 py-4">
                  Buyer approval
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {transactions.map((item) => (
                <tr key={item.attempt_id}>
                  <th
                    scope="row"
                    className="px-4 py-5 font-medium"
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-muted">
                        <ArrowUpRight
                          size={17}
                          aria-hidden="true"
                        />
                      </span>

                      <div>
                        <p
                          className="font-mono text-xs font-semibold"
                          title={item.attempt_id}
                        >
                          {item.attempt_id.slice(0, 8)}…
                        </p>

                        <p className="mt-1 text-xs font-normal text-muted">
                          Payment attempt
                        </p>
                      </div>
                    </div>
                  </th>

                  <td className="px-4 py-5 font-medium">
                    {item.merchant_id}
                  </td>

                  <td className="px-4 py-5 font-semibold tabular-nums">
                    {formatMoney(item.amount, item.currency)}
                  </td>

                  <td className="px-4 py-5">
                    <StatusBadge status={item.state} />
                  </td>

                  <td className="px-4 py-5">
                    <StatusBadge status={item.reservation_state} />
                  </td>

                  <td className="px-4 py-5">
                    <StatusBadge status={item.approval_state} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-xs text-muted">
          Showing {transactions.length} of {total} recorded
          payment attempts
        </p>

        <span className="inline-flex items-center gap-2 text-xs text-muted">
          <ShieldCheck
            size={15}
            className="text-emerald-600"
            aria-hidden="true"
          />
          Owner-scoped records
        </span>
      </div>

      <p className="mt-3 text-xs leading-5 text-muted">
        Payment attempts do not necessarily represent
        completed transactions. Buyer approval and
        successful capture are separate outcomes.
      </p>
    </div>
  );
}
