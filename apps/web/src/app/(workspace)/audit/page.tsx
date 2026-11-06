"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loadAudit, type AuditItem } from "@/lib/workspace/client";

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
    <header><p className="text-xs font-semibold uppercase tracking-widest text-accent">Immutable owner history</p><h1 className="mt-2 text-3xl font-semibold">Audit Explorer</h1><p className="mt-2 max-w-2xl text-sm text-muted">Chronological contract, proposal, payment, and reconciliation records. Filters apply only to your account and event details are screened for credential-like fields.</p></header>
    <section className="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"><label className="space-y-1 text-sm"><span>Entity type</span><select value={entity} onChange={(event) => { setSelected(null); setEntity(event.target.value); }} className="w-full rounded-lg border border-border bg-background px-3 py-2"><option value="">All entities</option>{kinds.slice(1).map((kind) => <option key={kind}>{kind}</option>)}</select></label><label className="space-y-1 text-sm"><span>Event type</span><input value={eventType} onChange={(event) => { setSelected(null); setEventType(event.target.value); }} maxLength={64} placeholder="e.g. CONTRACT_APPROVED" className="w-full rounded-lg border border-border bg-background px-3 py-2" /></label><label className="space-y-1 text-sm lg:col-span-2"><span>Search event type or details</span><input value={search} onChange={(event) => { setSelected(null); setSearch(event.target.value); }} maxLength={100} placeholder="Search recorded event data" className="w-full rounded-lg border border-border bg-background px-3 py-2" /></label></section>
    {error && <p role="alert" className="rounded-xl border border-red-500/40 p-4 text-sm text-red-600">{error}</p>}
    {loading ? <p role="status" className="rounded-2xl border border-border bg-surface p-6">Loading audit events…</p> : items.length === 0 ? <p className="rounded-2xl border border-border bg-surface p-8 text-sm text-muted">No audit events match these filters.</p> : <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.65fr)]"><ol className="divide-y divide-border rounded-2xl border border-border bg-surface">{items.map((item) => <li key={`${item.entity_type}-${item.event_id}`}><button type="button" onClick={() => setSelected(item)} aria-pressed={selected?.event_id === item.event_id} className={`w-full p-4 text-left hover:bg-surface-muted ${selected?.event_id === item.event_id ? "bg-surface-muted" : ""}`}><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{item.event_type}</span><time className="text-xs text-muted">{new Date(item.created_at).toLocaleString()}</time></div><p className="mt-1 text-xs text-muted">{item.entity_type} · {item.entity_id}{item.actor_email ? ` · ${item.actor_email}` : " · system"}</p></button></li>)}</ol><aside className="rounded-2xl border border-border bg-surface p-5"><h2 className="font-semibold">Event details</h2>{selected ? <><dl className="mt-4 space-y-3 text-sm"><div><dt className="text-xs text-muted">Event</dt><dd className="mt-1">{selected.event_type}</dd></div><div><dt className="text-xs text-muted">Actor</dt><dd className="mt-1">{selected.actor_email || (selected.actor_id ? selected.actor_id : "System")}</dd></div><div><dt className="text-xs text-muted">Related records</dt><dd className="mt-1 space-y-1">{Object.entries(selected.related_ids).map(([key, value]) => <div key={key} className="break-all"><span className="text-muted">{key}: </span>{value}</div>)}</dd></div><div><dt className="text-xs text-muted">Recorded data</dt><dd><pre className="mt-1 overflow-auto rounded-lg bg-surface-muted p-3 text-xs">{JSON.stringify(selected.event_data, null, 2)}</pre></dd></div><div><dt className="text-xs text-muted">Correlation</dt><dd className="mt-1 break-all">{selected.correlation_id || "Not assigned"}</dd></div></dl></> : <p className="mt-3 text-sm text-muted">Select an event to inspect its recorded evidence.</p>}</aside></div>}
    <nav aria-label="Audit pages" className="flex justify-between"><button type="button" onClick={() => void refresh(Math.max(0, offset - 50))} disabled={loading || offset === 0} className="rounded-xl border border-border px-4 py-2 text-sm disabled:opacity-50">Previous</button><span className="self-center text-xs text-muted">Showing {items.length} events from offset {offset}</span><button type="button" onClick={() => next !== null && void refresh(next)} disabled={loading || next === null} className="rounded-xl border border-border px-4 py-2 text-sm disabled:opacity-50">Next</button></nav>
  </section>;
}
