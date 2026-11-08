"use client";

import { useMemo } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { AnalyticsSummary } from "@/lib/workspace/client";

type Props = {
  rows: AnalyticsSummary["payment_states"];
};

const COLORS: Record<string, string> = {
  SUCCEEDED: "#10b981",
  PENDING: "#f59e0b",
  UNKNOWN: "#ef4444",
  FAILED: "#64748b",
};

const FALLBACK_COLOR = "#8b7cf6";

export function PaymentOutcomesChart({ rows }: Props) {
  const chartData = useMemo(() => {
    const totals = new Map<string, number>();

    for (const row of rows) {
      totals.set(
        row.state,
        (totals.get(row.state) ?? 0) + row.count,
      );
    }

    return Array.from(totals, ([name, value]) => ({
      name,
      value,
    })).filter((item) => item.value > 0);
  }, [rows]);

  const total = chartData.reduce(
    (sum, item) => sum + item.value,
    0,
  );

  return (
    <section className="app-card rounded-3xl border border-border bg-surface p-6">
      <div>
        <p className="page-kicker">Payment intelligence</p>

        <h2 className="mt-2 text-xl font-semibold">
          Payment outcomes
        </h2>

        <p className="mt-1 text-sm text-muted">
          Distribution of recorded payment attempt states.
        </p>
      </div>

      {total === 0 ? (
        <div className="mt-6 rounded-2xl bg-surface-muted p-8 text-center">
          <p className="font-medium">No payment attempts yet</p>

          <p className="mt-2 text-sm text-muted">
            Payment activity will appear here when recorded.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid items-center gap-6 sm:grid-cols-2">
          <div
            className="relative h-60 min-w-0"
            role="img"
            aria-label={`Payment outcomes chart showing ${total} recorded payment attempts`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={72}
                  outerRadius={100}
                  paddingAngle={chartData.length > 1 ? 3 : 0}
                  stroke="none"
                >
                  {chartData.map((item) => (
                    <Cell
                      key={item.name}
                      fill={COLORS[item.name] ?? FALLBACK_COLOR}
                    />
                  ))}
                </Pie>

                <Tooltip
                  formatter={(value, name) => [
                    `${value} attempts`,
                    String(name),
                  ]}
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    color: "var(--foreground)",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold tabular-nums">
                {total}
              </span>

              <span className="text-xs text-muted">
                Attempts
              </span>
            </div>
          </div>

          <div className="space-y-3">
            {chartData.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between gap-3 rounded-xl bg-surface-muted px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className="size-2.5 rounded-full"
                    style={{
                      backgroundColor:
                        COLORS[item.name] ?? FALLBACK_COLOR,
                    }}
                  />

                  <span className="text-sm font-medium">
                    {item.name}
                  </span>
                </div>

                <span className="text-sm font-semibold tabular-nums">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-muted">
        Counts represent payment attempts, not captured
        revenue. Pending or uncertain outcomes are not
        successful payments.
      </p>
    </section>
  );
}
