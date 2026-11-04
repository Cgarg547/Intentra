"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import {
  AgentApiError, AgentProposal, confirmAgentProposal, createAgentProposal,
  evaluateAgentProposal, listAgentProposals, prepareAgentProposalPayment, rejectAgentProposal,
} from "@/lib/agents/client";
import { launchCheckout } from "@/lib/payments/client";

function policyLabel(decision: AgentProposal["policy_decision"]) {
  if (decision === "ALLOW") return "Allowed by current policy";
  if (decision === "DENY") return "Denied by current policy";
  return "Needs information";
}

export function AgentWorkspace() {
  const submissionRef = useRef<{ request: string; contractId: string; key: string } | null>(null);
  const [contracts, setContracts] = useState<IntentContract[]>([]);
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [contractId, setContractId] = useState("");
  const [requestText, setRequestText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async ({ preserveError = false }: { preserveError?: boolean } = {}): Promise<string | null> => {
    setLoading(true);
    if (!preserveError) setError("");
    try {
      const [contractResponse, proposalResponse] = await Promise.all([listContracts(), listAgentProposals()]);
      setContracts(contractResponse.items);
      setProposals(proposalResponse);
      return null;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Unable to load the AI Agents workspace.";
      if (!preserveError) setError(message);
      return message;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => refresh());
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !contractId) return;
    setBusy(true); setError(""); setNotice("");
    const submission = submissionRef.current?.request === requestText
      && submissionRef.current.contractId === contractId
      ? submissionRef.current
      : { request: requestText, contractId, key: crypto.randomUUID() };
    submissionRef.current = submission;
    try {
      const proposal = await createAgentProposal(requestText, contractId, submission.key);
      submissionRef.current = null;
      setProposals((current) => [proposal, ...current]);
      setRequestText("");
      setNotice("Proposal created and evaluated. Review its details before confirming.");
    } catch (caught) {
      // A response proves the request ended; a network failure does not. Keep
      // the same key for ambiguous transport errors so a retry is idempotent.
      if (caught instanceof AgentApiError && [422, 429, 503].includes(caught.status)) {
        submissionRef.current = null;
      }
      setError(caught instanceof Error ? caught.message : "Unable to create a proposal.");
    } finally { setBusy(false); }
  }

  async function act(id: string, action: "evaluate" | "confirm" | "reject" | "prepare") {
    if (busy) return;
    if (action === "confirm" && !window.confirm("Confirm this purchase proposal? This records your review only; it will not reserve funds or initiate payment.")) return;
    if (action === "reject" && !window.confirm("Reject this purchase proposal?")) return;
    if (action === "prepare" && !window.confirm("Prepare this payment? INTENTRA will reserve the approved budget and create a local payment attempt. It will not contact PayPal or start checkout.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = action === "evaluate" ? await evaluateAgentProposal(id)
        : action === "confirm" ? await confirmAgentProposal(id)
        : action === "prepare" ? await prepareAgentProposalPayment(id) : await rejectAgentProposal(id);
      setProposals((current) => current.map((item) => item.proposal_id === id ? updated : item));
      setNotice(action === "confirm" ? "Proposal confirmed. No payment was initiated." : action === "reject" ? "Proposal rejected." : action === "prepare" ? "Payment prepared and budget reserved. No PayPal order or checkout was created." : "Proposal re-evaluated against current policy.");
    } catch (caught) {
      const actionError = caught instanceof Error ? caught.message : "Unable to update this proposal.";
      const refreshError = await refresh({ preserveError: true });
      setError(refreshError ? `${actionError} ${refreshError}` : actionError);
    } finally { setBusy(false); }
  }

  async function continueToCheckout(proposal: AgentProposal) {
    const prepared = proposal.payment_preparation;
    if (busy || !prepared || !window.confirm("Continue to PayPal Sandbox? This may create or resume the provider checkout order. If a previous checkout request failed or timed out, do not retry until payment history and PayPal Sandbox activity have been reviewed. Capture remains a separate action.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const handoff = await launchCheckout(prepared.reservation_id);
      window.location.assign(handoff.approval_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to continue to checkout.");
    } finally { setBusy(false); }
  }

  const eligibleContracts = contracts.filter((contract) => contract.status === "APPROVED");

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-surface p-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">Purchase planning</p>
            <h2 className="mt-2 text-xl font-semibold">Describe what you need</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">The agent extracts a proposal. INTENTRA checks the selected contract and remaining budget, then you review the result.</p>
          </div>
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-700">No autonomous payments</span>
        </div>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-medium" htmlFor="purchase-request">Purchase request</label>
          <textarea id="purchase-request" value={requestText} onChange={(event) => setRequestText(event.target.value)} maxLength={4000} required rows={4} placeholder="For example: Purchase a replacement keyboard from merchant id: office_store for USD 85.00" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-accent" />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <label className="mb-2 block text-sm font-medium" htmlFor="contract-select">Apply approved contract</label>
              <select id="contract-select" value={contractId} onChange={(event) => setContractId(event.target.value)} required className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm">
                <option value="">Select a contract</option>
                {eligibleContracts.map((contract) => <option key={contract.id} value={contract.id}>{contract.merchant_id} · limit {contract.currency} {contract.maximum_amount}</option>)}
              </select>
            </div>
            <button type="submit" disabled={busy || loading || eligibleContracts.length === 0} className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Working…" : "Create proposal"}</button>
          </div>
          <p className="text-xs text-muted">Only details you state are extracted. Selecting a contract scopes the merchant; no product price or availability is assumed. When a real LLM is configured, this request text is sent to that provider for extraction. Do not include payment credentials or unrelated sensitive information.</p>
        </form>
        {eligibleContracts.length === 0 && !loading && <p className="mt-4 rounded-lg bg-surface-muted p-3 text-sm text-muted">No approved contracts are available. Create and approve an intent contract before planning a purchase.</p>}
      </section>

      {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm">{error}</div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm">{notice}</div>}

      <section aria-labelledby="proposal-history-heading" className="space-y-4">
        <div className="flex items-center justify-between gap-3"><div><h2 id="proposal-history-heading" className="text-xl font-semibold">Proposal history</h2><p className="mt-1 text-sm text-muted">Owner-scoped saved proposals and their latest deterministic policy result.</p></div><button type="button" onClick={() => void refresh()} disabled={loading || busy} className="rounded-lg border border-border px-3 py-2 text-sm">Refresh</button></div>
        {loading ? <div className="animate-pulse rounded-2xl border border-border bg-surface p-8 text-sm text-muted">Loading proposals…</div>
          : proposals.length === 0 ? <div className="rounded-2xl border border-border bg-surface p-8 text-sm text-muted">No proposals yet.</div>
          : proposals.map((proposal) => <article key={proposal.proposal_id} className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-muted">{proposal.provider_mode === "SIMULATED" ? "Simulated AI" : "Configured LLM"}</p><h3 className="mt-2 text-lg font-semibold">{proposal.requested_purpose || "Purchase proposal"}</h3></div>
              <span className="rounded-full bg-surface-muted px-3 py-1 text-xs font-semibold">{proposal.status.replaceAll("_", " ")}</span>
            </div>
            <blockquote className="mt-4 border-l-2 border-border pl-3 text-sm text-muted">{proposal.request}</blockquote>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-xs text-muted">Merchant</dt><dd className="mt-1 font-medium">{proposal.merchant_id || "Not specified"}</dd></div>
              <div><dt className="text-xs text-muted">Proposed amount</dt><dd className="mt-1 font-medium">{proposal.proposed_amount && proposal.currency ? `${proposal.currency} ${proposal.proposed_amount}` : "Not specified"}</dd></div>
              <div><dt className="text-xs text-muted">Contract</dt><dd className="mt-1 font-medium">{proposal.contract_id ? contracts.find((item) => item.id === proposal.contract_id)?.merchant_id || "Selected contract" : "Not selected"}</dd></div>
              <div><dt className="text-xs text-muted">Policy</dt><dd className="mt-1 font-medium">{policyLabel(proposal.policy_decision)}</dd></div>
            </dl>
            <p className="mt-4 text-sm leading-6">{proposal.policy_reason || proposal.explanation}</p>
            {proposal.missing_information.length > 0 && <p className="mt-2 text-sm text-amber-700">Missing: {proposal.missing_information.join(", ")}</p>}
            <div className="mt-5 flex flex-wrap gap-2">
              {!['CONFIRMED', 'REJECTED'].includes(proposal.status) && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "evaluate")} className="rounded-lg border border-border px-4 py-2 text-sm">Re-evaluate</button>}
              {proposal.status === "READY_FOR_REVIEW" && proposal.policy_decision === "ALLOW" && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "confirm")} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground">Confirm proposal</button>}
              {!['CONFIRMED', 'REJECTED'].includes(proposal.status) && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "reject")} className="rounded-lg border border-border px-4 py-2 text-sm">Reject</button>}
              {proposal.status === "CONFIRMED" && proposal.policy_decision === "ALLOW" && !proposal.payment_preparation && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "prepare")} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground">Prepare payment</button>}
            </div>
            {proposal.status === "CONFIRMED" && !proposal.payment_preparation && <p className="mt-4 rounded-lg bg-surface-muted p-3 text-sm">Owner confirmed this plan. Payment has not been reserved or initiated.</p>}
            {proposal.payment_preparation && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface-muted p-4"><div><p className="text-sm font-semibold">Payment prepared</p><p className="mt-1 text-sm text-muted">Budget is reserved and a payment attempt exists. INTENTRA has not confirmed a PayPal order or buyer approval. If a previous checkout request failed or timed out, review Payments and PayPal Sandbox activity before retrying.</p><p className="mt-1 text-xs text-muted">Reservation {proposal.payment_preparation.reservation_id} · {proposal.payment_preparation.status.replaceAll("_", " ")}</p></div>{proposal.payment_preparation.status === "EXECUTION_PENDING" && <button type="button" disabled={busy} onClick={() => void continueToCheckout(proposal)} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground">Continue to checkout</button>}</div>}
          </article>)}
      </section>
    </div>
  );
}
