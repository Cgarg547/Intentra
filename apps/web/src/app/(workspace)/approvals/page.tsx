"use client";

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
      : <div className="space-y-4">{visible.map((proposal) => <article key={proposal.proposal_id} className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><span className="rounded-full border border-border px-2.5 py-1 text-xs font-semibold">{proposal.status}</span><h2 className="mt-3 text-lg font-semibold">{proposal.requested_purpose || "Purchase proposal"}</h2><p className="mt-1 text-sm text-muted">{proposal.provider_mode === "SIMULATED" ? "Simulated extraction" : "Configured model extraction"} · version {proposal.version}</p></div>
          <div className="text-right"><p className="text-2xl font-semibold">{proposal.proposed_amount && proposal.currency ? new Intl.NumberFormat(undefined, { style: "currency", currency: proposal.currency }).format(Number(proposal.proposed_amount)) : "Amount missing"}</p><p className="mt-1 text-xs text-muted">{proposal.merchant_id || "Merchant missing"}</p></div></div>
        <dl className="mt-5 grid gap-4 border-t border-border pt-4 text-sm sm:grid-cols-2"><div><dt className="text-xs text-muted">Contract</dt><dd className="mt-1 break-all">{proposal.contract_id ?? "Not selected"}{proposal.contract_version ? ` · version ${proposal.contract_version}` : ""}</dd></div><div><dt className="text-xs text-muted">Policy evaluation</dt><dd className="mt-1">{proposal.policy_decision ?? "Not evaluated"} · {proposal.policy_reason || "No policy explanation available."}</dd></div><div className="sm:col-span-2"><dt className="text-xs text-muted">Request</dt><dd className="mt-1">{proposal.request}</dd></div>{proposal.missing_information.length > 0 && <div className="sm:col-span-2"><dt className="text-xs text-muted">Missing information</dt><dd className="mt-1">{proposal.missing_information.join(", ")}</dd></div>}</dl>
        {proposal.status === "READY_FOR_REVIEW" && <div className="mt-5 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-end sm:justify-between"><label className="flex-1 space-y-1 text-sm"><span>Rejection reason (required to reject)</span><input value={reasons[proposal.proposal_id] ?? ""} maxLength={500} onChange={(event) => setReasons((current) => ({ ...current, [proposal.proposal_id]: event.target.value }))} className="w-full rounded-xl border border-border bg-background px-3 py-2.5" /></label><div className="flex gap-2"><button type="button" disabled={working !== null || proposal.policy_decision !== "ALLOW"} onClick={() => void decide(proposal, "confirm")} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working === proposal.proposal_id ? "Saving…" : "Confirm proposal"}</button><button type="button" disabled={working !== null || !reasons[proposal.proposal_id]?.trim()} onClick={() => void decide(proposal, "reject")} className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Reject</button></div></div>}
        {(proposal.events?.length ?? 0) > 0 && <details className="mt-4 border-t border-border pt-3"><summary className="cursor-pointer text-sm font-medium">Decision history ({proposal.events?.length ?? 0})</summary><ol className="mt-3 space-y-2">{proposal.events?.map((event, index) => <li key={`${event.event_type}-${index}`} className="rounded-lg bg-surface-muted p-3 text-sm"><span className="font-medium">{event.event_type}</span><span className="ml-2 text-xs text-muted">{new Date(event.created_at).toLocaleString()}</span><p className="mt-1 break-all text-xs text-muted">Actor: {event.actor_id ?? "System"}</p>{event.event_data.reason !== undefined && <p className="mt-1 text-muted">Reason: {String(event.event_data.reason)}</p>}</li>)}</ol></details>}
      </article>)}</div>}
  </section>;
}
