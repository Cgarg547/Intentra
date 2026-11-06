"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AgentApiError, confirmAgentProposal, evaluateAgentProposal, getAgentProposal,
  prepareAgentProposalPayment, rejectAgentProposal, type AgentProposal,
} from "@/lib/agents/client";
import { launchCheckout } from "@/lib/payments/client";
import { ProposalCard } from "./proposal-card";

export function ProposalDetail({ proposalId }: { proposalId: string }) {
  const [proposal, setProposal] = useState<AgentProposal | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [working, setWorking] = useState<"evaluate" | "confirm" | "reject" | "prepare" | "checkout" | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getAgentProposal(proposalId, controller.signal).then((result) => {
      if (active) setProposal(result);
    }).catch((cause: unknown) => {
      if (!active) return;
      if (cause instanceof AgentApiError && cause.status === 404) setError("This proposal is unavailable to your account.");
      else setError(cause instanceof AgentApiError ? cause.message : "Unable to load this proposal. Check your connection and refresh.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [proposalId, revision]);
  async function action(kind: NonNullable<typeof working>) {
    if (!proposal || working) return;
    if (kind === "confirm" && !window.confirm("Confirm this proposal? This records human review only; it does not reserve budget or contact PayPal.")) return;
    if (kind === "prepare" && !window.confirm("Prepare this payment? INTENTRA will reserve approved budget and create a local payment attempt. It will not contact PayPal.")) return;
    if (kind === "checkout" && !window.confirm("Continue to PayPal Sandbox? This may create or resume the existing provider order. If a prior checkout was uncertain, review payment history before continuing.")) return;
    if (kind === "reject" && !rejectReason.trim()) { setError("Add a short reason before rejecting this proposal."); return; }
    setWorking(kind); setError(""); setNotice("");
    try {
      if (kind === "checkout") {
        if (!proposal.payment_preparation) return;
        const handoff = await launchCheckout(proposal.payment_preparation.reservation_id);
        window.location.assign(handoff.approval_url);
        return;
      }
      const updated = kind === "evaluate" ? await evaluateAgentProposal(proposal.proposal_id)
        : kind === "confirm" ? await confirmAgentProposal(proposal.proposal_id)
          : kind === "reject" ? await rejectAgentProposal(proposal.proposal_id, rejectReason.trim())
            : await prepareAgentProposalPayment(proposal.proposal_id);
      setProposal(updated);
      setRejectReason("");
      setNotice(kind === "evaluate" ? "Policy evaluation refreshed using the current saved proposal."
        : kind === "confirm" ? "Proposal confirmed. No payment was initiated."
          : kind === "reject" ? "Proposal rejection was recorded in the audit history."
            : "Payment prepared and budget reserved. No PayPal order or buyer approval was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update this proposal. Refresh its saved state before trying again.");
    } finally { setWorking(null); }
  }

  const canEvaluate = proposal && !["CONFIRMED", "REJECTED"].includes(proposal.status);
  const canConfirm = proposal?.status === "READY_FOR_REVIEW" && proposal.policy_decision === "ALLOW";
  const canPrepare = proposal?.status === "CONFIRMED" && proposal.policy_decision === "ALLOW" && !proposal.payment_preparation;
  const canCheckout = proposal?.payment_preparation?.status === "EXECUTION_PENDING";

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><Link href="/agents" className="rounded-lg py-1 text-sm font-semibold text-accent underline">← Back to AI Purchasing Assistant</Link><button type="button" disabled={loading} onClick={() => { setError(""); setLoading(true); setRevision((value) => value + 1); }} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Refresh proposal</button></div>
    <header><p className="text-xs font-semibold uppercase tracking-widest text-accent">Saved proposal</p><h1 className="mt-3 text-3xl font-semibold tracking-tight">Proposal details</h1><p className="mt-3 text-sm text-muted">This read-only view shows the persisted policy result. Viewing it does not authorize or initiate payment.</p></header>
    {loading && <p role="status" className="rounded-xl border border-border bg-surface p-6 text-sm">Loading saved proposal…</p>}
    {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-surface p-5 text-sm text-red-600">{error}<Link href="/account" className="ml-2 text-accent underline">Account access</Link></div>}
    {notice && <p role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{notice}</p>}
    {!loading && proposal && <ProposalCard proposal={proposal} detail actions={<section aria-labelledby="proposal-actions" className="mt-5 border-t border-border pt-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="proposal-actions" className="text-sm font-semibold">Workflow actions</h2><p className="mt-1 max-w-xl text-xs leading-5 text-muted">Each transition is recorded separately. Payment preparation only reserves budget; checkout and capture are distinct actions.</p></div>{proposal.payment_preparation && <Link href="/payments" className="text-sm font-semibold text-accent underline">View payment history</Link>}</div>{canEvaluate && <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={working !== null} onClick={() => void action("evaluate")} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold disabled:opacity-50">{working === "evaluate" ? "Evaluating…" : "Re-evaluate policy"}</button>{canConfirm && <button type="button" disabled={working !== null} onClick={() => void action("confirm")} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working === "confirm" ? "Confirming…" : "Confirm proposal"}</button>}<button type="button" disabled={working !== null} onClick={() => { setRejectReason(""); setError(""); document.getElementById("proposal-reject-reason")?.focus(); }} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold disabled:opacity-50">Reject proposal</button></div>}{canEvaluate && <label className="mt-4 block max-w-xl text-sm"><span className="font-medium">Rejection reason</span><span className="ml-1 text-muted">(required only when rejecting)</span><div className="mt-2 flex flex-col gap-2 sm:flex-row"><input id="proposal-reject-reason" value={rejectReason} maxLength={500} onChange={(event) => setRejectReason(event.target.value)} placeholder="Why this proposal should not proceed" className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2" /><button type="button" disabled={working !== null || !rejectReason.trim()} onClick={() => void action("reject")} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold disabled:opacity-50">{working === "reject" ? "Rejecting…" : "Record rejection"}</button></div></label>}{canPrepare && <button type="button" disabled={working !== null} onClick={() => void action("prepare")} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working === "prepare" ? "Preparing…" : "Prepare payment"}</button>}{canCheckout && <button type="button" disabled={working !== null} onClick={() => void action("checkout")} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working === "checkout" ? "Preparing checkout…" : "Continue to PayPal Sandbox"}</button>}</section>} />}
  </div>;
}
