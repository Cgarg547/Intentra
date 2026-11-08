import {
  CheckCircle2,
  Clock3,
  FileQuestion,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import type { AgentProposal } from "@/lib/agents/client";

type Props = {
  proposals: AgentProposal[];
  loading: boolean;
};

export function ApprovalOverview({ proposals, loading }: Props) {
  const awaiting = proposals.filter(
    (item) => item.status === "READY_FOR_REVIEW"
  ).length;

  const confirmed = proposals.filter(
    (item) => item.status === "CONFIRMED"
  ).length;

  const rejected = proposals.filter(
    (item) => item.status === "REJECTED"
  ).length;

  const needsInformation = proposals.filter(
    (item) => item.status === "NEEDS_INFORMATION"
  ).length;

  const metrics = [
    {
      label: "Awaiting review",
      value: awaiting,
      description: "Ready for a human decision",
      icon: Clock3,
      color: "text-amber-600",
      background: "bg-amber-500/10",
    },
    {
      label: "Confirmed",
      value: confirmed,
      description: "Proposals confirmed by a human",
      icon: CheckCircle2,
      color: "text-emerald-600",
      background: "bg-emerald-500/10",
    },
    {
      label: "Rejected",
      value: rejected,
      description: "Declined purchase proposals",
      icon: XCircle,
      color: "text-rose-600",
      background: "bg-rose-500/10",
    },
    {
      label: "Needs information",
      value: needsInformation,
      description: "Requests awaiting clarification",
      icon: FileQuestion,
      color: "text-violet-600",
      background: "bg-violet-500/10",
    },
  ];

  return (
    <section aria-label="Approval overview" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="page-kicker">AUTHORIZATION OVERVIEW</p>

          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Review command center
          </h2>

          <p className="mt-1 text-sm leading-6 text-muted">
            Proposal decisions across your current account.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-semibold">
          <ShieldCheck size={15} aria-hidden="true" />
          Human oversight
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
                <div
                  role="status"
                  className="mt-5 h-9 w-16 animate-pulse rounded-lg bg-surface-muted"
                />
              ) : (
                <p className="mt-5 text-3xl font-bold tabular-nums tracking-tight">
                  {metric.value}
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
          Confirming a proposal records a human review decision.
          It does not reserve funds, approve a PayPal order,
          or capture a payment. Those operations require
          separate controlled steps.
        </p>
      </div>
    </section>
  );
}
