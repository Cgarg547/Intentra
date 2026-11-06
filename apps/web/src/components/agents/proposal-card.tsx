import Link from "next/link";
import { FileText, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { AgentProposal } from "@/lib/agents/client";

export function policyLabel(decision: AgentProposal["policy_decision"]) {
  if (decision === "ALLOW") return "Allowed by current policy";
  if (decision === "DENY") return "Denied by current policy";
  if (decision === "NEEDS_INFORMATION") return "Needs information";
  return "Not evaluated";
}

function statusLabel(status: string) {
  return status.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function ProposalCard({ proposal, actions, detail = false }: {
  proposal: AgentProposal;
  actions?: ReactNode;
  detail?: boolean;
}) {
  const prepared = proposal.payment_preparation;
  return (
    <article id={`proposal-${proposal.proposal_id}`} aria-label={`Proposal ${proposal.proposal_id}`} className="min-w-0 scroll-mt-24 rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted"><FileText size={15} aria-hidden="true" />{proposal.provider_mode === "SIMULATED" ? "Simulated AI" : proposal.provider_mode}</p>
          <h3 className="mt-3 break-words text-lg font-semibold">{proposal.requested_purpose || "Purchase proposal"}</h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${proposal.status === "NEEDS_INFORMATION" ? "border-accent/40 bg-accent/10 text-foreground" : "border-border bg-surface-muted"}`}>{statusLabel(proposal.status)}</span>
      </div>
      <dl className="mt-5 grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
        <div className="min-w-0"><dt className="text-xs text-muted">Proposal ID</dt><dd className="mt-1 break-all font-mono text-xs">{proposal.proposal_id}</dd></div>
        <div><dt className="text-xs text-muted">Created</dt><dd className="mt-1"><time dateTime={proposal.created_at}>{new Date(proposal.created_at).toLocaleString()}</time></dd></div>
        <div><dt className="text-xs text-muted">Merchant</dt><dd className="mt-1 break-words font-medium">{proposal.merchant_id || "Not specified"}</dd></div>
        <div><dt className="text-xs text-muted">Amount and currency</dt><dd className="mt-1 font-medium">{[proposal.currency, proposal.proposed_amount].filter((value) => value != null && value !== "").join(" ") || "Not specified"}</dd></div>
        <div><dt className="text-xs text-muted">Policy decision</dt><dd className="mt-1 font-medium">{policyLabel(proposal.policy_decision)}</dd></div>
        <div className="min-w-0"><dt className="text-xs text-muted">Contract</dt><dd className="mt-1 break-all text-xs">{proposal.contract_id || "Not selected"}</dd></div>
      </dl>
      <div className="mt-5 rounded-xl border border-border bg-surface-muted p-4">
        <p className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={17} aria-hidden="true" />Policy explanation</p>
        <p className="mt-2 text-sm leading-6">{proposal.policy_reason || (proposal.status === "DRAFT" ? "No completed policy evaluation is available. Refresh this saved proposal to check its latest state." : proposal.explanation)}</p>
        {proposal.missing_information.length > 0 && <div className="mt-3"><p className="text-xs font-semibold text-muted">Missing information</p><ul className="mt-2 flex flex-wrap gap-2" aria-label="Missing information">{proposal.missing_information.map((item, index) => <li key={`${item}-${index}`} className="rounded-lg border border-border bg-surface px-2 py-1 text-xs">{item}</li>)}</ul></div>}
      </div>
      <details className="mt-4 text-sm"><summary className="cursor-pointer rounded-lg py-1 text-muted">Original request</summary><p className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-surface-muted p-4 leading-6">{proposal.request}</p></details>
      {proposal.status === "CONFIRMED" && !prepared && <p className="mt-4 rounded-lg bg-surface-muted p-3 text-sm">Owner confirmed this plan. Payment has not been reserved or initiated.</p>}
      {prepared && <div className="mt-4 rounded-xl border border-border p-4"><p className="text-sm font-semibold">Payment prepared</p><p className="mt-2 text-sm text-muted">Budget is reserved and a payment attempt exists. INTENTRA has not confirmed a PayPal order or buyer approval. Review Payments before taking any further action.</p><p className="mt-2 break-all text-xs text-muted">Reservation {prepared.reservation_id} · {statusLabel(prepared.status)}</p></div>}
      {actions}
      {!detail && <Link href={`/agents/${proposal.proposal_id}`} prefetch={false} className="mt-5 inline-flex items-center gap-2 rounded-lg py-1 text-sm font-semibold text-accent underline underline-offset-4">View saved proposal<span className="sr-only"> {proposal.proposal_id}</span><span aria-hidden="true">→</span></Link>}
    </article>
  );
}
