"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CreditCard, FileCheck2, ShieldCheck, ShieldX } from "lucide-react";
import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import { listPayments, type PaymentAttempt } from "@/lib/payments/client";

const money = (value: number, currency: string) => new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);

export default function CommandCenterPage() {
  const [contracts, setContracts] = useState<IntentContract[]>([]);
  const [payments, setPayments] = useState<PaymentAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listContracts(100, 0), listPayments()]).then(([c, p]) => {
      if (active) { setContracts(c.items); setPayments(p.items); setError(null); }
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Unable to load your account data.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const metricItems = [
    { label: "Approved contracts", value: String(contracts.filter((c) => c.status === "APPROVED").length), detail: "Owner-approved spending policies", icon: FileCheck2 },
    { label: "Payments in progress", value: String(payments.filter((p) => ["PENDING", "UNKNOWN"].includes(p.attempt_state)).length), detail: "Pending buyer approval or review", icon: CreditCard },
    { label: "Captured payments", value: String(payments.filter((p) => p.attempt_state === "SUCCEEDED").length), detail: "Verified provider outcomes", icon: ShieldCheck },
    { label: "Reservations held", value: String(payments.filter((p) => ["RESERVED", "EXECUTION_PENDING", "OUTCOME_UNKNOWN"].includes(p.reservation_state)).length), detail: "Reserved, executing, or awaiting review", icon: ShieldX },
  ];

  return <div className="space-y-7">
    <section className="rounded-3xl border border-border bg-surface p-7 md:p-10">
      <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1.5 text-xs font-medium"><ShieldCheck aria-hidden="true" className="h-4 w-4 text-accent" /> PRIVATE PAYMENT WORKSPACE</div>
      <h1 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">Intent-led payments,<br />under your control.</h1>
      <p className="mt-5 max-w-2xl text-sm leading-7 text-muted md:text-base">Create an intent contract, reserve a payment within its limits, then review the provider outcome from one secure workspace.</p>
      <div className="mt-7 flex flex-wrap gap-3"><Link href="/contracts" className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground">Manage contracts <ArrowRight aria-hidden="true" size={16} /></Link><Link href="/payments" className="rounded-xl border border-border px-5 py-3 text-sm font-semibold">Review payments</Link></div>
    </section>
    {error ? <section role="alert" className="rounded-2xl border border-border bg-surface p-6"><h2 className="font-semibold">Your account data is unavailable</h2><p className="mt-2 text-sm text-muted">{error}</p><Link href="/account" className="mt-4 inline-block text-sm font-medium text-accent underline">Sign in or check your session</Link></section> : <>
      <div><h2 className="text-xl font-semibold">Account overview</h2><p className="mt-1 text-sm text-muted">Live records returned for your authenticated account.</p></div>
      <section aria-label="Account payment metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metricItems.map(({ label, value, detail, icon: Icon }) => <article key={label} className="rounded-2xl border border-border bg-surface p-5"><div className="flex items-center justify-between text-sm text-muted"><span>{label}</span><Icon aria-hidden="true" className="h-5 w-5 text-accent" /></div><p className="mt-4 text-3xl font-semibold">{loading ? "—" : value}</p><p className="mt-2 text-xs text-muted">{detail}</p></article>)}</section>
      <section className="rounded-2xl border border-border bg-surface p-6"><div className="flex items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Recent payment activity</h2><p className="mt-1 text-sm text-muted">Status is sourced from INTENTRA&apos;s payment records.</p></div><Link href="/payments" className="text-sm font-medium text-accent">View history</Link></div>{loading ? <div role="status" className="mt-5 animate-pulse space-y-3"><div className="h-12 rounded-lg bg-surface-muted" /><div className="h-12 rounded-lg bg-surface-muted" /></div> : payments.length === 0 ? <p className="mt-5 rounded-xl bg-surface-muted p-5 text-sm text-muted">No payment attempts yet. Start with an approved contract and create a payment reservation.</p> : <div className="mt-5 divide-y divide-border">{payments.slice(0, 5).map((p) => <Link key={p.attempt_id} href="/payments" className="flex flex-wrap items-center justify-between gap-3 py-4"><div><p className="font-medium">{p.merchant_id}</p><p className="mt-1 text-xs text-muted">{new Date(p.created_at).toLocaleString()}</p></div><div className="text-right"><p className="font-semibold">{money(Number(p.amount), p.currency)}</p><p className="mt-1 text-xs text-muted">{p.attempt_state} · {p.approval_state ?? "NO CHECKOUT"}</p></div></Link>)}</div>}</section>
      <section className="grid gap-4 sm:grid-cols-2"><Link href="/contracts" className="rounded-2xl border border-border bg-surface p-5 hover:bg-surface-muted"><h2 className="font-semibold">Intent contracts</h2><p className="mt-2 text-sm text-muted">Create, approve, inspect, and revoke merchant spending limits.</p></Link><Link href="/payments" className="rounded-2xl border border-border bg-surface p-5 hover:bg-surface-muted"><h2 className="font-semibold">Payments</h2><p className="mt-2 text-sm text-muted">Evaluate proposals, reserve budget, complete checkout, and reconcile outcomes.</p></Link></section>
    </>}
  </div>;
}
