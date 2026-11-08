import {
  CheckCircle2,
  FileClock,
  ShieldCheck,
  ShieldX,
} from "lucide-react";

import type { IntentContract } from "@/lib/contracts/types";

type Props = {
  contracts: IntentContract[];
  loading: boolean;
  error: string | null;
};

export function ContractOverview({
  contracts,
  loading,
  error,
}: Props) {
  const approved = contracts.filter(
    (item) => item.status === "APPROVED"
  ).length;

  const draft = contracts.filter(
    (item) => item.status === "DRAFT"
  ).length;

  const revoked = contracts.filter(
    (item) => item.status === "REVOKED"
  ).length;

  const metrics = [
    {
      label: "Approved contracts",
      value: approved,
      description: "Contracts with recorded human approval",
      icon: CheckCircle2,
      color: "text-emerald-600",
      background: "bg-emerald-500/10",
    },
    {
      label: "Draft contracts",
      value: draft,
      description: "Awaiting authorization",
      icon: FileClock,
      color: "text-amber-600",
      background: "bg-amber-500/10",
    },
    {
      label: "Revoked contracts",
      value: revoked,
      description: "No longer authorized for new spending",
      icon: ShieldX,
      color: "text-rose-600",
      background: "bg-rose-500/10",
    },
  ];

  return (
    <section aria-label="Contract overview" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="page-kicker">SPENDING GOVERNANCE</p>

          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Contract command center
          </h2>

          <p className="mt-1 text-sm leading-6 text-muted">
            Human-governed spending agreements and authorization states.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-semibold">
          <ShieldCheck size={15} aria-hidden="true" />
          Policy controlled
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <article
              key={metric.label}
              className="app-card rounded-2xl border border-border bg-surface p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold text-muted">
                  {metric.label}
                </p>

                <span
                  className={`flex size-10 items-center justify-center rounded-xl ${metric.background} ${metric.color}`}
                >
                  <Icon size={19} aria-hidden="true" />
                </span>
              </div>

              {loading ? (
                <div className="mt-5 h-9 w-16 animate-pulse rounded-lg bg-surface-muted" />
              ) : (
                <p className="mt-5 text-3xl font-bold tabular-nums tracking-tight">
                  {error ? "—" : metric.value}
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
          Approved contracts define merchant scope and maximum spending
          amounts. Contract approval does not reserve funds or authorize
          PayPal payment capture. Available budget must be checked
          separately during payment evaluation.
        </p>
      </div>
    </section>
  );
}
