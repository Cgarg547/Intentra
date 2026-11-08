import {
  Activity,
  Clock3,
  Database,
  ShieldCheck,
} from "lucide-react";

import type { AuditItem } from "@/lib/workspace/client";

type Props = {
  items: AuditItem[];
  loading: boolean;
};

function formatDate(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Unavailable"
    : date.toLocaleString();
}

export function AuditOverview({ items, loading }: Props) {
  const categories = new Set(
    items.map((item) => item.entity_type)
  ).size;

  const latest = items.reduce<AuditItem | null>(
    (current, item) => {
      if (!current) return item;

      const currentTime = Date.parse(current.created_at);
      const itemTime = Date.parse(item.created_at);

      return Number.isFinite(itemTime) &&
        (!Number.isFinite(currentTime) ||
          itemTime > currentTime)
        ? item
        : current;
    },
    null
  );

  const metrics = [
    {
      title: "Loaded audit events",
      value: String(items.length),
      note: "Events in the current result page",
      icon: Database,
      iconStyle: "bg-violet-500/10 text-violet-600",
    },
    {
      title: "Entity categories",
      value: String(categories),
      note: "Distinct categories in loaded events",
      icon: Activity,
      iconStyle: "bg-blue-500/10 text-blue-600",
    },
    {
      title: "Latest loaded event",
      value: latest ? formatDate(latest.created_at) : "—",
      note: "Most recent timestamp in this page",
      icon: Clock3,
      iconStyle: "bg-amber-500/10 text-amber-600",
    },
  ];

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Audit intelligence
          </p>

          <h2 className="mt-2 text-xl font-semibold text-foreground">
            Recorded activity overview
          </h2>

          <p className="mt-1 text-sm leading-6 text-muted">
            Visibility into the currently loaded,
            account-scoped audit records.
          </p>
        </div>

        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-xs font-semibold text-muted">
          <ShieldCheck size={15} aria-hidden="true" />
          Account-scoped records
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <article
              key={metric.title}
              className="rounded-2xl border border-border bg-surface p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-muted">
                  {metric.title}
                </p>

                <div
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${metric.iconStyle}`}
                >
                  <Icon size={21} aria-hidden="true" />
                </div>
              </div>

              <p className="mt-5 break-words text-2xl font-bold tracking-tight text-foreground">
                {loading ? "—" : metric.value}
              </p>

              <p className="mt-2 text-xs leading-5 text-muted">
                {metric.note}
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
          These metrics describe the current filtered page,
          not the complete audit history. Audit events are
          recorded evidence; their presence does not establish
          successful payment capture or independently verify
          system security.
        </p>
      </div>
    </section>
  );
}
