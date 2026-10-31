"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { spendingTrends } from "@/lib/demo/financial-data";

export function SpendingChart() {
  return (
    <section className="rounded-2xl border border-border bg-surface p-6">
      <h2 className="text-lg font-semibold text-foreground">
        Spending intelligence
      </h2>

      <p className="mt-1 text-sm text-muted">
        Simulated authorized and blocked spending over seven days
      </p>

      <div
        className="mt-6 h-80 w-full"
        role="img"
        aria-label="Illustrative seven-day spending trend comparing authorized and blocked payment amounts"
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={spendingTrends}
            margin={{ top: 10, right: 10, left: 0, bottom: 5 }}
          >
            <defs>
              <linearGradient id="authorizedFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b7cf6" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#8b7cf6" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border)"
              vertical={false}
            />

            <XAxis dataKey="day" stroke="var(--muted)" />
            <YAxis stroke="var(--muted)" />

            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                color: "var(--foreground)",
              }}
            />

            <Legend />

            <Area
              type="monotone"
              dataKey="authorized"
              name="Authorized"
              stroke="#8b7cf6"
              strokeWidth={3}
              fill="url(#authorizedFill)"
            />

            <Area
              type="monotone"
              dataKey="blocked"
              name="Blocked"
              stroke="#f97373"
              strokeWidth={2}
              fill="transparent"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-xs text-muted">
        Demonstration data only. No live PayPal transactions are represented.
      </p>
    </section>
  );
}
