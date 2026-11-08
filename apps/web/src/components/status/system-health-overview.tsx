"use client";

import {
  Activity,
  CheckCircle2,
  CircleHelp,
  CreditCard,
  Database,
  Server,
  Store,
  TriangleAlert,
} from "lucide-react";

import type { SystemStatus } from "@/lib/workspace/client";

type Props = {
  data: SystemStatus | null;
  loading: boolean;
};

type HealthState = "healthy" | "configured" | "unavailable" | "unknown";

function classify(value?: string): HealthState {
  if (!value) return "unknown";

  const normalized = value.trim().toLowerCase();

  if (
    ["healthy", "ok", "up", "ready", "connected", "operational"].includes(
      normalized
    )
  ) {
    return "healthy";
  }

  if (
    [
      "configured",
      "credentials_configured",
      "enabled",
      "simulated",
    ].includes(normalized)
  ) {
    return "configured";
  }

  if (normalized === "available") {
    return "healthy";
  }

  if (
    ["down", "error", "failed", "unavailable", "disconnected", "missing", "disabled", "not_configured"].includes(
      normalized
    )
  ) {
    return "unavailable";
  }

  return "unknown";
}

const appearance = {
  healthy: {
    label: "Available",
    icon: CheckCircle2,
    color: "text-emerald-600 dark:text-emerald-400",
    background: "bg-emerald-500/10",
  },
  configured: {
    label: "Configured",
    icon: CheckCircle2,
    color: "text-blue-600 dark:text-blue-400",
    background: "bg-blue-500/10",
  },
  unavailable: {
    label: "Unavailable",
    icon: TriangleAlert,
    color: "text-rose-600 dark:text-rose-400",
    background: "bg-rose-500/10",
  },
  unknown: {
    label: "Unknown",
    icon: CircleHelp,
    color: "text-amber-600 dark:text-amber-400",
    background: "bg-amber-500/10",
  },
};

export function SystemHealthOverview({ data, loading }: Props) {
  const services = [
    {
      title: "API service",
      description: "Backend service status",
      value: data?.api,
      icon: Server,
    },
    {
      title: "Database",
      description: "Persistent data service",
      value: data?.database,
      icon: Database,
    },
    {
      title: "PayPal Sandbox",
      description: "Sandbox integration status",
      value: data?.paypal_sandbox,
      icon: CreditCard,
    },
    {
      title: "Trusted merchants",
      description: "Protected merchant configuration",
      value: data?.trusted_merchants,
      icon: Store,
    },
  ];

  return (
    <section aria-label="System health overview" className="space-y-5">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
          Infrastructure intelligence
        </p>

        <h2 className="mt-2 text-xl font-semibold text-foreground">
          System health overview
        </h2>

        <p className="mt-2 text-sm text-muted">
          Operational indicators reported by the INTENTRA backend.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {services.map((service) => {
          const state = classify(service.value);
          const status = appearance[state];
          const StatusIcon = status.icon;
          const ServiceIcon = service.icon;

          return (
            <article
              key={service.title}
              className="rounded-2xl border border-border bg-surface p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-medium text-muted">
                  {service.title}
                </span>

                <span className="rounded-xl bg-violet-500/10 p-3 text-accent">
                  <ServiceIcon size={20} aria-hidden="true" />
                </span>
              </div>

              {loading ? (
                <div
                  role="status"
                  className="mt-6 h-9 w-28 animate-pulse rounded-lg bg-surface-muted"
                />
              ) : (
                <div className="mt-6 flex items-center gap-2">
                  <span className={`rounded-lg p-1.5 ${status.background}`}>
                    <StatusIcon
                      size={17}
                      className={status.color}
                      aria-hidden="true"
                    />
                  </span>

                  <span className="text-xl font-bold text-foreground">
                    {status.label}
                  </span>
                </div>
              )}

              <p className="mt-3 text-xs leading-5 text-muted">
                {service.description}
              </p>

              {!loading && (
                <p className="mt-3 break-all font-mono text-xs text-muted">
                  Reported: {service.value ?? "Not provided"}
                </p>
              )}
            </article>
          );
        })}
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted p-4">
        <Activity
          size={19}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-sm leading-6 text-muted">
          These indicators reflect the latest API-reported status.
          Configuration alone does not establish connectivity or
          transaction success. Unknown values are not assumed healthy.
        </p>
      </div>
    </section>
  );
}
