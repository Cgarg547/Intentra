"use client";

import { PaymentAuthorization } from "./payment-authorization";

import { PaymentLifecycle } from "./payment-lifecycle";
import { PaymentAuditTimeline } from "./payment-audit-timeline";

import { PaymentOverview } from "./payment-overview";
import { PaymentHistory } from "./payment-history";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import { capturePayment, evaluatePayment, getPayment, launchCheckout, listPayments, listReservations, reconcilePayment, reservePayment, type PaymentAttempt, type PaymentReservation } from "@/lib/payments/client";
import { checkoutStatusMessage } from "@/lib/payments/capture-status";

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
    <PaymentOverview payments={payments} loading={loading} />
    {checkoutStatusMessage(checkoutResult, payments) && <div role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{checkoutStatusMessage(checkoutResult, payments)}</div>}
    {notice && <div role="status" className="rounded-xl border border-border bg-surface p-4 text-sm">{notice}</div>}
    {error && <div role="alert" className="rounded-xl border border-red-500/40 bg-surface p-4 text-sm text-red-600">{error} <Link href="/account" className="underline">Check sign-in</Link></div>}
    <PaymentAuthorization
      contracts={contracts}
      contractId={contractId}
      amount={amount}
      loading={loading}
      error={error}
      working={working}
      evaluation={evaluation}
      reservation={reservation}
      reservationUncertain={reservationUncertain}
      onContractChange={(value) => {
        setContractId(value);
        setEvaluation(null);
        setReservation(null);
        reservationKey.current = null;
      }}
      onAmountChange={(value) => {
        setAmount(value);
        setEvaluation(null);
        setReservation(null);
        reservationKey.current = null;
      }}
      onEvaluate={evaluate}
      onReserve={reserve}
      onCheckout={checkout}
    />

    {(reservations.some((item) => item.status === "RESERVED") || resumableOrders.length > 0) && <section className="rounded-2xl border border-border bg-surface p-6"><h2 className="text-lg font-semibold">Payments ready to continue</h2><p className="mt-1 text-sm text-muted">Continue the existing reservation and PayPal order. INTENTRA verifies the order again and never creates a replacement for a bound order.</p><div className="mt-4 divide-y divide-border">{reservations.filter((item) => item.status === "RESERVED" || resumableOrders.some((resume) => resume.reservation_id === item.reservation_id)).map((item) => { const boundOrder = resumableOrders.some((resume) => resume.reservation_id === item.reservation_id); return <div key={item.reservation_id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div><p className="font-medium">{item.merchant_id} · {amountText(item.amount, item.currency)}</p><p className="mt-1 text-xs text-muted">{boundOrder ? "Existing PayPal order awaiting buyer approval" : "Reserved"} · {new Date(item.created_at).toLocaleString()}</p></div><button type="button" disabled={working} onClick={() => resumeCheckout(item)} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{working ? "Preparing…" : boundOrder ? "Resume PayPal approval" : "Continue checkout"}</button></div>; })}</div></section>}

    <PaymentHistory
      payments={payments}
      loading={loading}
      working={working}
      error={error}
      onRefresh={() => {
        setLoading(true);
        refresh()
          .catch((err: unknown) =>
            setError(err instanceof Error ? err.message : "Refresh failed.")
          )
          .finally(() => setLoading(false));
      }}
      onInspect={(attemptId) => {
        void inspect(attemptId);
      }}
    />

    {detail && <section className="rounded-2xl border border-border bg-surface p-6" aria-labelledby="payment-detail-title"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="payment-detail-title" className="text-xl font-semibold">Transaction details</h2><p className="mt-1 break-all text-xs text-muted">Attempt {detail.attempt_id}</p></div><button type="button" onClick={() => setDetail(null)} className="rounded-lg border border-border px-3 py-2 text-sm">Close</button></div><PaymentLifecycle payment={detail} /><dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">{[["Merchant", detail.merchant_id], ["Amount", amountText(detail.amount, detail.currency)], ["Payment state", detail.attempt_state], ["Reservation", detail.reservation_state], ["Buyer approval", detail.approval_state ?? "Not initiated"], ["Provider order", detail.provider_order_id ?? "Not created"], ["Capture reference", detail.capture_id ?? "Not captured"], ["Verified at", detail.approval_verified_at ? new Date(detail.approval_verified_at).toLocaleString() : "Not verified"]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 break-all font-medium">{value}</dd></div>)}</dl><div className="mt-5 flex flex-wrap gap-3">{detail.approval_state === "APPROVED" && detail.attempt_state === "PENDING" && <button type="button" disabled={working} onClick={() => capture(detail)} className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-50">Capture payment</button>}{detail.attempt_state === "UNKNOWN" && <button type="button" disabled={working} onClick={() => reconcile(detail)} className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Reconcile provider outcome</button>}</div>{detail.events && <PaymentAuditTimeline events={detail.events} />}</section>}
  </div>;
}
