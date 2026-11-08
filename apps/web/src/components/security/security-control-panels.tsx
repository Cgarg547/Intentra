"use client";

import {
  CheckCircle2,
  FileCheck2,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";

import type { SecuritySummary } from "@/lib/workspace/client";

type Props = {
  data: SecuritySummary;
};

export function SecurityControlPanels({ data }: Props) {
  const contracts = [
    {
      label: "Approved",
      count: data.contracts.APPROVED ?? 0,
      color: "bg-emerald-500",
    },
    {
      label: "Draft",
      count: data.contracts.DRAFT ?? 0,
      color: "bg-amber-500",
    },
    {
      label: "Revoked",
      count: data.contracts.REVOKED ?? 0,
      color: "bg-slate-400",
    },
  ];

  const decisions = [
    {
      label: "Allowed",
      count: data.policy_decisions.ALLOW ?? 0,
      color: "bg-emerald-500",
    },
    {
      label: "Blocked",
      count: data.policy_decisions.BLOCK ?? 0,
      color: "bg-rose-500",
    },
    {
      label: "Needs review",
      count: data.policy_decisions.REVIEW ?? 0,
      color: "bg-amber-500",
    },
  ];

  const totalContracts = contracts.reduce(
    (sum, item) => sum + item.count,
    0
  );

  const totalDecisions = decisions.reduce(
    (sum, item) => sum + item.count,
    0
  );

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <article className="overflow-hidden rounded-3xl border border-border bg-surface shadow-sm">
        <div className="border-b border-border px-6 py-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-accent">
                Authorization governance
              </p>

              <h2 className="mt-2 text-xl font-semibold">
                Contract authorization
              </h2>

              <p className="mt-2 text-sm text-muted">
                Recorded owner-controlled contract states.
              </p>
            </div>

            <span className="rounded-xl bg-violet-500/10 p-3 text-violet-600">
              <FileCheck2 size={23} aria-hidden="true" />
            </span>
          </div>
        </div>

        <div className="space-y-6 p-6">
          <div className="rounded-2xl bg-surface-muted p-5">
            <p className="text-sm text-muted">Total contracts</p>

            <p className="mt-2 text-3xl font-bold tabular-nums">
              {totalContracts}
            </p>
          </div>

          {contracts.map((item) => {
            const percentage =
              totalContracts > 0
                ? (item.count / totalContracts) * 100
                : 0;

            return (
              <div key={item.label}>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-medium">{item.label}</span>

                  <span className="font-semibold tabular-nums">
                    {item.count}
                    <span className="ml-2 text-muted">
                      {Math.round(percentage)}%
                    </span>
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-start gap-3 border-t border-border bg-surface-muted px-6 py-4">
          <ShieldCheck
            size={17}
            className="mt-0.5 shrink-0 text-emerald-600"
            aria-hidden="true"
          />

          <p className="text-xs leading-6 text-muted">
            An approved contract authorizes spending under
            its recorded terms. It does not establish buyer
            approval or successful payment capture.
          </p>
        </div>
      </article>

      <article className="overflow-hidden rounded-3xl border border-border bg-surface shadow-sm">
        <div className="border-b border-border px-6 py-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-accent">
                Policy intelligence
              </p>

              <h2 className="mt-2 text-xl font-semibold">
                Policy outcomes
              </h2>

              <p className="mt-2 text-sm text-muted">
                Recorded deterministic authorization decisions.
              </p>
            </div>

            <span className="rounded-xl bg-emerald-500/10 p-3 text-emerald-600">
              <CheckCircle2 size={23} aria-hidden="true" />
            </span>
          </div>
        </div>

        <div className="space-y-6 p-6">
          <div className="rounded-2xl bg-surface-muted p-5">
            <p className="text-sm text-muted">Total evaluations</p>

            <p className="mt-2 text-3xl font-bold tabular-nums">
              {totalDecisions}
            </p>
          </div>

          {decisions.map((item) => {
            const percentage =
              totalDecisions > 0
                ? (item.count / totalDecisions) * 100
                : 0;

            return (
              <div key={item.label}>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-medium">{item.label}</span>

                  <span className="font-semibold tabular-nums">
                    {item.count}
                    <span className="ml-2 text-muted">
                      {Math.round(percentage)}%
                    </span>
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-start gap-3 border-t border-border bg-surface-muted px-6 py-4">
          <ShieldAlert
            size={17}
            className="mt-0.5 shrink-0 text-amber-600"
            aria-hidden="true"
          />

          <p className="text-xs leading-6 text-muted">
            An ALLOW decision is a policy evaluation result,
            not evidence that budget was reserved, checkout
            was approved, or funds were captured.
          </p>
        </div>
      </article>
    </section>
  );
}
