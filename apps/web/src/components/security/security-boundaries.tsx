import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  CreditCard,
  FileSearch,
  LockKeyhole,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";

const controls = [
  {
    title: "Human authorization",
    description:
      "AI-generated proposals cannot approve contracts or authorize payment capture. Contract approval remains a separate human-controlled action.",
    icon: UserRoundCheck,
  },
  {
    title: "Payment execution boundaries",
    description:
      "Budget reservation, buyer approval, and payment capture are distinct steps. A pending payment attempt is not a successful payment.",
    icon: CreditCard,
  },
  {
    title: "Recorded security visibility",
    description:
      "Security Center displays recorded account and policy states. It does not perform live anomaly detection or guarantee the absence of threats.",
    icon: FileSearch,
  },
];

export function SecurityBoundaries() {
  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-surface shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-6 sm:px-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-accent">
            Governance framework
          </p>

          <h2 className="mt-2 text-xl font-semibold text-foreground">
            Security control boundaries
          </h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Understand the separation between AI assistance,
            human decisions, and payment execution.
          </p>
        </div>

        <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-600">
          <LockKeyhole size={24} aria-hidden="true" />
        </span>
      </div>

      <div className="grid gap-4 p-6 lg:grid-cols-3 sm:p-8">
        {controls.map((control) => {
          const Icon = control.icon;

          return (
            <article
              key={control.title}
              className="rounded-2xl border border-border bg-surface-muted p-5"
            >
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-surface text-accent">
                <Icon size={21} aria-hidden="true" />
              </span>

              <h3 className="mt-5 text-base font-semibold text-foreground">
                {control.title}
              </h3>

              <p className="mt-3 text-sm leading-6 text-muted">
                {control.description}
              </p>
            </article>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border bg-surface-muted px-6 py-5 sm:px-8">
        <div className="flex items-center gap-3">
          <ShieldCheck
            size={20}
            className="shrink-0 text-emerald-600"
            aria-hidden="true"
          />

          <div>
            <p className="text-sm font-semibold text-foreground">
              Human-controlled financial operations
            </p>
            <p className="mt-1 text-xs text-muted">
              Recorded safeguards and account visibility
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            href="/audit"
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-background"
          >
            <FileSearch size={16} aria-hidden="true" />
            Audit Explorer
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>

          <Link
            href="/account"
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition-opacity hover:opacity-90"
          >
            <Bot size={16} aria-hidden="true" />
            Manage session
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
