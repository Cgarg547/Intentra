import Link from "next/link";
import {
  ArrowRight,
  Bot,
  CircleDollarSign,
  FileCheck2,
  ShieldCheck,
  ShieldX,
  Sparkles,
} from "lucide-react";
import { MetricCard } from "@/components/dashboard/metric-card";
import { AuthorizationChart } from "@/components/dashboard/authorization-chart";
import { ActivityFeed } from "@/components/dashboard/activity-feed";

const metrics = [
  {
    label: "Active intent contracts",
    value: "12",
    detail: "Illustrative governed spending agreements",
    icon: FileCheck2,
  },
  {
    label: "Authorized spending",
    value: "$8,420",
    detail: "Simulated authorized payment volume",
    icon: CircleDollarSign,
  },
  {
    label: "Approved decisions",
    value: "68",
    detail: "Across 100 simulated requests",
    icon: ShieldCheck,
    tone: "positive" as const,
  },
  {
    label: "Blocked decisions",
    value: "22",
    detail: "Policy enforcement demonstrations",
    icon: ShieldX,
    tone: "warning" as const,
  },
  {
    label: "Connected AI agents",
    value: "3",
    detail: "Illustrative agent identities",
    icon: Bot,
  },
];

export default function CommandCenterPage() {
  return (
    <div className="space-y-7">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-surface p-7 md:p-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-32 h-80 w-80 rounded-full bg-accent opacity-10 blur-3xl"
        />

        <div className="relative">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1.5 text-xs font-medium text-foreground">
            <Sparkles aria-hidden="true" className="h-4 w-4" />
            INTENTRA FINANCIAL INTELLIGENCE
          </div>

          <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-foreground md:text-5xl">
            Human intent.
            <br />
            Intelligent financial execution.
          </h1>

          <p className="mt-5 max-w-2xl text-sm leading-7 text-muted md:text-base">
            Govern AI-driven spending through explicit intent contracts,
            deterministic policy enforcement, human approvals, and
            auditable authorization decisions.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              href="/contracts"
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground"
            >
              Explore intent contracts
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>

            <Link
              href="/audit"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-5 py-3 text-sm font-semibold text-foreground"
            >
              View audit explorer
            </Link>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Command Center
          </h2>
          <p className="mt-1 text-sm text-muted">
            Financial governance and authorization overview
          </p>
        </div>

        <span className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted">
          Demonstration data — not live payments
        </span>
      </div>

      <section
        aria-label="Key financial intelligence metrics"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5"
      >
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <AuthorizationChart />
        <ActivityFeed />
      </div>

      <section className="rounded-2xl border border-border bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              Platform engineering status
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Backend authorization and contract lifecycle tests have
              passed. PayPal Sandbox execution and production payment
              integration remain separate validation milestones.
            </p>
          </div>

          <div className="rounded-xl bg-surface-muted px-5 py-4 text-right">
            <p className="text-2xl font-semibold text-foreground">100</p>
            <p className="text-xs text-muted">Backend tests passed</p>
          </div>
        </div>
      </section>
    </div>
  );
}
