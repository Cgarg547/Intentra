"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loadAudit, type AuditItem } from "@/lib/workspace/client";
import { AuditOverview } from "@/components/audit/audit-overview";
import { AuditEventTimeline } from "@/components/audit/audit-event-timeline";
import { AuditEvidenceDetails } from "@/components/audit/audit-evidence-details";

const kinds = ["", "contract", "proposal", "payment", "reconciliation", "evaluation"];

export default function AuditPage() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [entity, setEntity] = useState("");
  const [eventType, setEventType] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [selected, setSelected] = useState<AuditItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const refresh = useCallback(async (at = 0) => {
    const version = ++requestVersion.current;
    setLoading(true); setError(null);
    setSelected(null);
    try {
      const page = await loadAudit({ entity_type: entity || undefined, event_type: eventType || undefined, q: search || undefined, offset: at });
      if (version !== requestVersion.current) return;
      setItems(page.items); setOffset(page.offset); setNext(page.next_offset);
    }
    catch (cause) {
      if (version === requestVersion.current) setError(cause instanceof Error ? cause.message : "Audit history unavailable.");
    }
    finally { if (version === requestVersion.current) setLoading(false); }
  }, [entity, eventType, search]);
  useEffect(() => {
    void Promise.resolve().then(() => refresh(0));
  }, [refresh]);
  return <section className="space-y-6">
    <header><p className="page-kicker">Immutable owner history</p><h1 className="page-title mt-2 text-3xl">Audit Explorer</h1><p className="mt-2 max-w-2xl text-sm text-muted">Chronological contract, proposal, payment, and reconciliation records. Filters apply only to your account and event details are screened for credential-like fields.</p></header>
    <AuditOverview items={items} loading={loading} />
    <section className="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"><label className="space-y-1 text-sm"><span>Entity type</span><select value={entity} onChange={(event) => { setSelected(null); setEntity(event.target.value); }} className="w-full rounded-lg border border-border bg-background px-3 py-2"><option value="">All entities</option>{kinds.slice(1).map((kind) => <option key={kind}>{kind}</option>)}</select></label><label className="space-y-1 text-sm"><span>Event type</span><input value={eventType} onChange={(event) => { setSelected(null); setEventType(event.target.value); }} maxLength={64} placeholder="e.g. CONTRACT_APPROVED" className="w-full rounded-lg border border-border bg-background px-3 py-2" /></label><label className="space-y-1 text-sm lg:col-span-2"><span>Search event type or details</span><input value={search} onChange={(event) => { setSelected(null); setSearch(event.target.value); }} maxLength={100} placeholder="Search recorded event data" className="w-full rounded-lg border border-border bg-background px-3 py-2" /></label></section>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    {loading ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Loading audit events…</p> : items.length === 0 ? <p className="rounded-2xl border border-border bg-surface p-8 text-sm text-muted">No audit events match these filters.</p> : <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.65fr)]"><AuditEventTimeline items={items} selected={selected} onSelect={setSelected} /><AuditEvidenceDetails selected={selected} /></div>}
    <nav aria-label="Audit pages" className="flex justify-between"><button type="button" onClick={() => void refresh(Math.max(0, offset - 50))} disabled={loading || offset === 0} className="rounded-xl border border-border px-4 py-2 text-sm disabled:opacity-50">Previous</button><span className="self-center text-xs text-muted">Showing {items.length} events from offset {offset}</span><button type="button" onClick={() => next !== null && void refresh(next)} disabled={loading || next === null} className="rounded-xl border border-border px-4 py-2 text-sm disabled:opacity-50">Next</button></nav>
  </section>;
}
