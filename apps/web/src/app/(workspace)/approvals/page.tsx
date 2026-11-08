"use client";

import { ApprovalOverview } from "@/components/approval-overview";
import { ProposalReviewCard } from "@/components/approvals/proposal-review-card";
import { useCallback, useEffect, useMemo, useState } from "react";
import { confirmAgentProposal, listAgentProposals, rejectAgentProposal, type AgentProposal } from "@/lib/agents/client";

export default function ApprovalsPage() {
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [showHistory, setShowHistory] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { setProposals(await listAgentProposals()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load proposal reviews."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    listAgentProposals().then((result) => { if (active) setProposals(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load proposal reviews."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const visible = useMemo(() => proposals.filter((proposal) => showHistory
    ? ["CONFIRMED", "REJECTED"].includes(proposal.status)
    : proposal.status === "READY_FOR_REVIEW"), [proposals, showHistory]);

  async function decide(proposal: AgentProposal, action: "confirm" | "reject") {
    if (action === "confirm" && !window.confirm("Confirm this proposal for possible payment preparation? This will not create a reservation or contact PayPal.")) return;
    if (action === "reject" && !reasons[proposal.proposal_id]?.trim()) {
      setError("Add a short reason before rejecting this proposal."); return;
    }
    setWorking(proposal.proposal_id); setError(null); setMessage(null);
    try {
      if (action === "confirm") await confirmAgentProposal(proposal.proposal_id);
      else await rejectAgentProposal(proposal.proposal_id, reasons[proposal.proposal_id]);
      setMessage(action === "confirm"
        ? "Proposal confirmed. This did not prepare a payment or approve a PayPal order."
        : "Proposal rejected and recorded in its audit history.");
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The decision could not be saved."); }
    finally { setWorking(null); }
  }

  return <section className="space-y-6">
    <ApprovalOverview proposals={proposals} loading={loading} />

    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-accent">Human review</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Approval Center</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">Review AI purchase proposals. Confirming a proposal authorizes no payment, PayPal buyer approval, or capture.</p></div>
      <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setShowHistory(false)} aria-pressed={!showHistory} className={`rounded-xl px-4 py-2 text-sm ${!showHistory ? "bg-accent text-accent-foreground" : "border border-border"}`}>Review queue</button>
        <button type="button" onClick={() => setShowHistory(true)} aria-pressed={showHistory} className={`rounded-xl px-4 py-2 text-sm ${showHistory ? "bg-accent text-accent-foreground" : "border border-border"}`}>Decision history</button>
        <button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-xl border border-border px-4 py-2 text-sm">Refresh</button></div>
    </header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{message}</p>}
    {loading ? <div role="status" className="animate-pulse rounded-2xl border border-border bg-surface p-8 text-sm text-muted">Loading owner-scoped proposals…</div>
      : visible.length === 0 ? <div className="rounded-2xl border border-border bg-surface p-8"><h2 className="font-semibold">{showHistory ? "No decisions recorded" : "Review queue is clear"}</h2><p className="mt-2 text-sm text-muted">{showHistory ? "Proposal decisions will appear here." : "Proposals ready for your review will appear here."}</p></div>
      : <div className="space-y-4">
          {visible.map((proposal) => (
            <ProposalReviewCard
              key={proposal.proposal_id}
              proposal={proposal}
              working={working !== null}
              saving={working === proposal.proposal_id}
              reason={reasons[proposal.proposal_id] ?? ""}
              onReasonChange={(value) =>
                setReasons((current) => ({
                  ...current,
                  [proposal.proposal_id]: value,
                }))
              }
              onConfirm={() => void decide(proposal, "confirm")}
              onReject={() => void decide(proposal, "reject")}
            />
          ))}
        </div>}
  </section>;
}
