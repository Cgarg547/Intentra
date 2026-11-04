import type { Metadata } from "next";
import { Suspense } from "react";
import { PaymentWorkspace } from "@/components/payments/payment-workspace";

export const metadata: Metadata = { title: "Payments" };

export default function PaymentsPage() {
  return <div className="space-y-6">
    <header>
      <p className="text-xs font-semibold uppercase tracking-widest text-accent">Payment authorization and execution</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Payments</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Evaluate payment proposals against approved contracts, reserve budget, approve through PayPal Sandbox, and inspect verified outcomes.</p>
    </header>
    <Suspense fallback={<div role="status" className="h-40 animate-pulse rounded-2xl border border-border bg-surface" />}><PaymentWorkspace /></Suspense>
  </div>;
}
