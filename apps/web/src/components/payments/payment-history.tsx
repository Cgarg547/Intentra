"use client";

import { ArrowUpRight, Clock3, CreditCard, RefreshCw } from "lucide-react";
import type { PaymentAttempt } from "@/lib/payments/client";

type Props = {
  payments: PaymentAttempt[];
  loading: boolean;
  working: boolean;
  error: string | null;
  onRefresh: () => void;
  onInspect: (attemptId: string) => void;
};

function formatAmount(amount: string, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(Number(amount));
}

function statusStyle(state: string) {
  const normalized = state.toUpperCase();

  if (normalized === "CAPTURED" || normalized === "COMPLETED") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (normalized === "UNKNOWN" || normalized === "FAILED") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }

  if (normalized === "PENDING") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-border bg-surface-muted text-foreground";
}

function StatusBadge({ state }: { state: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${statusStyle(state)}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {state.replaceAll("_", " ")}
    </span>
  );
}

export function PaymentHistory({
  payments,
  loading,
  working,
  error,
  onRefresh,
  onInspect,
}: Props) {
  return (
    <section className="rounded-3xl border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-accent">
            <CreditCard size={15} aria-hidden="true" />
            Transaction activity
          </div>

          <h2 className="text-xl font-semibold">Payment history</h2>

          <p className="mt-2 text-sm leading-6 text-muted">
            Recorded payment attempts and provider outcomes.
            Buyer approval and payment capture are separate steps.
          </p>
        </div>

        <button
          type="button"
          disabled={working || loading}
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-colors hover:bg-surface-muted disabled:opacity-50"
        >
          <RefreshCw size={15} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {loading ? (
        <div role="status" className="mt-6 space-y-3">
          <div className="h-16 animate-pulse rounded-xl bg-surface-muted" />
          <div className="h-16 animate-pulse rounded-xl bg-surface-muted" />
          <span className="sr-only">Loading payment history</span>
        </div>
      ) : payments.length === 0 ? (
        error ? null : (
          <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface-muted p-8 text-center">
            <Clock3 className="mx-auto text-muted" size={28} aria-hidden="true" />
            <h3 className="mt-3 font-semibold">No payment activity yet</h3>
            <p className="mt-2 text-sm text-muted">
              Payment attempts will appear here after checkout preparation.
            </p>
          </div>
        )
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs font-semibold uppercase tracking-wider text-muted">
                <th scope="col" className="px-3 py-4">Merchant</th>
                <th scope="col" className="px-3 py-4">Amount</th>
                <th scope="col" className="px-3 py-4">Payment status</th>
                <th scope="col" className="px-3 py-4">Buyer approval</th>
                <th scope="col" className="px-3 py-4">Created</th>
                <th scope="col" className="px-3 py-4 text-right">Details</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {payments.map((payment) => (
                <tr
                  key={payment.attempt_id}
                  className="transition-colors hover:bg-surface-muted"
                >
                  <th scope="row" className="px-3 py-5">
                    <div className="font-semibold text-foreground">
                      {payment.merchant_id}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-muted">
                      {payment.attempt_id.slice(0, 8)}
                    </div>
                  </th>

                  <td className="px-3 py-5 font-semibold tabular-nums">
                    {formatAmount(payment.amount, payment.currency)}
                  </td>

                  <td className="px-3 py-5">
                    <StatusBadge state={payment.attempt_state} />
                  </td>

                  <td className="px-3 py-5">
                    <StatusBadge state={payment.approval_state ?? "NOT_STARTED"} />
                  </td>

                  <td className="px-3 py-5 text-muted">
                    {new Date(payment.created_at).toLocaleDateString()}
                  </td>

                  <td className="px-3 py-5 text-right">
                    <button
                      type="button"
                      disabled={working}
                      onClick={() => onInspect(payment.attempt_id)}
                      className="inline-flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-xs font-semibold transition-colors hover:bg-surface-muted disabled:opacity-50"
                    >
                      View
                      <ArrowUpRight size={14} aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-muted">
        Payment attempts are not proof of completed transactions.
        Only verified capture outcomes should be treated as successful payments.
      </p>
    </section>
  );
}

