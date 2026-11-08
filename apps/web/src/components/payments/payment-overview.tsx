import {
  CheckCircle2,
  Clock3,
  CreditCard,
  ShieldAlert,
} from "lucide-react";
import type { PaymentAttempt } from "@/lib/payments/client";
import { hasVerifiedCapture } from "@/lib/payments/capture-status";

export function PaymentOverview({
  payments,
  loading,
}: {
  payments: PaymentAttempt[];
  loading: boolean;
}) {
  const captured = payments.filter(hasVerifiedCapture).length;

  const pending = payments.filter(
    (payment) => payment.attempt_state === "PENDING"
  ).length;

  const unknown = payments.filter(
    (payment) => payment.attempt_state === "UNKNOWN"
  ).length;

  const metrics = [
    {
      label: "Payment attempts",
      value: payments.length,
      detail: "Recorded payment attempts",
      icon: CreditCard,
    },
    {
      label: "Captured",
      value: captured,
      detail: "Recorded verified captures",
      icon: CheckCircle2,
    },
    {
      label: "Pending",
      value: pending,
      detail: "Awaiting payment resolution",
      icon: Clock3,
    },
    {
      label: "Needs reconciliation",
      value: unknown,
      detail: "Unknown payment outcomes",
      icon: ShieldAlert,
    },
  ];

  return (
    <section aria-label="Payment overview" className="space-y-4">
      <div>
        <p className="page-kicker">Financial operations overview</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">
          Payment command center
        </h2>
        <p className="mt-1 text-sm text-muted">
          Live account-scoped payment states. Reservations and buyer
          approvals are not completed payments.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <div
              key={metric.label}
              className="rounded-2xl border border-border bg-surface p-5 shadow-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold text-muted">
                  {metric.label}
                </p>
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-violet-600">
                  <Icon size={19} aria-hidden="true" />
                </span>
              </div>

              <p className="mt-5 text-3xl font-bold tracking-tight tabular-nums">
                {loading ? "—" : metric.value}
              </p>

              <p className="mt-2 text-xs text-muted">
                {metric.detail}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

