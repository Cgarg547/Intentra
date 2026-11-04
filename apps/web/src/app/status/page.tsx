"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { loadSystemStatus, type SystemStatus } from "@/lib/workspace/client";

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => { setLoading(true); setError(null); try { setStatus(await loadSystemStatus()); } catch (cause) { setError(cause instanceof Error ? cause.message : "System status unavailable."); } finally { setLoading(false); } }, []);
  useEffect(() => {
    let active = true;
    loadSystemStatus().then((result) => { if (active) setStatus(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "System status unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const rows = status ? [["API", status.api], ["Database", status.database], ["PayPal Sandbox", status.paypal_sandbox], ["Trusted merchant registry", status.trusted_merchants], ["AI provider", status.llm_provider], ["AI configuration", status.llm_mode], ["AI runtime", status.llm_runtime], ["Local model", status.llm_model_status]] : [];
  return <main className="mx-auto min-h-screen max-w-5xl space-y-6 bg-background px-4 py-10 text-foreground sm:px-8"><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-accent">Operational status</p><h1 className="mt-2 text-3xl font-semibold">INTENTRA System Status</h1><p className="mt-2 max-w-2xl text-sm text-muted">Configuration readiness is reported separately from live provider verification. This view does not contact PayPal.</p></div><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-xl border border-border px-4 py-2 text-sm">Refresh</button></header>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 bg-surface p-4 text-sm text-red-600">{error}</p>}
    {loading && !status ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Checking authenticated service status…</p> : status && <><section className="grid gap-4 sm:grid-cols-2">{rows.map(([label, value]) => <article key={label} className="rounded-2xl border border-border bg-surface p-5"><p className="text-sm text-muted">{label}</p><p className="mt-3 text-lg font-semibold">{value.replaceAll("_", " ")}</p></article>)}</section><p className="text-xs text-muted">Checked {new Date(status.checked_at).toLocaleString()}. API and database status reflect this authenticated request. Ollama runtime status uses a read-only local model-list check; it does not run a model. OpenAI availability is not checked. PayPal credentials being configured does not verify provider availability.</p></>}
    <Link href="/" className="inline-block text-sm text-accent underline">Return to workspace</Link></main>;
}
