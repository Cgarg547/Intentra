"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AgentApiError, getAgentProposal, type AgentProposal } from "@/lib/agents/client";
import { ProposalCard } from "./proposal-card";

export function ProposalDetail({ proposalId }: { proposalId: string }) {
  const [proposal, setProposal] = useState<AgentProposal | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
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
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><Link href="/agents" className="rounded-lg py-1 text-sm font-semibold text-accent underline">← Back to AI Purchasing Assistant</Link><button type="button" disabled={loading} onClick={() => { setError(""); setLoading(true); setRevision((value) => value + 1); }} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Refresh proposal</button></div>
    <header><p className="text-xs font-semibold uppercase tracking-widest text-accent">Saved proposal</p><h1 className="mt-3 text-3xl font-semibold tracking-tight">Proposal details</h1><p className="mt-3 text-sm text-muted">This read-only view shows the persisted policy result. Viewing it does not authorize or initiate payment.</p></header>
    {loading && <p role="status" className="rounded-xl border border-border bg-surface p-6 text-sm">Loading saved proposal…</p>}
    {error && <div role="alert" className="rounded-xl border border-border bg-surface p-5 text-sm">{error}<Link href="/account" className="ml-2 text-accent underline">Account access</Link></div>}
    {!loading && !error && proposal && <ProposalCard proposal={proposal} detail />}
  </div>;
}
