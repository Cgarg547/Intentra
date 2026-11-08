import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileClock,
  RotateCcw,
} from "lucide-react";
import type { PaymentAttempt } from "@/lib/payments/client";

type AuditEvent = NonNullable<PaymentAttempt["events"]>[number];

const eventDescriptions: Record<
  string,
  { title: string; description: string; tone: "success" | "warning" | "neutral" }
> = {
  CHECKOUT_NOT_STARTED: {
    title: "Checkout awaiting initiation",
    description: "Payment preparation was recorded before checkout began.",
    tone: "neutral",
  },
  ORDER_CREATE_ATTEMPT_STARTED: {
    title: "PayPal order creation started",
    description: "INTENTRA started an order-creation attempt.",
    tone: "neutral",
  },
  ORDER_CREATE_OUTCOME_UNKNOWN: {
    title: "Order creation required verification",
    description: "The initial provider outcome could not be confirmed at this point.",
    tone: "warning",
  },
  ORDER_CREATE_RECOVERED: {
    title: "Existing PayPal order recovered",
    description: "INTENTRA recorded recovery of an existing order.",
    tone: "success",
  },
  CHECKOUT_CREATED: {
    title: "Checkout prepared",
    description: "A PayPal checkout handoff was recorded.",
    tone: "success",
  },
  CHECKOUT_HANDOFF_RESUMED: {
    title: "Checkout handoff resumed",
    description: "The existing checkout handoff was resumed.",
    tone: "success",
  },
};

function describeEvent(event: AuditEvent) {
  return (
    eventDescriptions[event.event_type] ?? {
      title: event.event_type.replaceAll("_", " ").toLowerCase(),
      description: "Recorded payment workflow event.",
      tone: "neutral" as const,
    }
  );
}

export function PaymentAuditTimeline({
  events,
}: {
  events: AuditEvent[];
}) {
  if (events.length === 0) return null;

  return (
    <section
      aria-labelledby="payment-audit-heading"
      className="mt-7 border-t border-border pt-6"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-violet-500/10 p-2.5 text-violet-600">
          <FileClock size={19} aria-hidden="true" />
        </div>
        <div>
          <h3 id="payment-audit-heading" className="text-lg font-semibold">
            Payment audit timeline
          </h3>
          <p className="mt-1 text-sm text-muted">
            Recorded events from the payment lifecycle.
            These events do not independently confirm payment capture.
          </p>
        </div>
      </div>

      <ol className="relative mt-6 space-y-4 border-l border-border pl-6">
        {events.map((event, index) => {
          const info = describeEvent(event);
          const Icon =
            info.tone === "success"
              ? CheckCircle2
              : info.tone === "warning"
                ? AlertTriangle
                : index === 0
                  ? Clock3
                  : RotateCcw;

          return (
            <li
              key={`${event.event_correlation_id}-${index}`}
              className="relative rounded-2xl border border-border bg-surface-muted/40 p-4"
            >
              <span
                className={`absolute -left-[35px] top-4 flex h-5 w-5 items-center justify-center rounded-full bg-surface ${
                  info.tone === "success"
                    ? "text-emerald-600"
                    : info.tone === "warning"
                      ? "text-amber-600"
                      : "text-muted"
                }`}
              >
                <Icon size={17} aria-hidden="true" />
              </span>

              <div className="flex flex-wrap items-start justify-between gap-2">
                <h4 className="text-sm font-semibold capitalize">
                  {info.title}
                </h4>
                <time
                  dateTime={event.created_at}
                  className="text-xs text-muted"
                >
                  {new Date(event.created_at).toLocaleString()}
                </time>
              </div>

              <p className="mt-2 text-sm leading-6 text-muted">
                {info.description}
              </p>

              <details className="mt-3 text-xs">
                <summary className="cursor-pointer font-medium text-muted">
                  Technical event details
                </summary>
                <dl className="mt-3 space-y-2 rounded-xl border border-border bg-surface p-3">
                  <div>
                    <dt className="text-muted">Event type</dt>
                    <dd className="mt-1 break-all font-mono">
                      {event.event_type}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Correlation ID</dt>
                    <dd className="mt-1 break-all font-mono">
                      {event.event_correlation_id}
                    </dd>
                  </div>
                </dl>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

