"use client";

import { Wallet, ShieldCheck, TrendingUp } from "lucide-react";
import type { AnalyticsSummary } from "@/lib/workspace/client";

type BudgetRecord = AnalyticsSummary["budget_by_contract"][number];

type Props = {
  budgets: BudgetRecord[];
};

function formatMoney(amount: string, currency: string) {
  const value = Number(amount);

  if (!Number.isFinite(value)) {
    return `${amount} ${currency}`;
  }

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
    }).format(value);
  } catch {
    return `${amount} ${currency}`;
  }
}

function utilization(record: BudgetRecord) {
  const maximum = Number(record.maximum_amount);
  const consumed = Number(record.consumed_amount);

  if (
    !Number.isFinite(maximum) ||
    !Number.isFinite(consumed) ||
    maximum <= 0
  ) {
    return null;
  }

  return Math.max(
    0,
    Math.min(100, (consumed / maximum) * 100)
  );
}

export function BudgetUtilization({ budgets }: Props) {
  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-surface shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-6 sm:px-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Spending governance
          </p>

          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Contract budget utilization
          </h2>

          <p className="mt-2 text-sm leading-6 text-muted">
            Monitor spending limits and available balances
            across your recorded intent contracts.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-2 text-xs font-semibold">
          <Wallet size={15} aria-hidden="true" />
          {budgets.length} contracts
        </span>
      </div>

      {budgets.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-16 text-center">
          <div className="flex size-16 items-center justify-center rounded-2xl bg-surface-muted text-muted">
            <Wallet size={28} aria-hidden="true" />
          </div>

          <h3 className="mt-5 text-lg font-semibold">
            No contract budgets available
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-muted">
            Contract budget information will appear here
            when intent contracts are available.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 p-6 lg:grid-cols-2 sm:p-8">
          {budgets.map((record) => {
            const percentage = utilization(record);

            return (
              <article
                key={record.contract_id}
                className="rounded-2xl border border-border bg-background p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-violet-500/10 text-violet-600">
                      <Wallet size={20} aria-hidden="true" />
                    </div>

                    <div className="min-w-0">
                      <h3 className="break-all text-base font-semibold">
                        {record.merchant_id}
                      </h3>

                      <p className="mt-1 text-xs text-muted">
                        Intent contract
                      </p>
                    </div>
                  </div>

                  <span className="rounded-full border border-border bg-surface-muted px-3 py-1.5 text-xs font-semibold">
                    {record.status.replaceAll("_", " ")}
                  </span>
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl bg-surface-muted p-4">
                    <p className="text-xs text-muted">
                      Contract limit
                    </p>

                    <p className="mt-2 text-xl font-bold tabular-nums">
                      {formatMoney(
                        record.maximum_amount,
                        record.currency
                      )}
                    </p>
                  </div>

                  <div className="rounded-xl bg-surface-muted p-4">
                    <p className="text-xs text-muted">
                      Consumed budget
                    </p>

                    <p className="mt-2 text-xl font-bold tabular-nums">
                      {formatMoney(
                        record.consumed_amount,
                        record.currency
                      )}
                    </p>
                  </div>
                </div>

                <div className="mt-6">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold">
                      Budget utilization
                    </span>

                    <span className="inline-flex items-center gap-1.5 text-sm font-bold tabular-nums text-accent">
                      <TrendingUp size={15} aria-hidden="true" />
                      {percentage === null
                        ? "Unavailable"
                        : `${percentage.toFixed(0)}%`}
                    </span>
                  </div>

                  <div
                    className="h-3 overflow-hidden rounded-full bg-surface-muted"
                    role="progressbar"
                    aria-label={`${record.merchant_id} budget utilization`}
                    aria-valuenow={percentage ?? undefined}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      className="h-full rounded-full bg-accent transition-all duration-500"
                      style={{
                        width: `${percentage ?? 0}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                  <span className="inline-flex items-center gap-2 text-sm text-muted">
                    <ShieldCheck
                      size={17}
                      className="text-emerald-600"
                      aria-hidden="true"
                    />
                    Remaining available budget
                  </span>

                  <span className="text-lg font-bold tabular-nums text-foreground">
                    {formatMoney(
                      record.remaining_amount,
                      record.currency
                    )}
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <div className="border-t border-border bg-surface-muted px-6 py-4 sm:px-8">
        <p className="text-xs leading-6 text-muted">
          Values are sourced from persisted contract budget
          records. Consumed budget is not necessarily captured
          revenue. A budget reservation does not establish
          buyer approval or successful payment.
        </p>
      </div>
    </section>
  );
}
