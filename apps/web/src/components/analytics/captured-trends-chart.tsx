"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, ShieldCheck } from "lucide-react";

import type { AnalyticsSummary } from "@/lib/workspace/client";

type CapturedRow = AnalyticsSummary["daily_captured"][number];

type Props = {
  rows: CapturedRow[];
  currency: string;
};

function formatMoney(value: number, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(value);
}

export function CapturedTrendsChart({ rows, currency }: Props) {
  const filtered = useMemo(
    () =>
      rows
        .filter(
          (row) =>
            currency === "ALL" || row.currency === currency
        )
        .sort((a, b) => a.date.localeCompare(b.date)),
    [rows, currency]
  );

  const currencies = [...new Set(filtered.map((row) => row.currency))];

  const hasMultipleCurrencies = currencies.length > 1;

  const chartCurrency =
    currency !== "ALL"
      ? currency
      : currencies.length === 1
        ? currencies[0]
        : null;

  const chartData = useMemo(() => {
    if (!chartCurrency) return [];

    const daily = new Map<string, number>();

    for (const row of filtered) {
      if (row.currency !== chartCurrency) continue;

      daily.set(
        row.date,
        (daily.get(row.date) ?? 0) + Number(row.amount)
      );
    }

    return [...daily.entries()].map(([date, amount]) => ({
      date,
      amount,
    }));
  }, [filtered, chartCurrency]);

  const totalCaptured = chartData.reduce(
    (sum, row) => sum + row.amount,
    0
  );

  const totalTransactions = filtered
    .filter((row) => row.currency === chartCurrency)
    .reduce((sum, row) => sum + row.count, 0);

  return (
    <section className="app-card overflow-hidden rounded-3xl border border-border bg-surface">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-6 sm:px-8">
        <div>
          <p className="page-kicker">Payment performance</p>

          <h2 className="mt-2 text-xl font-semibold">
            Captured payment trends
          </h2>

          <p className="mt-2 text-sm text-muted">
            Recorded successful captures over the last 30 days.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-2 text-xs font-semibold">
          <Activity size={15} aria-hidden="true" />
          Last 30 days
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center px-6 py-12 text-center">
          <div className="flex size-16 items-center justify-center rounded-2xl bg-surface-muted">
            <Activity
              size={28}
              className="text-muted"
              aria-hidden="true"
            />
          </div>

          <h3 className="mt-5 text-lg font-semibold">
            No captured payments yet
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-muted">
            Successful PayPal Sandbox captures will appear here
            once they are verified and recorded by INTENTRA.
            Pending payment attempts are not included.
          </p>
        </div>
      ) : hasMultipleCurrencies ? (
        <div className="px-6 py-10 sm:px-8">
          <h3 className="font-semibold">
            Multiple currencies recorded
          </h3>

          <p className="mt-2 text-sm leading-6 text-muted">
            Select a single currency in Transaction intelligence
            to view its captured trend. Different currencies
            are never combined without conversion.
          </p>
        </div>
      ) : (
        <div className="px-6 py-7 sm:px-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl bg-surface-muted p-5">
              <p className="text-xs font-medium text-muted">
                Captured amount
              </p>

              <p className="mt-2 text-3xl font-bold tabular-nums">
                {formatMoney(totalCaptured, chartCurrency!)}
              </p>
            </div>

            <div className="rounded-2xl bg-surface-muted p-5">
              <p className="text-xs font-medium text-muted">
                Successful captures
              </p>

              <p className="mt-2 text-3xl font-bold tabular-nums">
                {totalTransactions}
              </p>
            </div>
          </div>

          <div
            className="mt-8 h-72 w-full"
            role="img"
            aria-label="Captured payment amounts by recorded date"
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{
                  top: 10,
                  right: 12,
                  left: 0,
                  bottom: 5,
                }}
              >
                <defs>
                  <linearGradient
                    id="intentraCapturedFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor="var(--accent)"
                      stopOpacity={0.25}
                    />

                    <stop
                      offset="95%"
                      stopColor="var(--accent)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  stroke="var(--border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />

                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  stroke="var(--muted)"
                />

                <YAxis
                  tick={{ fontSize: 11 }}
                  stroke="var(--muted)"
                  width={48}
                />

                <Tooltip
                  formatter={(value) =>
                    formatMoney(
                      Number(value),
                      chartCurrency!
                    )
                  }
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    color: "var(--foreground)",
                  }}
                />

                <Area
                  type="monotone"
                  dataKey="amount"
                  name="Captured"
                  stroke="var(--accent)"
                  strokeWidth={3}
                  fill="url(#intentraCapturedFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="flex items-start gap-3 border-t border-border bg-surface-muted px-6 py-4 sm:px-8">
        <ShieldCheck
          size={18}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-xs leading-6 text-muted">
          This visualization uses persisted capture records.
          Evaluations, budget reservations, pending checkout,
          and unverified buyer approvals are excluded.
        </p>
      </div>
    </section>
  );
}
