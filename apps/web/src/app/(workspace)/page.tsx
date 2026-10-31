import {
  Activity,
  Bot,
  CreditCard,
  FileCheck2,
  ShieldCheck,
} from "lucide-react";

const metrics = [
  {
    label: "Intent contracts",
    value: "12",
    description: "Illustrative approved contracts",
    icon: FileCheck2,
  },
  {
    label: "Authorized value",
    value: "$8,420",
    description: "Illustrative authorized payments",
    icon: CreditCard,
  },
  {
    label: "Policy blocks",
    value: "7",
    description: "Illustrative rejected proposals",
    icon: ShieldCheck,
  },
  {
    label: "Active AI agents",
    value: "3",
    description: "Illustrative agent activity",
    icon: Bot,
  },
];

export default function HomePage() {
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-semibold text-accent">
            COMMAND CENTER
          </p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Financial Intelligence
          </h1>
          <p className="mt-3 max-w-2xl text-muted">
            Monitor human-approved payment intent, AI proposals, and
            authorization decisions from one unified workspace.
          </p>
        </div>
        <span className="rounded-full border border-border bg-surface px-4 py-2 text-sm text-muted">
          Demo data
        </span>
      </div>

      <section aria-label="Overview metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, description, icon: Icon }) => (
          <article
            key={label}
            className="rounded-2xl border border-border bg-surface p-6"
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted">{label}</h2>
              <Icon className="text-accent" size={22} aria-hidden="true" />
            </div>
            <p className="text-3xl font-bold tabular-nums">{value}</p>
            <p className="mt-3 text-xs text-muted">{description}</p>
          </article>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="rounded-2xl border border-border bg-surface p-6 xl:col-span-2">
          <div className="mb-6">
            <h2 className="text-xl font-bold">Authorization overview</h2>
            <p className="mt-1 text-sm text-muted">
              Illustrative payment policy decisions
            </p>
          </div>

          <div className="space-y-5">

              {[
  {
    label: "Allowed",
    count: 68,
    width: "68%",
    color: "var(--chart-allowed)",
  },
  {
    label: "Blocked",
    count: 22,
    width: "22%",
    color: "var(--chart-blocked)",
  },
  {
    label: "Review required",
    count: 10,
    width: "10%",
    color: "var(--chart-review)",
  },
].map((item) => (
              <div key={item.label}>
                <div className="mb-2 flex justify-between text-sm">
                  <span>{item.label}</span>
                  <span className="font-semibold">{item.count}%</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: item.width, backgroundColor: item.color,}}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-6">
          <div className="mb-6 flex items-center gap-3">
            <Activity className="text-accent" aria-hidden="true" />
            <h2 className="text-xl font-bold">Platform readiness</h2>
          </div>
          <p className="text-sm leading-7 text-muted">
            The payment authorization backend has completed its current
            development test milestone. Live PayPal Sandbox execution and
            full reconciliation integration remain future work.
          </p>
          <div className="mt-6 rounded-xl border border-border bg-surface-muted p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Latest verified backend milestone
            </p>
            <p className="mt-2 text-2xl font-bold">100 tests passed</p>
            <p className="mt-1 font-mono text-xs text-muted">
              Commit cfef715
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
