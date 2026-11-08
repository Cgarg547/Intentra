import {
  CheckCircle2,
  Circle,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import type { AgentProposal } from "@/lib/agents/client";

type Stage = {
  label: string;
  detail: string;
  complete: boolean;
};

export function ProposalProgress({
  proposal,
}: {
  proposal: AgentProposal;
}) {
  const confirmed = proposal.status === "CONFIRMED";
  const allowed = proposal.policy_decision === "ALLOW";
  const prepared = proposal.payment_preparation !== null;
  const rejected = proposal.status === "REJECTED";

  const stages: Stage[] = [
    {
      label: "Proposal created",
      detail: "Saved purchase request",
      complete: true,
    },
    {
      label: "Policy evaluated",
      detail: allowed
        ? "Allowed by policy"
        : proposal.policy_decision === "DENY"
          ? "Denied by policy"
          : "Requires clarification or evaluation",
      complete: proposal.policy_decision !== null,
    },
    {
      label: "Human review",
      detail: rejected
        ? "Proposal rejected"
        : confirmed
          ? "Proposal confirmed"
          : "Awaiting confirmation",
      complete: confirmed || rejected,
    },
    {
      label: "Budget reservation",
      detail: prepared
        ? "Payment preparation recorded"
        : "Not prepared",
      complete: prepared,
    },
  ];

  return (
    <section
      aria-label="Proposal workflow progress"
      className="mt-6 rounded-2xl border border-border bg-surface-muted/50 p-4 sm:p-5"
    >
      <div className="mb-5 flex items-center gap-2">
        <ShieldCheck
          size={17}
          className="text-accent"
          aria-hidden="true"
        />
        <h4 className="text-sm font-semibold">
          Purchase workflow
        </h4>
      </div>

      <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, index) => (
          <li key={stage.label} className="flex items-start gap-3">
            {stage.complete ? (
              <CheckCircle2
                size={20}
                className="shrink-0 text-emerald-600"
                aria-hidden="true"
              />
            ) : index === 2 || index === 3 ? (
              <Clock3
                size={20}
                className="shrink-0 text-amber-500"
                aria-hidden="true"
              />
            ) : (
              <Circle
                size={20}
                className="shrink-0 text-muted"
                aria-hidden="true"
              />
            )}

            <div className="min-w-0">
              <p className="text-xs font-semibold">
                {stage.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-muted">
                {stage.detail}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-muted">
        This progress display does not verify PayPal buyer
        approval or payment capture. Review Payments for
        the current execution outcome.
      </p>
    </section>
  );
}
