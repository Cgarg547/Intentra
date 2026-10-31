import type { Metadata } from "next";
import { SpendingChart } from "@/components/analytics/spending-chart";
import { TransactionTable } from "@/components/analytics/transaction-table";

export const metadata: Metadata = {
  title: "Financial Analytics",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">
          Financial intelligence
        </p>

        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
          Analytics & transaction intelligence
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Explore spending behavior, policy outcomes, and explainable
          agent authorization decisions using simulated demonstration data.
        </p>
      </header>

      <SpendingChart />
      <TransactionTable />
    </div>
  );
}
