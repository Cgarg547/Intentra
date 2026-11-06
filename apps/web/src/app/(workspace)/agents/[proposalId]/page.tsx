import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProposalDetail } from "@/components/agents/proposal-detail";

export const metadata: Metadata = { title: "Proposal details" };

export default async function Page({ params }: { params: Promise<{ proposalId: string }> }) {
  const { proposalId } = await params;
  if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(proposalId)) notFound();
  return <ProposalDetail key={proposalId} proposalId={proposalId} />;
}
