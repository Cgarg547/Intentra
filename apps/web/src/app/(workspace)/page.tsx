"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  CircleAlert,
  Clock3,
  CreditCard,
  FileCheck2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wallet,
  Zap,
} from "lucide-react";

import { listContracts } from "@/lib/contracts/client";
import type { IntentContract } from "@/lib/contracts/types";
import {
  listPayments,
  type PaymentAttempt,
} from "@/lib/payments/client";

import { Card } from "@/components/ui/primitives";

const money = (value: number, currency: string) =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);

function paymentTone(state: string) {
  switch (state.toUpperCase()) {
    case "SUCCEEDED":
      return "text-emerald-500 bg-emerald-500/10";
    case "FAILED":
    case "BLOCKED":
      return "text-red-500 bg-red-500/10";
    case "PENDING":
    case "UNKNOWN":
      return "text-amber-500 bg-amber-500/10";
    default:
      return "text-muted bg-surface-muted";
  }
}

export default function CommandCenterPage() {
  const [contracts, setContracts] = useState<IntentContract[]>([]);
  const [payments, setPayments] = useState<PaymentAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);

    try {
      const [contractResult, paymentResult] = await Promise.all([
        listContracts(100, 0),
        listPayments(),
      ]);

      setContracts(contractResult.items);
      setPayments(paymentResult.items);
      setLastUpdated(new Date());
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load workspace records.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(refresh);
  }, [refresh]);

  const approvedContracts = contracts.filter(
    (item) => item.status === "APPROVED",
  );

  const pendingPayments = payments.filter(
    (item) =>
      item.attempt_state === "PENDING" ||
      item.attempt_state === "UNKNOWN",
  );

  const successfulPayments = payments.filter(
    (item) => item.attempt_state === "SUCCEEDED",
  );

  const reservedPayments = payments.filter((item) =>
    [
      "RESERVED",
      "EXECUTION_PENDING",
      "OUTCOME_UNKNOWN",
    ].includes(item.reservation_state),
  );

  const metrics = [
    {
      label: "Approved contracts",
      value: approvedContracts.length,
      detail: "Active spending authorizations",
      icon: FileCheck2,
      accent: "violet",
    },
    {
      label: "Pending payments",
      value: pendingPayments.length,
      detail: "Awaiting resolution or review",
      icon: Clock3,
      accent: "amber",
    },
    {
      label: "Successful payments",
      value: successfulPayments.length,
      detail: "Recorded successful outcomes",
      icon: CheckCircle2,
      accent: "emerald",
    },
    {
      label: "Reserved payments",
      value: reservedPayments.length,
      detail: "Reserved or awaiting execution",
      icon: Wallet,
      accent: "blue",
    },
  ];

  return (
    <div className="dashboard-page space-y-8">

      {/* Premium hero */}
      <section className="dashboard-hero relative isolate overflow-hidden rounded-[2rem] border border-violet-400/20">
        <div className="dashboard-grid absolute inset-0" aria-hidden="true" />
        <div className="dashboard-glow dashboard-glow-one" aria-hidden="true" />
        <div className="dashboard-glow dashboard-glow-two" aria-hidden="true" />

        <div className="relative z-10 grid min-h-[390px] items-center gap-8 px-6 py-10 sm:px-10 lg:grid-cols-[1.2fr_0.8fr] lg:px-14 lg:py-12">

          <div className="max-w-2xl">
            <div className="mb-7 flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-300">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                Financial control center
              </span>

              <span className="text-xs font-medium text-slate-400">
                HUMAN-GOVERNED AI
              </span>
            </div>

            <p className="text-xs font-bold uppercase tracking-[0.24em] text-violet-300">
              INTENTRA / COMMAND CENTER
            </p>

            <h1 className="mt-5 text-4xl font-semibold leading-[1.12] tracking-[-0.055em] text-white sm:text-5xl lg:text-[3.65rem]">
              Intelligent spending.
              <span className="block bg-gradient-to-r from-violet-300 via-indigo-300 to-cyan-300 bg-clip-text text-transparent">
                Human control.
              </span>
            </h1>

            <p className="mt-6 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
              Your intelligent financial operations workspace.
              Plan purchases with AI, enforce spending policies,
              authorize transactions and maintain a complete
              audit trail.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/agents"
                className="group inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3.5 text-sm font-bold text-slate-950 shadow-xl shadow-violet-950/30 transition duration-300 hover:-translate-y-1 hover:bg-violet-100"
              >
                <Sparkles size={17} />
                Start AI purchase
                <ArrowUpRight
                  size={16}
                  className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </Link>

              <Link
                href="/contracts"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-5 py-3.5 text-sm font-semibold text-white backdrop-blur transition hover:-translate-y-1 hover:bg-white/10"
              >
                <ShieldCheck size={17} />
                Manage authorization
              </Link>
            </div>

            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-white/10 pt-6 text-xs text-slate-400">
              <span className="flex items-center gap-2">
                <ShieldCheck size={15} className="text-emerald-400" />
                Human approval required
              </span>
              <span className="flex items-center gap-2">
                <Zap size={15} className="text-violet-300" />
                Policy-driven decisions
              </span>
            </div>
          </div>

          {/* CSS 3D financial intelligence illustration */}
          <div
            className="dashboard-orb-scene relative mx-auto flex h-[290px] w-full max-w-[360px] items-center justify-center sm:h-[340px]"
            aria-label="Abstract three-dimensional INTENTRA financial intelligence illustration"
            role="img"
          >
            <div className="dashboard-orb-shadow" />
            <div className="dashboard-orb-ring dashboard-ring-one" />
            <div className="dashboard-orb-ring dashboard-ring-two" />

            <div className="dashboard-orb">
              <div className="dashboard-orb-inner">
                <ShieldCheck size={65} strokeWidth={1.1} />
                <span className="mt-3 text-[10px] font-black tracking-[0.3em]">
                  INTENTRA
                </span>
              </div>
            </div>

            <div className="dashboard-float-card dashboard-float-top">
              <ShieldCheck size={16} className="text-emerald-300" />
              <span>Protected spending</span>
            </div>

            <div className="dashboard-float-card dashboard-float-bottom">
              <Activity size={16} className="text-violet-300" />
              <span>Intelligent control</span>
            </div>

            <div className="dashboard-orb-particle particle-one" />
            <div className="dashboard-orb-particle particle-two" />
            <div className="dashboard-orb-particle particle-three" />
          </div>
        </div>

        <div className="relative z-10 flex flex-wrap justify-between gap-3 border-t border-white/10 bg-black/10 px-6 py-4 text-[11px] text-slate-400 sm:px-10 lg:px-14">
          <span>INTENTRA FINANCIAL INTELLIGENCE</span>
          <span>Sandbox environment · Explicit authorization</span>
        </div>
      </section>

      {/* Loading and error states */}
      {error && (
        <section
          role="alert"
          className="rounded-2xl border border-red-500/30 bg-red-500/5 p-5"
        >
          <div className="flex items-start gap-3">
            <CircleAlert className="mt-0.5 text-red-500" size={20} />
            <div>
              <h2 className="font-semibold">Unable to synchronize records</h2>
              <p className="mt-2 text-sm text-muted">{error}</p>
              <button
                type="button"
                onClick={() => void refresh()}
                className="mt-3 text-sm font-semibold text-accent"
              >
                Try again
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Financial overview */}
      <section className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="page-kicker">Your financial overview</p>
            <h2 className="page-title mt-2 text-2xl sm:text-3xl">
              Operating at a glance
            </h2>
            <p className="mt-2 text-sm text-muted">
              Account-scoped records from your INTENTRA workspace.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2.5 text-xs font-semibold transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            <RefreshCw
              size={14}
              className={loading ? "animate-spin" : ""}
            />
            Refresh records
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon;

            return (
              <article
                key={metric.label}
                className="dashboard-metric group relative overflow-hidden rounded-2xl border border-border bg-surface p-5 transition duration-300 hover:-translate-y-1 hover:border-accent/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-muted">
                      {metric.label}
                    </p>
                    <p className="mt-5 text-4xl font-semibold tracking-[-0.05em]">
                      {loading ? "—" : metric.value}
                    </p>
                  </div>

                  <div className={`dashboard-metric-icon metric-${metric.accent}`}>
                    <Icon size={21} strokeWidth={1.8} />
                  </div>
                </div>

                <p className="mt-4 text-xs text-muted">{metric.detail}</p>
                <div className="dashboard-metric-line" />
              </article>
            );
          })}
        </div>

        <p className="text-[11px] text-muted">
          {lastUpdated
            ? `Last synchronized ${lastUpdated.toLocaleTimeString([], {
                hour: "numeric",
                minute: "2-digit",
              })}.`
            : "Waiting for the first successful synchronization."}
          {" "}Values reflect retrieved account records, not projected activity.
        </p>
      </section>

      {/* Activity and attention */}
      <section className="grid gap-5 xl:grid-cols-[1.45fr_0.85fr]">

        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5 sm:p-6">
            <div>
              <div className="flex items-center gap-2">
                <Activity size={18} className="text-accent" />
                <h2 className="text-lg font-semibold">
                  Recent payment activity
                </h2>
              </div>
              <p className="mt-1 text-xs text-muted">
                Recorded transactions and their current states.
              </p>
            </div>

            <Link
              href="/payments"
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline"
            >
              View all payments <ArrowRight size={14} />
            </Link>
          </div>

          <div className="p-5 sm:p-6">
            {loading ? (
              <div role="status" className="space-y-4">
                <span className="sr-only">Loading payment activity</span>
                {[1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="h-14 animate-pulse rounded-xl bg-surface-muted"
                  />
                ))}
              </div>
            ) : payments.length === 0 ? (
              <div className="py-9 text-center">
                <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-accent/10">
                  <CreditCard size={25} className="text-accent" />
                </div>
                <h3 className="mt-4 font-semibold">
                  Your payment activity starts here
                </h3>
                <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted">
                  Payment records will appear here when transactions are
                  created through your authorized purchasing workflows.
                </p>
                <Link
                  href="/agents"
                  className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-accent"
                >
                  Explore AI purchasing <ArrowRight size={15} />
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {payments.slice(0, 6).map((payment) => (
                  <Link
                    key={payment.attempt_id}
                    href="/payments"
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg py-4 transition hover:bg-surface-muted/70"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
                        <Wallet size={18} />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">
                          {payment.merchant_id}
                        </p>
                        <p className="mt-1 text-[11px] text-muted">
                          {new Date(payment.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="text-sm font-bold">
                        {money(Number(payment.amount), payment.currency)}
                      </p>
                      <span
                        className={`mt-1 inline-flex rounded-full px-2 py-1 text-[10px] font-bold ${paymentTone(payment.attempt_state)}`}
                      >
                        {payment.attempt_state.replaceAll("_", " ")}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Attention panel */}
        <Card className="overflow-hidden">
          <div className="border-b border-border p-5 sm:p-6">
            <div className="flex items-center gap-2">
              <CircleAlert size={18} className="text-amber-500" />
              <h2 className="text-lg font-semibold">Needs attention</h2>
            </div>
            <p className="mt-1 text-xs text-muted">
              Items identified from your account records.
            </p>
          </div>

          <div className="space-y-3 p-5 sm:p-6">
            {loading ? (
              <p role="status" className="text-sm text-muted">
                Checking your workspace...
              </p>
            ) : (
              <>
                {pendingPayments.length > 0 && (
                  <Link
                    href="/payments"
                    className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 transition hover:border-amber-500/50"
                  >
                    <Clock3 className="mt-0.5 shrink-0 text-amber-500" size={19} />
                    <div>
                      <p className="text-sm font-semibold">
                        {pendingPayments.length} payment
                        {pendingPayments.length === 1 ? "" : "s"} need review
                      </p>
                      <p className="mt-1 text-xs leading-5 text-muted">
                        Pending or unknown payment outcomes require
                        appropriate reconciliation.
                      </p>
                    </div>
                  </Link>
                )}

                {approvedContracts.length === 0 && (
                  <Link
                    href="/contracts"
                    className="flex items-start gap-3 rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 transition hover:border-violet-500/50"
                  >
                    <FileCheck2 className="mt-0.5 shrink-0 text-accent" size={19} />
                    <div>
                      <p className="text-sm font-semibold">
                        No approved spending contracts
                      </p>
                      <p className="mt-1 text-xs leading-5 text-muted">
                        Create and approve an intent contract before
                        authorizing purchases.
                      </p>
                    </div>
                  </Link>
                )}

                {pendingPayments.length === 0 &&
                  approvedContracts.length > 0 && (
                    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                      <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 size={19} />
                        <p className="text-sm font-semibold">
                          No pending payment reviews
                        </p>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-muted">
                        No pending or unknown payment attempts were
                        returned by the current account records.
                      </p>
                    </div>
                  )}
              </>
            )}
          </div>

          <div className="border-t border-border px-5 py-4">
            <Link
              href="/security"
              className="inline-flex items-center gap-2 text-xs font-semibold text-accent hover:underline"
            >
              Open Security Center <ArrowUpRight size={14} />
            </Link>
          </div>
        </Card>
      </section>

      {/* Workflow shortcuts */}
      <section className="space-y-5">
        <div>
          <p className="page-kicker">Explore INTENTRA</p>
          <h2 className="page-title mt-2 text-2xl">
            Your financial workflow
          </h2>
          <p className="mt-2 text-sm text-muted">
            Everything you need to plan, authorize and monitor purchasing.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              title: "AI Purchasing",
              description: "Convert natural-language requests into structured proposals.",
              href: "/agents",
              icon: Bot,
            },
            {
              title: "Intent Contracts",
              description: "Define merchant permissions and spending limits.",
              href: "/contracts",
              icon: FileCheck2,
            },
            {
              title: "Payment Operations",
              description: "Manage reservations, approvals and payment outcomes.",
              href: "/payments",
              icon: CreditCard,
            },
            {
              title: "Audit Explorer",
              description: "Inspect recorded decisions and financial events.",
              href: "/audit",
              icon: Activity,
            },
          ].map((item) => {
            const Icon = item.icon;

            return (
              <Link
                key={item.title}
                href={item.href}
                className="dashboard-shortcut group rounded-2xl border border-border bg-surface p-5 transition duration-300 hover:-translate-y-1 hover:border-accent/40"
              >
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-accent/10 text-accent transition group-hover:scale-110">
                    <Icon size={21} />
                  </div>
                  <ArrowUpRight
                    size={17}
                    className="text-muted transition group-hover:-translate-y-1 group-hover:translate-x-1 group-hover:text-accent"
                  />
                </div>

                <h3 className="mt-5 font-semibold">{item.title}</h3>
                <p className="mt-2 text-xs leading-6 text-muted">
                  {item.description}
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Governance statement */}
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-violet-500/20 bg-gradient-to-r from-violet-500/5 via-indigo-500/5 to-transparent p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
            <ShieldCheck size={21} />
          </div>
          <div>
            <h2 className="text-sm font-semibold">
              Intelligence without losing control.
            </h2>
            <p className="mt-1 max-w-2xl text-xs leading-6 text-muted">
              AI can assist with purchase planning, but contract
              authorization, buyer approval and payment execution
              remain separate controlled operations.
            </p>
          </div>
        </div>

        <Link
          href="/security"
          className="text-xs font-bold text-accent hover:underline"
        >
          Explore governance <ArrowRight className="ml-1 inline" size={14} />
        </Link>
      </section>

    </div>
  );
}
