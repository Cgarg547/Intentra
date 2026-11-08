"use client";

import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  ShieldCheck,
  ShieldX,
  Store,
  Wallet,
  X,
} from "lucide-react";

import type { IntentContract } from "@/lib/contracts/types";

type Props = {
  contract: IntentContract;
  saving: boolean;
  onClose: () => void;
  onApprove: () => void;
  onRevoke: () => void;
};

function formatAmount(contract: IntentContract) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: contract.currency,
  }).format(Number(contract.maximum_amount));
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

export function ContractInspector({
  contract,
  saving,
  onClose,
  onApprove,
  onRevoke,
}: Props) {
  const approved = contract.status === "APPROVED";
  const draft = contract.status === "DRAFT";

  const StatusIcon = approved
    ? CheckCircle2
    : draft
      ? Clock3
      : ShieldX;

  const statusStyle = approved
    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
    : draft
      ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
      : "border-rose-500/20 bg-rose-500/10 text-rose-700";

  const details = [
    {
      label: "Contract ID",
      value: contract.id,
      icon: FileText,
    },
    {
      label: "Merchant",
      value: contract.merchant_id,
      icon: Store,
    },
    {
      label: "Contract version",
      value: `Version ${contract.version}`,
      icon: FileText,
    },
    {
      label: "Created",
      value: formatDate(contract.created_at),
      icon: CalendarDays,
    },
    {
      label: "Approved",
      value: contract.approved_at
        ? formatDate(contract.approved_at)
        : "Not approved",
      icon: ShieldCheck,
    },
    {
      label: "Revoked",
      value: contract.revoked_at
        ? formatDate(contract.revoked_at)
        : "Not revoked",
      icon: ShieldX,
    },
  ];

  return (
    <section
      aria-labelledby="contract-details-heading"
      className="app-card overflow-hidden rounded-3xl border border-border bg-surface"
    >
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-6 sm:px-8">
        <div>
          <p className="page-kicker">Contract inspection</p>

          <h2
            id="contract-details-heading"
            className="mt-2 text-2xl font-semibold tracking-tight"
          >
            Contract details
          </h2>

          <p className="mt-2 text-sm text-muted">
            Review authorization scope, contract lifecycle,
            and recorded approval information.
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium hover:bg-surface-muted"
        >
          <X size={16} aria-hidden="true" />
          Close
        </button>
      </div>

      <div className="space-y-6 p-6 sm:p-8">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-border bg-surface-muted p-6">
            <div className="flex items-center gap-2 text-sm text-muted">
              <Wallet size={17} aria-hidden="true" />
              Maximum authorized amount
            </div>

            <p className="mt-4 text-4xl font-bold tabular-nums tracking-tight">
              {formatAmount(contract)}
            </p>

            <p className="mt-2 text-xs text-muted">
              Spending ceiling · {contract.currency}
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-muted p-6">
            <p className="text-sm text-muted">
              Authorization status
            </p>

            <div className="mt-4">
              <span
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold ${statusStyle}`}
              >
                <StatusIcon size={16} aria-hidden="true" />
                {contract.status}
              </span>
            </div>

            <p className="mt-4 text-xs leading-6 text-muted">
              {approved
                ? "Human approval is recorded. Payment evaluation still requires separate policy and budget checks."
                : draft
                  ? "This contract requires explicit human approval before it can authorize payment evaluation."
                  : "This contract is revoked and cannot authorize new spending."}
            </p>
          </div>
        </div>

        <div>
          <h3 className="text-base font-semibold">
            Contract information
          </h3>

          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            {details.map(({ label, value, icon: Icon }) => (
              <div
                key={label}
                className="rounded-xl border border-border p-4"
              >
                <dt className="flex items-center gap-2 text-xs text-muted">
                  <Icon size={15} aria-hidden="true" />
                  {label}
                </dt>

                <dd className="mt-2 break-all text-sm font-semibold">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded-2xl border border-border bg-surface-muted p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck
              size={20}
              className="mt-0.5 shrink-0 text-emerald-600"
              aria-hidden="true"
            />

            <div>
              <h3 className="text-sm font-semibold">
                Human-controlled authorization
              </h3>

              <p className="mt-2 text-xs leading-6 text-muted">
                Contract approval is separate from budget reservation,
                PayPal buyer approval, and payment capture.
                Contract lifecycle changes are recorded by the backend
                and may change the authorization version.
              </p>
            </div>
          </div>
        </div>
      </div>

      {(draft || approved) && (
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border px-6 py-5 sm:px-8">
          <div>
            <p className="text-sm font-semibold">
              Contract controls
            </p>

            <p className="mt-1 text-xs text-muted">
              Changes require an explicit human action.
            </p>
          </div>

          {draft && (
            <button
              type="button"
              disabled={saving}
              onClick={onApprove}
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground disabled:opacity-50"
            >
              <ShieldCheck size={17} aria-hidden="true" />
              {saving ? "Working…" : "Approve contract"}
            </button>
          )}

          {approved && (
            <button
              type="button"
              disabled={saving}
              onClick={onRevoke}
              className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 px-5 py-3 text-sm font-semibold text-red-600 hover:bg-red-500/5 disabled:opacity-50"
            >
              <ShieldX size={17} aria-hidden="true" />
              {saving ? "Working…" : "Revoke contract"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
