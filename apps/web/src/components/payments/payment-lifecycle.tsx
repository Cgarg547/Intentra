import {
  Check,
  Clock3,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import type { PaymentAttempt } from "@/lib/payments/client";
import { hasVerifiedCapture } from "@/lib/payments/capture-status";

export function PaymentLifecycle({
  payment,
}: {
  payment: PaymentAttempt;
}) {
  const reserved = [
    "RESERVED",
    "EXECUTION_PENDING",
    "CAPTURED",
  ].includes(payment.reservation_state);

  const orderCreated = Boolean(payment.provider_order_id);

  const approved =
    payment.approval_state === "APPROVED" &&
    Boolean(payment.approval_verified_at);

  const captured = hasVerifiedCapture(payment);

  const stages = [
    {
      label: "Budget reserved",
      complete: reserved,
      icon: Wallet,
    },
    {
      label: "PayPal order",
      complete: orderCreated,
      icon: ShieldCheck,
    },
    {
      label: "Buyer approved",
      complete: approved,
      icon: ShieldCheck,
    },
    {
      label: "Payment captured",
      complete: captured,
      icon: Check,
    },
  ];

  return (
    <section
      aria-label="Payment lifecycle"
      className="mt-6 rounded-2xl border border-border bg-surface-muted/50 p-5"
    >
      <div className="mb-6">
        <h3 className="font-semibold">Payment lifecycle</h3>
        <p className="mt-1 text-xs text-muted">
          Based on recorded payment and provider states.
        </p>
      </div>

      <ol className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage) => {
          const Icon = stage.icon;

          return (
            <li key={stage.label} className="flex items-center gap-3">
              <span
                className={
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-full " +
                  (stage.complete
                    ? "bg-emerald-500/10 text-emerald-600"
                    : "bg-surface border border-border text-muted")
                }
              >
                {stage.complete ? (
                  <Icon size={19} aria-hidden="true" />
                ) : (
                  <Clock3 size={19} aria-hidden="true" />
                )}
              </span>

              <div>
                <p className="text-sm font-semibold">{stage.label}</p>
                <p className="mt-1 text-xs text-muted">
                  {stage.complete ? "Recorded" : "Not confirmed"}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-6 border-t border-border pt-4 text-xs text-muted">
        A reservation or PayPal order does not establish buyer
        approval or successful capture.
      </p>
    </section>
  );
}

