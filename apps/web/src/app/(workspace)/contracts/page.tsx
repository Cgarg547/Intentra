import type { Metadata } from "next";
import { ContractRegistry } from "@/components/contracts/contract-registry";

export const metadata: Metadata = {
  title: "Intent Contracts",
};

export default function ContractsPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">
          Human-governed financial execution
        </p>

        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
          Intent Contracts
        </h1>

        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Inspect spending ceilings, merchant scope, approval states,
          and contract versions. Every authorization must respect the
          human-approved contract rather than an agent&apos;s request alone.
        </p>
      </header>

      <ContractRegistry />
    </div>
  );
}
