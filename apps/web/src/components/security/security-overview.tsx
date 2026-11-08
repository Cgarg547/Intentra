"use client";

import {
  Activity,
  CheckCircle2,
  Clock3,
  ShieldCheck,
  Store,
} from "lucide-react";

import type { SecuritySummary } from "@/lib/workspace/client";

type Props = {
  data: SecuritySummary;
};

export function SecurityOverview({ data }: Props) {
  const indicators = [
    {
      label: "Current session",
      value: data.current_session_valid ? "Valid" : "Unavailable",
      description: "API-checked authentication session",
      icon: ShieldCheck,
      tone: data.current_session_valid
        ? "text-emerald-600 bg-emerald-500/10"
        : "text-amber-600 bg-amber-500/10",
    },
    {
      label: "Active sessions",
      value: String(data.active_session_count),
      description: "Unexpired, unrevoked account sessions",
      icon: Activity,
      tone: "text-violet-600 bg-violet-500/10",
    },
    {
      label: "Trusted merchants",
      value: String(data.trusted_merchant_count),
      description: "Server-configured merchant mappings",
      icon: Store,
      tone: "text-blue-600 bg-blue-500/10",
    },
    {
      label: "Uncertain payments",
      value: String(data.unresolved_attempts),
      description: "UNKNOWN payment outcomes awaiting resolution",
      icon: Clock3,
      tone:
        data.unresolved_attempts === 0
          ? "text-emerald-600 bg-emerald-500/10"
          : "text-amber-600 bg-amber-500/10",
    },
  ];

  return (
    <section aria-label="Security indicators" className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">
            Security intelligence
          </p>

          <h2 className="mt-2 text-xl font-semibold text-foreground">
            Security overview
          </h2>

          <p className="mt-1 text-sm text-muted">
            Recorded account security and financial control indicators.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-semibold text-muted">
          <CheckCircle2 size={15} aria-hidden="true" />
          Account-scoped data
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {indicators.map((indicator) => {
          const Icon = indicator.icon;

          return (
            <article
              key={indicator.label}
              className="rounded-2xl border border-border bg-surface p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-muted">
                  {indicator.label}
                </p>

                <span
                  className={`inline-flex h-11 w-11 items-center justify-center rounded-xl ${indicator.tone}`}
                >
                  <Icon size={21} aria-hidden="true" />
                </span>
              </div>

              <p className="mt-5 text-3xl font-bold tracking-tight text-foreground">
                {indicator.value}
              </p>

              <p className="mt-2 text-xs leading-5 text-muted">
                {indicator.description}
              </p>
            </article>
          );
        })}
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted px-5 py-4">
        <ShieldCheck
          size={19}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-sm leading-6 text-muted">
          These indicators reflect recorded API state.
          They do not establish a complete security assessment,
          live threat monitoring, or successful payment capture.
        </p>
      </div>
    </section>
  );
}
