import Link from "next/link";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  ShieldAlert,
} from "lucide-react";
import type { AgentProposal } from "@/lib/agents/client";

export function ProposalNextAction({
  proposal,
}: {
  proposal: AgentProposal;
}) {
  const prepared = proposal.payment_preparation !== null;
  const denied = proposal.policy_decision === "DENY";
  const needsInformation =
    proposal.status === "NEEDS_INFORMATION" ||
    proposal.policy_decision === "NEEDS_INFORMATION";

  let title = "Review purchase proposal";
  let description =
    "Review the extracted purchase details and policy decision before taking any further action.";
  let tone = "neutral";

  if (denied) {
    title = "Purchase blocked by policy";
    description =
      "The current policy denies this request. Review the policy explanation and applicable spending contract. Do not proceed to payment.";
    tone = "danger";
  } else if (needsInformation) {
    title = "More purchase information needed";
    description =
      "Review the missing details below. A new, explicit request may be needed before this purchase can proceed.";
    tone = "warning";
  } else if (prepared) {
    title = "Review payment execution";
    description =
      "Budget reservation and payment preparation are recorded. Buyer approval and verified capture are separate. Check Payments for the latest execution outcome.";
    tone = "warning";
  } else if (proposal.status === "CONFIRMED") {
    title = "Proposal confirmed";
    description =
      "The proposal is confirmed, but payment preparation has not been recorded. Any reservation or checkout requires a separate explicit action.";
    tone = "success";
  } else if (proposal.status === "REJECTED") {
    title = "Proposal rejected";
    description =
      "This proposal was rejected. No further payment action should be taken from this proposal.";
    tone = "danger";
  } else if (proposal.status === "DRAFT") {
    title = "Awaiting proposal evaluation";
    description =
      "This saved proposal has not reached a final review state. Refresh the record to check its latest status.";
  }

  const toneStyles = {
    neutral: "border-border bg-surface-muted/40",
    warning: "border-amber-500/25 bg-amber-500/5",
    danger: "border-rose-500/25 bg-rose-500/5",
    success: "border-emerald-500/25 bg-emerald-500/5",
  };

  const Icon =
    tone === "danger"
      ? ShieldAlert
      : tone === "warning"
        ? AlertCircle
        : tone === "success"
          ? CheckCircle2
          : Clock3;

  return (
    <section
      aria-label="Recommended next step"
      className={`mt-5 rounded-2xl border p-4 sm:p-5 ${
        toneStyles[tone as keyof typeof toneStyles]
      }`}
    >
      <div className="flex items-start gap-3">
        <Icon
          size={21}
          className="mt-0.5 shrink-0 text-accent"
          aria-hidden="true"
        />

        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold uppercase tracking-widest text-muted">
            Next step
          </p>

          <h4 className="mt-1 text-base font-semibold">
            {title}
          </h4>

          <p className="mt-2 text-sm leading-6 text-muted">
            {description}
          </p>

          {prepared && !denied && (
            <Link
              href="/payments"
              className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-accent hover:underline"
            >
              Review payments
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
