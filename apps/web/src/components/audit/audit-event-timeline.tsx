"use client";

import {
  Bot,
  CheckCircle2,
  Clock3,
  CreditCard,
  FileCheck2,
  History,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import type { AuditItem } from "@/lib/workspace/client";

type Props = {
  items: AuditItem[];
  selected: AuditItem | null;
  onSelect: (item: AuditItem) => void;
};

const eventLabels: Record<string, string> = {
  CHECKOUT_HANDOFF_RESUMED: "Checkout resumed",
  CHECKOUT_CREATED: "PayPal checkout created",
  ORDER_CREATE_RECOVERED: "PayPal order creation recovered",
  ORDER_CREATE_OUTCOME_UNKNOWN: "Order creation outcome was uncertain",
  ORDER_CREATE_ATTEMPT_STARTED: "PayPal order creation started",
  PAYMENT_EVALUATED: "Payment evaluated",
  PROPOSAL_PAYMENT_PREPARED: "Proposal payment prepared",
  CHECKOUT_NOT_STARTED: "Checkout not started",
  PROPOSAL_CONFIRMED: "Proposal confirmed",
  PROPOSAL_EVALUATED: "Proposal evaluated",
  CONTRACT_APPROVED: "Contract approved",
  CONTRACT_CREATED: "Contract created",
};

function readableEvent(type: string): string {
  if (eventLabels[type]) return eventLabels[type];

  return type
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (character) => character.toUpperCase());
}

function categoryIcon(category: string) {
  switch (category.toLowerCase()) {
    case "payment":
      return CreditCard;
    case "proposal":
      return Bot;
    case "contract":
      return FileCheck2;
    case "reconciliation":
      return RefreshCw;
    case "evaluation":
      return ShieldCheck;
    default:
      return History;
  }
}

function categoryStyle(category: string): string {
  switch (category.toLowerCase()) {
    case "payment":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "proposal":
      return "bg-violet-500/10 text-violet-700 dark:text-violet-300";
    case "contract":
      return "bg-blue-500/10 text-blue-700 dark:text-blue-300";
    case "reconciliation":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    default:
      return "bg-surface-muted text-muted";
  }
}

function eventTime(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

export function AuditEventTimeline({
  items,
  selected,
  onSelect,
}: Props) {
  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-surface">
      <div className="border-b border-border px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">
              Recorded history
            </p>

            <h2 className="mt-2 text-lg font-semibold">
              Audit event timeline
            </h2>

            <p className="mt-1 text-sm text-muted">
              Select an event to inspect its recorded evidence.
            </p>
          </div>

          <span className="rounded-full bg-surface-muted px-3 py-1.5 text-xs font-semibold text-muted">
            {items.length} loaded events
          </span>
        </div>
      </div>

      <ol className="divide-y divide-border">
        {items.map((item) => {
          const Icon = categoryIcon(item.entity_type);

          const active =
            selected?.event_id === item.event_id &&
            selected?.entity_type === item.entity_type;

          return (
            <li key={`${item.entity_type}-${item.event_id}`}>
              <button
                type="button"
                onClick={() => onSelect(item)}
                aria-pressed={active}
                className={`flex w-full items-start gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-muted sm:px-6 ${
                  active ? "bg-surface-muted" : ""
                }`}
              >
                <span
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${categoryStyle(item.entity_type)}`}
                >
                  <Icon size={20} aria-hidden="true" />
                </span>

                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-foreground">
                      {readableEvent(item.event_type)}
                    </span>

                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                      {item.entity_type}
                    </span>
                  </span>

                  <span className="mt-1 block break-all text-xs text-muted">
                    {item.event_type}
                  </span>

                  <span className="mt-2 block break-all text-xs text-muted">
                    {item.actor_email ||
                      item.actor_id ||
                      "System"}
                  </span>

                  <span className="mt-1 block truncate text-xs text-muted">
                    Record: {item.entity_id}
                  </span>
                </span>

                <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted">
                  <Clock3 size={13} aria-hidden="true" />
                  <time dateTime={item.created_at}>
                    {eventTime(item.created_at)}
                  </time>
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="flex items-start gap-2 border-t border-border bg-surface-muted px-5 py-4 text-xs leading-5 text-muted sm:px-6">
        <CheckCircle2
          size={16}
          className="shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        Events are shown from recorded audit history.
        Historical uncertainty or recovery events do not
        necessarily describe the current payment state.
      </div>
    </section>
  );
}
