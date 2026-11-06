"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import { capturePayment, evaluatePayment, getPayment, launchCheckout, listPayments, listReservations, reconcilePayment, reservePayment, type PaymentAttempt, type PaymentReservation } from "@/lib/payments/client";

const amountText = (amount: string, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount));

export function PaymentWorkspace() {
  const searchParams = useSearchParams();
  const checkoutResult = searchParams.get("checkout");
  const [contracts, setContracts] = useState<IntentContract[]>([]);
  const [contractId, setContractId] = useState("");
  const [amount, setAmount] = useState("");
  const [payments, setPayments] = useState<PaymentAttempt[]>([]);
  const [reservations, setReservations] = useState<PaymentReservation[]>([]);
  const [detail, setDetail] = useState<PaymentAttempt | null>(null);
  const [evaluation, setEvaluation] = useState<{ decision: string; reason: string } | null>(null);
  const [reservation, setReservation] = useState<{ reservation_id: string; status: string; reason: string } | null>(null);
  const [reservationUncertain, setReservationUncertain] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const reservationKey = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    const [contractResult, paymentResult, reservationResult] = await Promise.all([listContracts(100, 0), listPayments(), listReservations()]);
    setContracts(contractResult.items);
    setPayments(paymentResult.items);
    setReservations(reservationResult.items);
    setError(null);
  }, [setError]);

  useEffect(() => {
    let active = true;
    Promise.all([listContracts(100, 0), listPayments(), listReservations()]).then(([c, p, r]) => {
      if (active) { setContracts(c.items); setPayments(p.items); setReservations(r.items); setContractId((current) => current || c.items.find((item) => item.status === "APPROVED")?.id || ""); }
    }).catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Unable to load payment data."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const selectedContract = contracts.find((contract) => contract.id === contractId);
  const resumableOrders = reservations.filter((item) => item.status === "EXECUTION_PENDING" && payments.some((payment) => {
    const activeApproval = payment.approval_state === null || (
      payment.approval_state === "PENDING" && payment.approval_consumed_at == null &&
      payment.approval_expires_at != null && Date.parse(payment.approval_expires_at) > Date.now());
    return payment.reservation_id === item.reservation_id && payment.attempt_state === "PENDING" &&
      payment.provider_order_id !== null && activeApproval;
  }) &&
    contracts.some((contract) => contract.id === item.contract_id && contract.status === "APPROVED"));

  async function evaluate() {
    if (!selectedContract) return;
    setWorking(true); setError(null); setNotice(null);
    try {
      const result = await evaluatePayment({ contract_id: selectedContract.id, merchant_id: selectedContract.merchant_id, amount, currency: selectedContract.currency });
      setEvaluation({ decision: result.decision, reason: result.reason });
    } catch (err) { setError(err instanceof Error ? err.message : "Payment evaluation failed."); }
    finally { setWorking(false); }
  }

  async function reserve() {
    if (!selectedContract || !evaluation || evaluation.decision !== "ALLOW") return;
    setWorking(true); setError(null);
    try {
      reservationKey.current ??= crypto.randomUUID();
      const result = await reservePayment({ contract_id: selectedContract.id, merchant_id: selectedContract.merchant_id, amount, currency: selectedContract.currency, idempotency_key: reservationKey.current });
      setReservation(result);
      setReservationUncertain(false);
      void refresh().catch(() => undefined);
      if (result.status === "RESERVED") setNotice("Budget reserved. Continue to PayPal Sandbox for buyer approval.");
      else setNotice(result.reason);
    } catch (err) { setReservationUncertain(true); setError(`${err instanceof Error ? err.message : "Unable to confirm the reservation."} Retry the same proposal before changing its details.`); }
    finally { setWorking(false); }
  }

  async function checkout() {
    if (!reservation || reservation.status !== "RESERVED") return;
    setWorking(true); setError(null);
    try {
      const result = await launchCheckout(reservation.reservation_id);
      window.location.assign(result.approval_url);
    } catch (err) { setError(err instanceof Error ? err.message : "Checkout could not be started. Check payment history before retrying."); setWorking(false); await refresh().catch(() => undefined); }
  }

  async function resumeCheckout(item: PaymentReservation) {
    const contract = contracts.find((candidate) => candidate.id === item.contract_id);
    if (!contract || contract.status !== "APPROVED") { setError("This reservation's contract is no longer approved. Review its state before continuing."); return; }
    setContractId(item.contract_id); setAmount(item.amount);
    setReservation({ reservation_id: item.reservation_id, status: item.status, reason: item.reason });
    setEvaluation({ decision: "ALLOW", reason: "This payment was already authorized and reserved by INTENTRA." });
    setWorking(true); setError(null);
    try {
      const result = await launchCheckout(item.reservation_id);
      window.location.assign(result.approval_url);
    } catch (err) { setError(err instanceof Error ? err.message : "Checkout could not be resumed. Review the payment history before retrying."); }
    finally { setWorking(false); }
  }

  async function inspect(attemptId: string) {
    setWorking(true); setError(null);
    try { setDetail(await getPayment(attemptId)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load payment details."); }
    finally { setWorking(false); }
  }

  async function capture(attempt: PaymentAttempt) {
    if (!window.confirm(`Capture ${amountText(attempt.amount, attempt.currency)} for ${attempt.merchant_id}? This sends a capture request to PayPal Sandbox.`)) return;
    setWorking(true); setError(null); setNotice(null);
    try {
      const result = await capturePayment(attempt.attempt_id);
      setNotice(`Capture result: ${result.state}. ${result.action}`);
      // Show the confirmed local result immediately. Refreshing history is
      // useful, but must not hide a definitive response behind a slow view
      // refresh or make the operator wonder whether capture was submitted.
      void refresh().catch(() => undefined);
      void inspect(attempt.attempt_id);
    } catch (err) { setError(err instanceof Error ? err.message : "Capture state is uncertain. Reconcile before any retry."); }
    finally { setWorking(false); }
  }

  async function reconcile(attempt: PaymentAttempt) {
    setWorking(true); setError(null); setNotice(null);
    try {
      const result = await reconcilePayment(attempt.attempt_id);
      setNotice(`Reconciliation: ${result.action}${result.provider_status ? ` · provider ${result.provider_status}` : ""}`);
      void refresh().catch(() => undefined);
      void inspect(attempt.attempt_id);
    } catch (err) { setError(err instanceof Error ? err.message : "Reconciliation is unavailable. The current reservation remains held."); }
    finally { setWorking(false); }
  }

  return <div className="space-y-6">
    {(checkoutResult === "verified" || checkoutResult === "cancelled" || checkoutResult === "cancel-review" || checkoutResult?.startsWith("verification")) && <div role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{checkoutResult === "verified" ? "PayPal buyer approval was verified by INTENTRA. No payment was captured; review the attempt below and choose Capture when ready." : checkoutResult === "cancelled" ? "Checkout was cancelled. The payment reservation remains available for review." : checkoutResult === "cancel-review" ? "Checkout could not be safely marked cancelled. Review the payment state before retrying." : "PayPal returned to INTENTRA, but approval could not be verified. Review the payment before taking another action."}</div>}
    {notice && <div role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{notice}</div>}
    {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-surface p-4 text-sm text-red-600">{error} <Link href="/account" className="underline">Check sign-in</Link></div>}
    <section className="app-card rounded-3xl border border-border bg-surface p-6">
      <h2 className="text-xl font-semibold">Evaluate and reserve a payment</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">INTENTRA checks the proposal against a human-approved contract. Evaluation does not move money. A separate reservation holds budget before checkout.</p>
      {loading ? <div role="status" className="mt-5 h-28 animate-pulse rounded-xl bg-surface-muted" /> : <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm"><span>Approved intent contract</span><select required disabled={reservation?.status === "RESERVED" || reservationUncertain} value={contractId} onChange={(e) => { setContractId(e.target.value); setEvaluation(null); setReservation(null); reservationKey.current = null; }} className="w-full rounded-xl border border-border bg-background px-3 py-3 disabled:opacity-60"><option value="">Select a contract</option>{contracts.filter((c) => c.status === "APPROVED").map((c) => <option key={c.id} value={c.id}>{c.merchant_id} · up to {amountText(c.maximum_amount, c.currency)}</option>)}</select></label>
        <label className="space-y-2 text-sm"><span>Payment amount {selectedContract ? `(${selectedContract.currency})` : ""}</span><input type="number" min="0.01" step="0.01" required disabled={reservation?.status === "RESERVED" || reservationUncertain} value={amount} onChange={(e) => { setAmount(e.target.value); setEvaluation(null); setReservation(null); reservationKey.current = null; }} className="w-full rounded-xl border border-border bg-background px-3 py-3 disabled:opacity-60" placeholder="0.00" /></label>
      </div>}
      <div className="mt-4 flex flex-wrap gap-3"><button type="button" disabled={working || reservation?.status === "RESERVED" || reservationUncertain || !selectedContract || !amount || loading} onClick={evaluate} className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{working ? "Working…" : "Evaluate payment"}</button>{evaluation?.decision === "ALLOW" && !reservation && <button type="button" disabled={working} onClick={reserve} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{reservationUncertain ? "Retry reservation safely" : "Reserve budget"}</button>}{reservation?.status === "RESERVED" && <button type="button" disabled={working} onClick={checkout} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working ? "Preparing checkout…" : "Continue to PayPal Sandbox"}</button>}</div>
      {evaluation && <div className="mt-4 rounded-xl bg-surface-muted p-4 text-sm"><p className="font-semibold">Authorization: {evaluation.decision}</p><p className="mt-1 text-muted">{evaluation.reason}</p></div>}
      {reservation && <div className="mt-3 rounded-xl bg-surface-muted p-4 text-sm"><p className="font-semibold">Reservation: {reservation.status}</p><p className="mt-1 text-muted">{reservation.reason}</p></div>}
      {contracts.filter((c) => c.status === "APPROVED").length === 0 && !loading && !error && <p className="mt-4 text-sm text-muted">No approved contracts are available. Create and approve a contract first.</p>}
    </section>

    {(reservations.some((item) => item.status === "RESERVED") || resumableOrders.length > 0) && <section className="rounded-2xl border border-border bg-surface p-6"><h2 className="text-lg font-semibold">Payments ready to continue</h2><p className="mt-1 text-sm text-muted">Continue the existing reservation and PayPal order. INTENTRA verifies the order again and never creates a replacement for a bound order.</p><div className="mt-4 divide-y divide-border">{reservations.filter((item) => item.status === "RESERVED" || resumableOrders.some((resume) => resume.reservation_id === item.reservation_id)).map((item) => { const boundOrder = resumableOrders.some((resume) => resume.reservation_id === item.reservation_id); return <div key={item.reservation_id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div><p className="font-medium">{item.merchant_id} · {amountText(item.amount, item.currency)}</p><p className="mt-1 text-xs text-muted">{boundOrder ? "Existing PayPal order awaiting buyer approval" : "Reserved"} · {new Date(item.created_at).toLocaleString()}</p></div><button type="button" disabled={working} onClick={() => resumeCheckout(item)} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working ? "Preparing…" : boundOrder ? "Resume PayPal approval" : "Continue checkout"}</button></div>; })}</div></section>}

    <section className="rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Payment history</h2><p className="mt-1 text-sm text-muted">Owner-scoped payment attempts and provider outcomes. Uncertain attempts require reconciliation.</p></div><button type="button" disabled={working} onClick={() => { setLoading(true); refresh().catch((e: unknown) => setError(e instanceof Error ? e.message : "Refresh failed.")).finally(() => setLoading(false)); }} className="rounded-lg border border-border px-3 py-2 text-sm">Refresh</button></div>
      {loading ? <div role="status" className="mt-5 animate-pulse space-y-3"><div className="h-14 rounded-lg bg-surface-muted" /><div className="h-14 rounded-lg bg-surface-muted" /></div> : payments.length === 0 ? error ? null : <p className="mt-5 rounded-xl bg-surface-muted p-5 text-sm text-muted">No payment attempts have been created.</p> : <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[740px] text-left text-sm"><thead><tr className="border-b border-border text-muted"><th className="px-3 py-3">Merchant</th><th className="px-3 py-3">Amount</th><th className="px-3 py-3">Payment</th><th className="px-3 py-3">Buyer approval</th><th className="px-3 py-3">Date</th><th className="px-3 py-3">Action</th></tr></thead><tbody className="divide-y divide-border">{payments.map((p) => <tr key={p.attempt_id}><th scope="row" className="px-3 py-4 font-medium">{p.merchant_id}</th><td className="px-3 py-4">{amountText(p.amount, p.currency)}</td><td className="px-3 py-4"><span className="rounded-md border border-border px-2 py-1 text-xs font-semibold">{p.attempt_state}</span></td><td className="px-3 py-4">{p.approval_state ?? "—"}</td><td className="px-3 py-4 text-muted">{new Date(p.created_at).toLocaleDateString()}</td><td className="px-3 py-4"><button type="button" disabled={working} onClick={() => inspect(p.attempt_id)} className="rounded-lg border border-border px-3 py-2 text-xs font-medium">Details</button></td></tr>)}</tbody></table></div>}
    </section>

    {detail && <section className="rounded-2xl border border-border bg-surface p-6" aria-labelledby="payment-detail-title"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="payment-detail-title" className="text-xl font-semibold">Transaction details</h2><p className="mt-1 break-all text-xs text-muted">Attempt {detail.attempt_id}</p></div><button type="button" onClick={() => setDetail(null)} className="rounded-lg border border-border px-3 py-2 text-sm">Close</button></div><dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">{[["Merchant", detail.merchant_id], ["Amount", amountText(detail.amount, detail.currency)], ["Payment state", detail.attempt_state], ["Reservation", detail.reservation_state], ["Buyer approval", detail.approval_state ?? "Not initiated"], ["Provider order", detail.provider_order_id ?? "Not created"], ["Capture reference", detail.capture_id ?? "Not captured"], ["Verified at", detail.approval_verified_at ? new Date(detail.approval_verified_at).toLocaleString() : "Not verified"]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 break-all font-medium">{value}</dd></div>)}</dl><div className="mt-5 flex flex-wrap gap-3">{detail.approval_state === "APPROVED" && detail.attempt_state === "PENDING" && <button type="button" disabled={working} onClick={() => capture(detail)} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">Capture payment</button>}{detail.attempt_state === "UNKNOWN" && <button type="button" disabled={working} onClick={() => reconcile(detail)} className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Reconcile provider outcome</button>}</div>{(detail.events?.length ?? 0) > 0 && <div className="mt-6 border-t border-border pt-5"><h3 className="font-semibold">Audit timeline</h3><ol className="mt-3 space-y-3">{detail.events?.map((event) => <li key={event.event_correlation_id} className="rounded-lg bg-surface-muted p-3"><p className="text-sm font-medium">{event.event_type}</p><p className="mt-1 text-xs text-muted">{new Date(event.created_at).toLocaleString()}</p></li>)}</ol></div>}</section>}
  </div>;
}
