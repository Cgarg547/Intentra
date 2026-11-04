import type { Metadata } from "next";
import { AgentWorkspace } from "@/components/agents/agent-workspace";

export const metadata: Metadata = { title: "AI Agents" };

export default function Page() {
  return (
    <section className="space-y-5">
      <header><p className="text-sm font-semibold text-accent">INTENTRA WORKSPACE</p><h1 className="mt-2 text-3xl font-bold tracking-tight">AI Agents</h1><p className="mt-2 max-w-2xl text-muted">Plan purchases within human-approved intent contracts. Every proposal is checked against current deterministic policy and requires your review.</p></header>
      <AgentWorkspace />
    </section>
  );
}
