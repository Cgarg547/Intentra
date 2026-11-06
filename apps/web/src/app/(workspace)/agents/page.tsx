import type { Metadata } from "next";
import { AgentWorkspace } from "@/components/agents/agent-workspace";

export const metadata: Metadata = { title: "AI Purchasing Assistant" };

export default function Page() {
  return (
    <section className="space-y-5">
      <header><p className="text-xs font-semibold uppercase tracking-widest text-accent">INTENTRA / Purchase planning</p><h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">AI Purchasing Assistant</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted">Turn a request into a structured proposal. See what is known, what is missing, and how it fits your policy before taking the next step.</p></header>
      <AgentWorkspace />
    </section>
  );
}
