"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CreditCard,
  ShieldCheck,
} from "lucide-react";

import type { AnalyticsSummary } from "@/lib/workspace/client";

type Props = {
  data: AnalyticsSummary | null;
  loading: boolean;
};

export function AnalyticsOverview({ data, loading }: Props) {
  const proposalCount = data
    ? Object.values(data.proposals).reduce(
        (sum, count) => sum + count,
        0,
      )
    : 0;

  const metrics = [
    {
      label: "Payment attempts",
      value: data?.payments.count ?? 0,
      description: "Recorded payment attempts",
      icon: CreditCard,
      color: "text-violet-600",
      background: "bg-violet-500/10",
    },
    {
      label: "Successful payments",
      value: data?.payments.successful_count ?? 0,
      description: "Attempts recorded as successful",
      icon: CheckCircle2,
      color: "text-emerald-600",
      background: "bg-emerald-500/10",
    },
    {
      label: "Uncertain outcomes",
      value: data?.payments.unknown_count ?? 0,
      description: "Attempts currently in unknown state",
      icon: AlertTriangle,
      color: "text-amber-600",
      background: "bg-amber-500/10",
    },
    {
      label: "AI proposals",
      value: proposalCount,
      description: "Saved purchasing proposals",
      icon: Bot,
      color: "text-indigo-600",
      background: "bg-indigo-500/10",
    },
  ];

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="page-kicker">
            Financial intelligence
          </p>

          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Financial command center
          </h2>

          <p className="mt-1 text-sm text-muted">
            Payment activity and purchasing intelligence
            across your authenticated workspace.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-xs font-semibold">
          <ShieldCheck size={15} aria-hidden="true" />
          Owner-scoped records
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <article
              key={metric.label}
              className="app-card rounded-2xl border border-border bg-surface p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-muted">
                  {metric.label}
                </p>

                <span
                  className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${metric.background} ${metric.color}`}
                >
                  <Icon size={19} aria-hidden="true" />
                </span>
              </div>

              {loading || !data ? (
                <div
                  role="status"
                  className="mt-5 h-9 w-16 animate-pulse rounded-lg bg-surface-muted"
                />
              ) : (
                <p className="mt-5 text-3xl font-bold tabular-nums tracking-tight">
                  {metric.value.toLocaleString()}
                </p>
              )}

              <p className="mt-2 text-xs leading-5 text-muted">
                {metric.description}
              </p>
            </article>
          );
        })}
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted p-4">
        <ShieldCheck
          size={19}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-xs leading-6 text-muted">
          Payment attempts are not necessarily completed
          payments. Successful outcomes are counted separately.
          An approved contract or AI proposal does not
          establish buyer approval or payment capture.
        </p>
      </div>
    </section>
  );
}
