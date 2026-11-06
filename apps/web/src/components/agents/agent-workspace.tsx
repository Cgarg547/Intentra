"use client";

import Link from "next/link";
import { Clock3, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import {
  AgentApiError, AgentProposal, confirmAgentProposal, createAgentProposal,
  evaluateAgentProposal, listAgentProposals, prepareAgentProposalPayment, rejectAgentProposal,
} from "@/lib/agents/client";
import { launchCheckout } from "@/lib/payments/client";
import { ProposalCard } from "./proposal-card";

// Outlast the proxy's 330s inactivity limit, with a finite browser wait.
export const PROPOSAL_WAIT_MS = 340_000;
const examples = [
  { label: "Explore a request", text: "Synthetic planning example: describe a replacement keyboard. No merchant, amount, or currency is provided." },
  { label: "Include explicit details", text: "Synthetic example: purchase a notebook from merchant id: demo_stationery for USD 12.00." },
];

type Attempt = { key: string; controller: AbortController; stopped: boolean; timedOut: boolean; sessionChanged: boolean };

export function AgentWorkspace() {
  const operationRef = useRef(false);
  const attemptRef = useRef<Attempt | null>(null);
  const refreshVersion = useRef(0);
  const [contracts, setContracts] = useState<IntentContract[]>([]);
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [contractId, setContractId] = useState("");
  const [requestText, setRequestText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [contractError, setContractError] = useState("");
  const [notice, setNotice] = useState("");
  const [latestId, setLatestId] = useState<string | null>(null);
  const [uncertainKey, setUncertainKey] = useState<string | null>(null);
  const [historyReviewed, setHistoryReviewed] = useState(false);

  const refresh = useCallback(async () => {
    const version = ++refreshVersion.current;
    setLoading(true);
    setHistoryError("");
    const [saved, available] = await Promise.allSettled([listAgentProposals(), listContracts()]);
    if (version !== refreshVersion.current) return;
    if (saved.status === "fulfilled") {
      setProposals(saved.value);
      setAuthenticated(true);
      setHistoryReviewed(true);
    } else {
      if (saved.reason instanceof AgentApiError && saved.reason.status === 401) {
        setAuthenticated(false);
        setProposals([]);
      }
      setHistoryError(saved.reason instanceof Error ? saved.reason.message : "Unable to load proposal history. Refresh to check saved requests.");
      setHistoryReviewed(false);
    }
    if (available.status === "fulfilled") {
      setContracts(available.value.items);
      setContractError("");
    } else {
      setContracts([]);
      setContractId("");
      setContractError("Contracts could not be loaded. You can still create a proposal without a contract.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void Promise.resolve().then(refresh);
    const changed = () => {
      const attempt = attemptRef.current;
      if (attempt) { attempt.sessionChanged = true; attempt.controller.abort(); }
      setAuthenticated(false);
      setProposals([]);
      setContracts([]);
      setLatestId(null);
      setNotice("");
      void refresh();
    };
    window.addEventListener("intentra:auth-changed", changed);
    const invalidatePending = () => {
      ++refreshVersion.current;
      attemptRef.current?.controller.abort();
    };
    return () => {
      invalidatePending();
      window.removeEventListener("intentra:auth-changed", changed);
    };
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // A ref closes the gap before React's disabled state reaches the DOM.
    if (operationRef.current || !authenticated || uncertainKey) return;
    const trimmed = requestText.trim();
    if (!trimmed || trimmed.length > 4000) {
      setError("Enter a request between 1 and 4,000 characters.");
      return;
    }
    const attempt: Attempt = { key: crypto.randomUUID(), controller: new AbortController(), stopped: false, timedOut: false, sessionChanged: false };
    attemptRef.current = attempt;
    operationRef.current = true;
    setBusy(true); setGenerating(true); setElapsed(0); setError(""); setNotice("");
    const started = performance.now();
    const ticker = window.setInterval(() => setElapsed(Math.floor((performance.now() - started) / 1000)), 1000);
    const deadline = window.setTimeout(() => { attempt.timedOut = true; attempt.controller.abort(); }, PROPOSAL_WAIT_MS);
    try {
      const proposal = await createAgentProposal(trimmed, contractId || null, attempt.key, attempt.controller.signal);
      // Ignore any late completion after the user chose to stop waiting.
      if (attempt.stopped || attempt.timedOut || attempt.sessionChanged) return;
      ++refreshVersion.current;
      setLoading(false);
      setProposals((current) => [proposal, ...current.filter((item) => item.proposal_id !== proposal.proposal_id)]);
      setLatestId(proposal.proposal_id);
      setRequestText("");
      setNotice("Proposal created and evaluated. Review the saved result below. No payment was initiated.");
    } catch (caught) {
      if (attempt.sessionChanged) setError("Your session changed while waiting. Sign in and refresh history to check the saved result.");
      else if (attempt.stopped) setError("You stopped waiting. The server may still finish this request.");
      else if (attempt.timedOut) setError("The waiting limit was reached. The request was not retried.");
      else if (caught instanceof AgentApiError) {
        setError(caught.status >= 500 ? "The service could not complete the response. Refresh history to check whether a proposal was saved." : caught.message);
        if (caught.status === 401) { setAuthenticated(false); setProposals([]); }
      } else setError("The connection was interrupted. The request was not retried.");
      const ambiguous = !(caught instanceof AgentApiError) || caught.status >= 500 || caught.status === 200 || caught.status === 409;
      if (ambiguous) { setUncertainKey(attempt.key); setHistoryReviewed(false); }
    } finally {
      window.clearInterval(ticker);
      window.clearTimeout(deadline);
      // Even if a response races an abort, preserve the uncertain outcome.
      if (attempt.stopped || attempt.timedOut || attempt.sessionChanged) { setUncertainKey(attempt.key); setHistoryReviewed(false); }
      if (attemptRef.current === attempt) attemptRef.current = null;
      operationRef.current = false;
      setBusy(false); setGenerating(false);
    }
  }

  function stopWaiting() {
    const attempt = attemptRef.current;
    if (!attempt) return;
    attempt.stopped = true;
    attempt.controller.abort();
  }

  // Existing review actions remain explicit and separate from generation.
  async function act(id: string, action: "evaluate" | "confirm" | "reject" | "prepare") {
    if (operationRef.current) return;
    if (action === "confirm" && !window.confirm("Confirm this purchase proposal? This records your review only; it will not reserve funds or initiate payment.")) return;
    if (action === "reject" && !window.confirm("Reject this purchase proposal?")) return;
    if (action === "prepare" && !window.confirm("Prepare this payment? INTENTRA will reserve the approved budget and create a local payment attempt. It will not contact PayPal or start checkout.")) return;
    operationRef.current = true;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = action === "evaluate" ? await evaluateAgentProposal(id)
        : action === "confirm" ? await confirmAgentProposal(id)
        : action === "prepare" ? await prepareAgentProposalPayment(id) : await rejectAgentProposal(id);
      setProposals((current) => current.map((item) => item.proposal_id === id ? updated : item));
      setNotice(action === "confirm" ? "Proposal confirmed. No payment was initiated." : action === "reject" ? "Proposal rejected." : action === "prepare" ? "Payment prepared and budget reserved. No PayPal order or checkout was created." : "Proposal re-evaluated against current policy.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update this proposal.");
      await refresh();
    } finally { operationRef.current = false; setBusy(false); }
  }

  async function continueToCheckout(proposal: AgentProposal) {
    const prepared = proposal.payment_preparation;
    if (operationRef.current || !prepared || !window.confirm("Continue to PayPal Sandbox? This may create or resume the provider checkout order. If a previous checkout request failed or timed out, do not retry until payment history and PayPal Sandbox activity have been reviewed. Capture remains a separate action.")) return;
    operationRef.current = true;
    setBusy(true); setError("");
    try {
      const handoff = await launchCheckout(prepared.reservation_id);
      window.location.assign(handoff.approval_url);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to continue to checkout."); }
    finally { operationRef.current = false; setBusy(false); }
  }

  const eligibleContracts = contracts.filter((contract) => contract.status === "APPROVED");
  const latestProposal = latestId ? proposals.find((proposal) => proposal.proposal_id === latestId) ?? null : null;
  return (
    <div className="space-y-7">
      <section aria-labelledby="request-heading" className="overflow-hidden rounded-2xl border border-border bg-surface">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_16rem]">
          <div className="min-w-0 p-5 sm:p-7">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-accent"><Sparkles size={16} aria-hidden="true" />01 / Describe your request</p>
            <h2 id="request-heading" className="mt-3 text-xl font-semibold">A considered plan starts with your intent.</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Describe what you need. AI extracts the details; INTENTRA evaluates them against deterministic policy.</p>
            {!loading && !authenticated && <div className="mt-5 rounded-xl border border-border bg-surface-muted p-4 text-sm"><Link href="/account" className="font-semibold text-accent underline">Sign in to your account</Link><p className="mt-1 text-muted">Your proposals and contracts are visible only to you.</p></div>}
            <form onSubmit={submit} className="mt-6 space-y-4" aria-busy={generating}>
              <div className="flex items-baseline justify-between gap-3"><label className="text-sm font-semibold" htmlFor="purchase-request">Purchase request</label><span id="request-count" className="text-xs tabular-nums text-muted">{requestText.length.toLocaleString()} / 4,000</span></div>
              <textarea id="purchase-request" value={requestText} onChange={(event) => setRequestText(event.target.value)} maxLength={4000} required rows={5} disabled={busy} aria-describedby="request-count request-help" placeholder="What do you need? Include a purpose, merchant, amount and currency if known." className="w-full resize-y rounded-xl border border-border bg-background px-4 py-3 text-sm leading-6 disabled:opacity-60" />
              <div className="flex flex-wrap gap-2" aria-label="Synthetic example prompts">{examples.map((example) => <button key={example.label} type="button" disabled={busy} onClick={() => setRequestText(example.text)} className="rounded-lg border border-border px-3 py-2 text-xs text-muted hover:bg-surface-muted disabled:opacity-50">{example.label}</button>)}</div>
              <div><label className="mb-2 block text-sm font-semibold" htmlFor="contract-select">Apply approved contract <span className="font-normal text-muted">(optional)</span></label><select id="contract-select" value={contractId} onChange={(event) => setContractId(event.target.value)} disabled={busy} aria-describedby="contract-help" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm disabled:opacity-60"><option value="">No contract selected</option>{eligibleContracts.map((contract) => <option key={contract.id} value={contract.id}>{contract.merchant_id} · limit {contract.currency} {contract.maximum_amount}</option>)}</select><p id="contract-help" className="mt-2 text-xs leading-5 text-muted">Without an approved contract, the result will need more information before it can be confirmed.</p>{contractError && <p className="mt-2 text-xs text-muted">{contractError}</p>}</div>
              <p id="request-help" className="text-xs leading-5 text-muted">Your request is sent to the configured AI provider. Include only relevant purchase details; leave out passwords, payment credentials and unrelated personal information.</p>
              <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4"><button type="submit" disabled={busy || loading || !authenticated || !!uncertainKey} className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50">{generating ? "Creating proposal…" : "Create proposal"}</button>{generating && <button type="button" onClick={stopWaiting} className="rounded-xl border border-border px-4 py-3 text-sm font-semibold">Stop waiting</button>}<span className="text-xs text-muted">Creates a saved proposal and policy evaluation.</span></div>
              {generating && <div className="rounded-xl bg-surface-muted p-4"><p role="status" className="flex items-center gap-2 text-sm"><Clock3 size={16} aria-hidden="true" />Waiting for the AI response… <span className="tabular-nums">{elapsed}s</span></p><p className="mt-2 text-xs leading-5 text-muted">Local models can take a few minutes. Stopping only ends this browser wait; it does not guarantee the server stopped or that nothing was saved.</p></div>}
            </form>
          </div>
          <aside aria-label="How proposals work" className="border-t border-border bg-surface-muted p-5 sm:p-7 lg:border-t-0 lg:border-l"><ShieldCheck className="text-accent" size={25} aria-hidden="true" /><h3 className="mt-3 text-sm font-semibold">Your review stays in control</h3><ol className="mt-5 space-y-5 text-sm"><li><span className="font-semibold">1. Describe</span><p className="mt-1 text-xs leading-5 text-muted">AI extracts only the details you provide.</p></li><li><span className="font-semibold">2. Evaluate</span><p className="mt-1 text-xs leading-5 text-muted">Policy checks produce a saved result.</p></li><li><span className="font-semibold">3. Review</span><p className="mt-1 text-xs leading-5 text-muted">Confirmation and payment are separate actions.</p></li></ol><p className="mt-6 border-t border-border pt-4 text-xs font-semibold leading-5">Creating a proposal does not reserve funds or initiate a payment.</p></aside>
        </div>
      </section>
      {error && <div role="alert" className="rounded-xl border border-red-500/50 bg-surface p-4 text-sm">{error}{!authenticated && <Link href="/account" className="ml-2 font-semibold text-accent underline">Sign in</Link>}</div>}
      {uncertainKey && <section aria-label="Interrupted request" className="rounded-xl border border-accent/40 bg-surface p-5"><h2 className="text-sm font-semibold">Check saved history before starting again</h2><p className="mt-2 text-sm leading-6 text-muted">An interrupted request may still have created a proposal. No automatic retry was sent. Refresh history to inspect the result; starting again could create a duplicate.</p><p className="mt-2 break-all font-mono text-xs text-muted">Submission reference: {uncertainKey}</p><button type="button" disabled={!historyReviewed || loading || busy} onClick={() => { setUncertainKey(null); setError(""); setHistoryReviewed(false); }} className="mt-4 rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50">I reviewed history — start a new request</button></section>}
      <div aria-live="polite" aria-atomic="true">{notice && <p className="rounded-xl border border-accent/40 bg-surface p-4 text-sm">{notice}{latestId && <a href={`#proposal-${latestId}`} className="ml-2 font-semibold text-accent underline">View result</a>}</p>}</div>
      {latestProposal && <section aria-label="New proposal result" className="rounded-2xl border border-accent/40 bg-surface p-5 sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">Proposal created</p>
        <h2 className="mt-2 text-xl font-semibold">{latestProposal.status === "READY_FOR_REVIEW" && latestProposal.policy_decision === "ALLOW" ? "Ready for human approval" : "More information is needed"}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{latestProposal.status === "READY_FOR_REVIEW" && latestProposal.policy_decision === "ALLOW"
          ? "A person must still review and explicitly confirm this proposal. Creating it did not reserve funds or initiate payment."
          : "Review the saved policy result to see which purchase details need clarification. Creating it did not reserve funds or initiate payment."}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href={`/agents/${latestProposal.proposal_id}`} prefetch={false} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground">Review saved proposal</Link>
          {latestProposal.status === "READY_FOR_REVIEW" && latestProposal.policy_decision === "ALLOW" && <Link href="/approvals" className="rounded-lg border border-border px-4 py-2 text-sm font-semibold">Open Approval Center</Link>}
        </div>
      </section>}
      <section aria-labelledby="proposal-history-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-accent">02 / Saved results</p><h2 id="proposal-history-heading" className="mt-2 text-xl font-semibold">Proposal history</h2><p className="mt-1 text-sm text-muted">Your latest saved proposals, including requests that need more information.</p></div><button type="button" onClick={() => void refresh()} disabled={loading || busy} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm disabled:opacity-50"><RefreshCw size={15} aria-hidden="true" />Refresh</button></div>
        {historyError && <p role="alert" className="rounded-xl border border-border bg-surface p-4 text-sm">{historyError}{!authenticated && <Link href="/account" className="ml-2 font-semibold text-accent underline">Sign in to view proposals</Link>}</p>}
        {loading && <p role="status" className="rounded-2xl border border-border bg-surface p-8 text-sm text-muted">Loading proposals…</p>}
        {!loading && !historyError && proposals.length === 0 && <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center"><FileEmpty /><h3 className="mt-3 font-semibold">No proposals yet.</h3><p className="mt-2 text-sm text-muted">Describe your first request above. You can start without a contract.</p></div>}
        {proposals.map((proposal) => <ProposalCard key={proposal.proposal_id} proposal={proposal} actions={<details open className="mt-5 border-t border-border pt-4"><summary className="cursor-pointer rounded-lg py-1 text-sm font-semibold">Review actions</summary><p className="mt-2 text-xs leading-5 text-muted">These actions are separate from proposal creation. Preparing payment reserves budget; checkout is a further explicit action.</p><div className="mt-3 flex flex-wrap gap-2">
          {!['CONFIRMED', 'REJECTED'].includes(proposal.status) && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "evaluate")} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Re-evaluate</button>}
          {proposal.status === "READY_FOR_REVIEW" && proposal.policy_decision === "ALLOW" && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "confirm")} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Confirm proposal</button>}
          {!['CONFIRMED', 'REJECTED'].includes(proposal.status) && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "reject")} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Reject</button>}
          {proposal.status === "CONFIRMED" && proposal.policy_decision === "ALLOW" && !proposal.payment_preparation && <button type="button" disabled={busy} onClick={() => void act(proposal.proposal_id, "prepare")} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Prepare payment</button>}
          {proposal.payment_preparation?.status === "EXECUTION_PENDING" && <button type="button" disabled={busy} onClick={() => void continueToCheckout(proposal)} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50">Continue to checkout</button>}
        </div></details>} />)}
      </section>
    </div>
  );
}

function FileEmpty() {
  return <Sparkles size={24} className="mx-auto text-accent" aria-hidden="true" />;
}
