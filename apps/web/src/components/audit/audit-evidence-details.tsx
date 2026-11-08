"use client";

import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  ClipboardCopy,
  Clock3,
  Database,
  FileSearch,
  Fingerprint,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import type { AuditItem } from "@/lib/workspace/client";

type Props = {
  selected: AuditItem | null;
};

function readable(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll(":", " · ")
    .toLowerCase()
    .replace(/^./, (character) => character.toUpperCase());
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="break-all text-sm font-medium text-foreground">
        {value}
      </dd>
    </div>
  );
}

function EvidenceContent({ item }: { item: AuditItem }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const related = Object.entries(item.related_ids ?? {});
  const evidence = JSON.stringify(item.event_data ?? {}, null, 2);

  async function copyEvidence() {
    try {
      await navigator.clipboard.writeText(evidence);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <>
      <div className="border-b border-border px-5 py-5 sm:px-6">
        <div className="flex items-center gap-2">
          <span className="inline-flex rounded-lg bg-violet-500/10 p-2 text-accent">
            <ShieldCheck size={18} aria-hidden="true" />
          </span>
          <span className="text-xs font-semibold uppercase tracking-widest text-accent">
            Recorded evidence
          </span>
        </div>

        <h3 className="mt-4 break-words text-lg font-semibold text-foreground">
          {readable(item.event_type)}
        </h3>

        <p className="mt-2 break-all font-mono text-xs text-muted">
          {item.event_type}
        </p>

        <span className="mt-4 inline-flex rounded-full border border-border bg-surface-muted px-3 py-1 text-xs font-semibold uppercase text-muted">
          {item.entity_type}
        </span>
      </div>

      <div className="space-y-6 px-5 py-6 sm:px-6">
        <section aria-label="Event metadata">
          <div className="mb-4 flex items-center gap-2">
            <Clock3 size={16} className="text-accent" aria-hidden="true" />
            <h4 className="text-sm font-semibold">Event information</h4>
          </div>

          <dl className="space-y-4 rounded-2xl bg-surface-muted p-4">
            <DetailRow label="Recorded at" value={formatTime(item.created_at)} />
            <DetailRow label="Event ID" value={item.event_id} />
            <DetailRow label="Entity ID" value={item.entity_id} />
          </dl>
        </section>

        <section aria-label="Actor">
          <div className="mb-3 flex items-center gap-2">
            <UserRound size={16} className="text-accent" aria-hidden="true" />
            <h4 className="text-sm font-semibold">Recorded actor</h4>
          </div>

          <p className="break-all rounded-xl border border-border px-4 py-3 text-sm text-foreground">
            {item.actor_email || item.actor_id || "System"}
          </p>
        </section>

        <section aria-label="Related records">
          <div className="mb-3 flex items-center gap-2">
            <Database size={16} className="text-accent" aria-hidden="true" />
            <h4 className="text-sm font-semibold">Related records</h4>
          </div>

          {related.length === 0 ? (
            <p className="text-sm text-muted">
              No related record identifiers were supplied.
            </p>
          ) : (
            <dl className="space-y-3 rounded-2xl bg-surface-muted p-4">
              {related.map(([key, value]) => (
                <DetailRow key={key} label={readable(key)} value={value} />
              ))}
            </dl>
          )}
        </section>

        <section aria-label="Correlation">
          <div className="mb-3 flex items-center gap-2">
            <Fingerprint size={16} className="text-accent" aria-hidden="true" />
            <h4 className="text-sm font-semibold">Correlation</h4>
          </div>

          <p className="break-all font-mono text-xs leading-6 text-muted">
            {item.correlation_id || "Not assigned"}
          </p>
        </section>

        <section className="overflow-hidden rounded-2xl border border-border">
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-surface-muted"
          >
            <span className="flex items-center gap-2 text-sm font-semibold">
              <FileSearch size={17} className="text-accent" aria-hidden="true" />
              Technical event data
            </span>

            {expanded ? (
              <ChevronUp size={17} aria-hidden="true" />
            ) : (
              <ChevronDown size={17} aria-hidden="true" />
            )}
          </button>

          {expanded && (
            <div className="border-t border-border p-4">
              <div className="mb-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => void copyEvidence()}
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-semibold"
                >
                  {copied ? <Check size={14} /> : <ClipboardCopy size={14} />}
                  {copied ? "Copied" : "Copy JSON"}
                </button>
              </div>

              <pre className="max-h-80 overflow-auto rounded-xl bg-surface-muted p-4 text-xs leading-6 text-foreground">
                {evidence}
              </pre>
            </div>
          )}
        </section>

        <p className="text-xs leading-5 text-muted">
          This panel displays recorded, API-provided evidence.
          An event does not independently establish successful
          payment capture or complete security verification.
        </p>
      </div>
    </>
  );
}

export function AuditEvidenceDetails({ selected }: Props) {
  return (
    <aside className="self-start overflow-hidden rounded-3xl border border-border bg-surface shadow-sm xl:sticky xl:top-6">
      {selected ? (
        <EvidenceContent key={selected.event_id} item={selected} />
      ) : (
        <div className="px-6 py-10 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-muted text-accent">
            <FileSearch size={26} aria-hidden="true" />
          </div>

          <h2 className="mt-5 text-lg font-semibold text-foreground">
            Event evidence
          </h2>

          <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-muted">
            Select an event from the timeline to inspect its
            recorded metadata, related records, and technical evidence.
          </p>
        </div>
      )}
    </aside>
  );
}
