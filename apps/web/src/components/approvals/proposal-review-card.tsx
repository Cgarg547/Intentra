"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Clock3,
  FileText,
  ShieldCheck,
  Store,
  XCircle,
} from "lucide-react";

import type { AgentProposal } from "@/lib/agents/client";

type Props = {
  proposal: AgentProposal;
  working: boolean;
  saving: boolean;
  reason: string;
  onReasonChange: (value: string) => void;
  onConfirm: () => void;
  onReject: () => void;
};

function formatAmount(amount: string | null, currency: string | null) {
  if (!amount || !currency) return "Amount unavailable";

  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return "Amount unavailable";

  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(numeric);
  } catch {
    return `${amount} ${currency}`;
  }
}

export function ProposalReviewCard({
  proposal,
  working,
  saving,
  reason,
  onReasonChange,
  onConfirm,
  onReject,
}: Props) {
  const [showAudit, setShowAudit] = useState(false);

  const ready = proposal.status === "READY_FOR_REVIEW";
  const allowed = proposal.policy_decision === "ALLOW";
  const confirmed = proposal.status === "CONFIRMED";
  const rejected = proposal.status === "REJECTED";

  const StatusIcon = confirmed
    ? CheckCircle2
    : rejected
      ? XCircle
      : Clock3;

  return (
    <article className="app-card overflow-hidden rounded-3xl border border-border bg-surface">
      <div className="flex flex-wrap items-start justify-between gap-5 border-b border-border p-6 sm:p-7">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1.5 text-xs font-semibold">
              <StatusIcon size={14} aria-hidden="true" />
              {proposal.status.replaceAll("_", " ")}
            </span>

            <span className="rounded-full border border-border px-3 py-1.5 text-xs text-muted">
              {proposal.provider_mode === "SIMULATED"
                ? "Simulated extraction"
                : `${proposal.provider_mode} extraction`}
            </span>
          </div>

          <h3 className="mt-4 text-xl font-semibold tracking-tight">
            {proposal.requested_purpose || "Purchase proposal"}
          </h3>

          <p className="mt-2 flex items-center gap-2 text-sm text-muted">
            <Store size={15} aria-hidden="true" />
            {proposal.merchant_id || "Merchant not specified"}
          </p>
        </div>

        <div className="sm:text-right">
          <p className="text-2xl font-bold tabular-nums tracking-tight">
            {formatAmount(proposal.proposed_amount, proposal.currency)}
          </p>

          <p className="mt-1 text-xs text-muted">
            Proposal version {proposal.version}
          </p>
        </div>
      </div>

      <div className="grid gap-5 p-6 sm:p-7 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-surface-muted p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} aria-hidden="true" />
            <h4 className="text-sm font-semibold">Policy evaluation</h4>
          </div>

          <p
            className={`mt-4 text-sm font-bold ${
              allowed
                ? "text-emerald-600"
                : proposal.policy_decision === "DENY"
                  ? "text-rose-600"
                  : "text-amber-600"
            }`}
          >
            {proposal.policy_decision || "Not evaluated"}
          </p>

          <p className="mt-2 text-sm leading-6 text-muted">
            {proposal.policy_reason ||
              "No policy explanation is available."}
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-surface-muted p-5">
          <div className="flex items-center gap-2">
            <FileText size={18} aria-hidden="true" />
            <h4 className="text-sm font-semibold">Linked contract</h4>
          </div>

          <p className="mt-4 break-all text-sm font-medium">
            {proposal.contract_id || "No contract selected"}
          </p>

          <p className="mt-2 text-xs text-muted">
            {proposal.contract_version
              ? `Contract version ${proposal.contract_version}`
              : "Contract version unavailable"}
          </p>
        </div>

        <div className="lg:col-span-2">
          <h4 className="text-sm font-semibold">Original request</h4>

          <p className="mt-2 rounded-xl border border-border bg-surface-muted p-4 text-sm leading-6">
            {proposal.request}
          </p>
        </div>

        {proposal.missing_information.length > 0 && (
          <div className="lg:col-span-2">
            <h4 className="text-sm font-semibold">
              Missing information
            </h4>

            <p className="mt-2 text-sm text-muted">
              {proposal.missing_information.join(", ")}
            </p>
          </div>
        )}
      </div>

      {ready && (
        <div className="border-t border-border p-6 sm:p-7">
          <p className="mb-4 text-xs leading-5 text-muted">
            Confirming this proposal does not reserve funds,
            approve a PayPal order, or capture payment.
          </p>

          <label className="block text-sm">
            <span className="font-semibold">
              Rejection reason
            </span>

            <input
              value={reason}
              maxLength={500}
              disabled={working}
              onChange={(event) =>
                onReasonChange(event.target.value)
              }
              placeholder="Explain why this proposal should be rejected"
              className="mt-2 block w-full rounded-xl border border-border bg-background px-4 py-3"
            />
          </label>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={working || !allowed}
              onClick={onConfirm}
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground transition-colors hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving…" : "Confirm proposal"}
            </button>

            <button
              type="button"
              disabled={working || !reason.trim()}
              onClick={onReject}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-rose-500/30 bg-surface px-5 py-3 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject proposal
            </button>
          </div>
        </div>
      )}

      {(proposal.events?.length ?? 0) > 0 && (
        <div className="border-t border-border p-6 sm:px-7">
          <button
            type="button"
            aria-expanded={showAudit}
            onClick={() => setShowAudit(!showAudit)}
            className="flex w-full items-center justify-between text-left text-sm font-semibold"
          >
            <span>
              Decision audit history ({proposal.events?.length ?? 0})
            </span>

            <span className="text-muted">
              {showAudit ? "Hide" : "View"}
            </span>
          </button>

          {showAudit && (
            <ol className="mt-5 space-y-3">
              {proposal.events?.map((event, index) => (
                <li
                  key={`${event.event_type}-${index}`}
                  className="rounded-xl bg-surface-muted p-4 text-sm"
                >
                  <p className="font-semibold">
                    {event.event_type.replaceAll("_", " ")}
                  </p>

                  <p className="mt-1 text-xs text-muted">
                    {new Date(event.created_at).toLocaleString()}
                  </p>

                  <p className="mt-2 break-all text-xs text-muted">
                    Actor: {event.actor_id ?? "System"}
                  </p>

                  {event.event_data.reason !== undefined && (
                    <p className="mt-2 text-sm text-muted">
                      Reason: {String(event.event_data.reason)}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </article>
  );
}
