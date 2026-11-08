import Link from "next/link";
import { FileText, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { AgentProposal } from "@/lib/agents/client";
import { ProposalProgress } from "./proposal-progress";
import { ProposalNextAction } from "./proposal-next-action";

export function policyLabel(decision: AgentProposal["policy_decision"]) {
  if (decision === "ALLOW") return "Allowed by current policy";
  if (decision === "DENY") return "Denied by current policy";
  if (decision === "NEEDS_INFORMATION") return "Needs information";
  return "Not evaluated";
}

function statusLabel(status: string) {
  return status.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function ProposalCard({
  proposal,
  actions,
  detail = false,
}: {
  proposal: AgentProposal;
  actions?: ReactNode;
  detail?: boolean;
}) {
  const prepared = proposal.payment_preparation;

  const amount = [proposal.currency, proposal.proposed_amount]
    .filter((value) => value != null && value !== "")
    .join(" ");

  return (
    <article
      id={`proposal-${proposal.proposal_id}`}
      aria-label={`Proposal ${proposal.proposal_id}`}
      className="group min-w-0 scroll-mt-24 overflow-hidden rounded-3xl border border-border bg-surface p-5 shadow-sm transition-shadow duration-200 hover:shadow-lg hover:shadow-violet-500/5 sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted">
            <FileText size={15} aria-hidden="true" />
            {proposal.provider_mode === "SIMULATED"
              ? "Simulated AI"
              : proposal.provider_mode}
          </p>
          <h3 className="mt-3 break-words text-xl font-semibold tracking-tight">
            {proposal.requested_purpose || "Purchase proposal"}
          </h3>
        </div>

        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            proposal.status === "NEEDS_INFORMATION"
              ? "border-accent/40 bg-accent/10 text-foreground"
              : "border-border bg-surface-muted"
          }`}
        >
          {statusLabel(proposal.status)}
        </span>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-violet-500/15 bg-violet-500/5 p-5">
          <p className="text-xs font-medium text-muted">
            Proposed purchase amount
          </p>
          <p className="mt-2 text-3xl font-bold tracking-tight tabular-nums">
            {amount || "Not specified"}
          </p>
          <p className="mt-2 text-xs text-muted">
            Proposed amount, not a completed payment
          </p>
        </div>

        <dl className="grid content-center gap-3 rounded-2xl border border-border p-4 text-sm">
          <div>
            <dt className="text-xs text-muted">Merchant</dt>
            <dd className="mt-1 break-words font-semibold">
              {proposal.merchant_id || "Not specified"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Created</dt>
            <dd className="mt-1">
              <time dateTime={proposal.created_at}>
                {new Date(proposal.created_at).toLocaleString()}
              </time>
            </dd>
          </div>
        </dl>
      </div>

      <section className="mt-4 rounded-2xl border border-violet-500/15 bg-violet-500/5 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <ShieldCheck size={18} className="text-accent" aria-hidden="true" />
          <h4 className="text-sm font-semibold">Policy decision</h4>
          <span className="text-sm font-medium text-muted">
            {policyLabel(proposal.policy_decision)}
          </span>
        </div>

        <p className="mt-2 text-sm leading-6">
          {proposal.policy_reason ||
            (proposal.status === "DRAFT"
              ? "No completed policy evaluation is available. Refresh this saved proposal to check its latest state."
              : proposal.explanation)}
        </p>

        {proposal.missing_information.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold text-muted">
              Missing information
            </p>
            <ul
              className="mt-2 flex flex-wrap gap-2"
              aria-label="Missing information"
            >
              {proposal.missing_information.map((item, index) => (
                <li
                  key={`${item}-${index}`}
                  className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {prepared ? (
        <div className="mt-4 rounded-2xl border border-border p-4">
          <p className="text-sm font-semibold">Payment prepared</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            Budget is reserved and a payment attempt exists.
            Buyer approval and verified payment capture are separate steps.
            Review Payments for the latest execution outcome.
          </p>
          <p className="mt-2 break-all text-xs text-muted">
            Reservation {prepared.reservation_id} · {statusLabel(prepared.status)}
          </p>
        </div>
      ) : proposal.status === "CONFIRMED" ? (
        <p className="mt-4 rounded-xl bg-surface-muted p-4 text-sm">
          Proposal confirmed. Payment has not been reserved or initiated.
        </p>
      ) : null}

      <ProposalProgress proposal={proposal} />
      <ProposalNextAction proposal={proposal} />

      {actions}

      <details className="mt-5 rounded-xl border border-border bg-surface-muted/40 px-4 py-3 text-sm">
        <summary className="cursor-pointer font-medium text-muted">
          Request and technical details
        </summary>

        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <div>
            <p className="text-xs font-semibold text-muted">Original request</p>
            <p className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-surface p-3 leading-6">
              {proposal.request}
            </p>
          </div>

          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-xs text-muted">Proposal ID</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                {proposal.proposal_id}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs text-muted">Contract ID</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                {proposal.contract_id || "Not selected"}
              </dd>
            </div>
          </dl>
        </div>
      </details>

      {!detail && (
        <Link
          href={`/agents/${proposal.proposal_id}`}
          prefetch={false}
          className="mt-5 inline-flex items-center gap-2 rounded-lg py-1 text-sm font-semibold text-accent underline underline-offset-4"
        >
          View saved proposal
          <span className="sr-only"> {proposal.proposal_id}</span>
          <span aria-hidden="true">→</span>
        </Link>
      )}
    </article>
  );
}
