"use client";

import { ShieldCheck } from "lucide-react";

import type { AnalyticsSummary } from "@/lib/workspace/client";

type Props = {
  decisions: AnalyticsSummary["policy_decisions"];
};

const STATES = [
  {
    key: "ALLOW",
    label: "Allowed",
    color: "bg-emerald-500",
    text: "text-emerald-600",
  },
  {
    key: "BLOCK",
    label: "Blocked",
    color: "bg-rose-500",
    text: "text-rose-600",
  },
  {
    key: "REVIEW",
    label: "Needs review",
    color: "bg-amber-500",
    text: "text-amber-600",
  },
] as const;

export function PolicyEvaluationsChart({ decisions }: Props) {
  const total = STATES.reduce(
    (sum, state) => sum + (decisions[state.key] ?? 0),
    0,
  );

  return (
    <section className="app-card flex h-full flex-col rounded-3xl border border-border bg-surface p-6">
      <div>
        <p className="page-kicker">Policy intelligence</p>

        <h2 className="mt-2 text-xl font-semibold">
          Deterministic policy evaluations
        </h2>

        <p className="mt-1 text-sm text-muted">
          Recorded authorization decisions.
        </p>
      </div>

      <div className="mt-7 flex items-center justify-between rounded-2xl bg-surface-muted p-5">
        <div>
          <p className="text-xs font-medium text-muted">
            Total evaluations
          </p>

          <p className="mt-2 text-4xl font-bold tabular-nums">
            {total}
          </p>
        </div>

        <span className="flex size-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
          <ShieldCheck size={24} aria-hidden="true" />
        </span>
      </div>

      <div className="mt-7 space-y-6">
        {STATES.map((state) => {
          const count = decisions[state.key] ?? 0;

          const percentage =
            total > 0 ? (count / total) * 100 : 0;

          return (
            <div key={state.key}>
              <div className="mb-2 flex items-center justify-between gap-3">
                <span className="text-sm font-medium">
                  {state.label}
                </span>

                <span className={`text-sm font-semibold tabular-nums ${state.text}`}>
                  {count}
                  <span className="ml-2 text-xs font-normal text-muted">
                    {percentage.toFixed(0)}%
                  </span>
                </span>
              </div>

              <div
                className="h-2.5 overflow-hidden rounded-full bg-surface-muted"
                role="progressbar"
                aria-label={`${state.label} evaluations`}
                aria-valuenow={count}
                aria-valuemin={0}
                aria-valuemax={total || 1}
              >
                <div
                  className={`h-full rounded-full ${state.color}`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-auto border-t border-border pt-5 text-xs leading-6 text-muted">
        An ALLOW decision does not mean funds were
        reserved, the buyer approved checkout, or
        PayPal captured a payment.
      </p>
    </section>
  );
}
