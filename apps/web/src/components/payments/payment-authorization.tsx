"use client";

import Link from "next/link";
import {
  ArrowRight,
  Check,
  CreditCard,
  LockKeyhole,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import type { IntentContract } from "@/lib/contracts/types";

type Evaluation = {
  decision: string;
  reason: string;
};

type Reservation = {
  reservation_id: string;
  status: string;
  reason: string;
};

type Props = {
  contracts: IntentContract[];
  contractId: string;
  amount: string;
  loading: boolean;
  error: string | null;
  working: boolean;
  evaluation: Evaluation | null;
  reservation: Reservation | null;
  reservationUncertain: boolean;
  onContractChange: (value: string) => void;
  onAmountChange: (value: string) => void;
  onEvaluate: () => void;
  onReserve: () => void;
  onCheckout: () => void;
};

function formatAmount(amount: string, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(Number(amount));
}

export function PaymentAuthorization({
  contracts,
  contractId,
  amount,
  loading,
  error,
  working,
  evaluation,
  reservation,
  reservationUncertain,
  onContractChange,
  onAmountChange,
  onEvaluate,
  onReserve,
  onCheckout,
}: Props) {
  const approvedContracts = contracts.filter(
    (contract) => contract.status === "APPROVED",
  );

  const selectedContract = contracts.find(
    (contract) => contract.id === contractId,
  );

  const reserved = reservation?.status === "RESERVED";
  const locked = reserved || reservationUncertain;

  const amountValid =
    amount.trim() !== "" &&
    Number.isFinite(Number(amount)) &&
    Number(amount) >= 0.01 &&
    Math.round(Number(amount) * 100) === Number(amount) * 100;

  const allowed = evaluation?.decision === "ALLOW";

  const steps = [
    {
      label: "Evaluate",
      description: "Check spending policy",
      complete: Boolean(evaluation),
    },
    {
      label: "Reserve",
      description: "Hold approved budget",
      complete: reserved,
    },
    {
      label: "PayPal approval",
      description: "Authorize with PayPal",
      complete: false,
    },
  ];

  return (
    <section className="app-card overflow-hidden rounded-3xl border border-border bg-surface">
      <div className="border-b border-border px-6 py-7 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="page-kicker">CONTROLLED PAYMENT WORKFLOW</p>

            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              Authorize a payment
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Evaluate a purchase against an approved spending contract,
              reserve its budget, then continue to PayPal Sandbox.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-border bg-surface-muted px-4 py-2 text-xs font-semibold">
            <LockKeyhole size={15} aria-hidden="true" />
            Human-controlled
          </div>
        </div>

        <div className="mt-7 grid gap-3 md:grid-cols-3">
          {steps.map((step, index) => (
            <div
              key={step.label}
              className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted p-4"
            >
              <span
                className={`flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
                  step.complete
                    ? "bg-emerald-500/15 text-emerald-600"
                    : "bg-violet-500/10 text-violet-600"
                }`}
              >
                {step.complete ? (
                  <Check size={18} aria-hidden="true" />
                ) : (
                  String(index + 1).padStart(2, "0")
                )}
              </span>

              <div>
                <p className="text-sm font-semibold">{step.label}</p>
                <p className="mt-1 text-xs leading-5 text-muted">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-6 sm:p-8">
        {loading ? (
          <div
            role="status"
            className="h-36 animate-pulse rounded-2xl bg-surface-muted"
          />
        ) : (
          <>
            <div className="grid gap-6 lg:grid-cols-2">
              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <ShieldCheck size={16} aria-hidden="true" />
                  Approved intent contract
                </span>

                <select
                  required
                  value={contractId}
                  disabled={locked || working}
                  onChange={(event) =>
                    onContractChange(event.target.value)
                  }
                  className="block h-12 w-full appearance-none rounded-xl border border-border bg-background px-4 text-sm disabled:opacity-60"
                >
                  <option value="">Select a contract</option>

                  {approvedContracts.map((contract) => (
                    <option key={contract.id} value={contract.id}>
                      {contract.merchant_id} · up to{" "}
                      {formatAmount(
                        contract.maximum_amount,
                        contract.currency,
                      )}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <CreditCard size={16} aria-hidden="true" />
                  Payment amount
                  {selectedContract
                    ? ` (${selectedContract.currency})`
                    : ""}
                </span>

                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  placeholder="0.00"
                  value={amount}
                  disabled={locked || working}
                  onChange={(event) =>
                    onAmountChange(event.target.value)
                  }
                  className="block h-12 w-full rounded-xl border border-border bg-background px-4 text-sm tabular-nums disabled:opacity-60"
                />
              </label>
            </div>

            {selectedContract && (
              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-surface-muted p-5">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-violet-500/10 text-violet-600">
                    <Wallet size={19} aria-hidden="true" />
                  </div>

                  <div>
                    <p className="text-xs text-muted">
                      Contract maximum amount
                    </p>

                    <p className="mt-1 text-lg font-bold tabular-nums">
                      {formatAmount(
                        selectedContract.maximum_amount,
                        selectedContract.currency,
                      )}
                    </p>
                  </div>
                </div>

                <span className="rounded-full bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-600">
                  Approved contract
                </span>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={
                  working ||
                  loading ||
                  locked ||
                  !selectedContract ||
                  !amountValid
                }
                onClick={onEvaluate}
                className="inline-flex items-center gap-2 rounded-xl border border-border px-5 py-3 text-sm font-semibold transition-colors hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
              >
                {working ? "Working…" : "Evaluate payment"}
                <ArrowRight size={16} aria-hidden="true" />
              </button>

              {allowed && !reservation && (
                <button
                  type="button"
                  disabled={working}
                  onClick={onReserve}
                  className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground disabled:opacity-50"
                >
                  {reservationUncertain
                    ? "Retry reservation safely"
                    : "Reserve budget"}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              )}

              {reserved && (
                <button
                  type="button"
                  disabled={working}
                  onClick={onCheckout}
                  className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground disabled:opacity-50"
                >
                  {working
                    ? "Preparing checkout…"
                    : "Continue to PayPal Sandbox"}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              )}
            </div>

            {evaluation && (
              <div
                role="status"
                className="mt-6 rounded-2xl border border-border bg-surface-muted p-5"
              >
                <p className="text-sm font-semibold">
                  Policy decision: {evaluation.decision}
                </p>

                <p className="mt-2 text-sm leading-6 text-muted">
                  {evaluation.reason}
                </p>
              </div>
            )}

            {reservation && (
              <div
                role="status"
                className="mt-4 rounded-2xl border border-border bg-surface-muted p-5"
              >
                <p className="text-sm font-semibold">
                  Reservation: {reservation.status}
                </p>

                <p className="mt-2 text-sm leading-6 text-muted">
                  {reservation.reason}
                </p>
              </div>
            )}

            {approvedContracts.length === 0 && !error && (
              <div className="mt-6 rounded-2xl border border-border bg-surface-muted p-5 text-sm">
                No approved contracts are available.{" "}
                <Link
                  href="/contracts"
                  className="font-semibold text-accent underline"
                >
                  Create or approve a contract
                </Link>
                .
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex items-start gap-3 border-t border-border bg-surface-muted px-6 py-5 sm:px-8">
        <ShieldCheck
          size={19}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-xs leading-6 text-muted">
          Evaluation does not move money. A reservation holds budget,
          and PayPal buyer approval is separate from payment capture.
          Only a verified capture confirms a successful payment.
        </p>
      </div>
    </section>
  );
}
