"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, RefreshCw } from "lucide-react";
import { loadSystemStatus, type SystemStatus } from "@/lib/workspace/client";

type IndicatorState = "checking" | "ready" | "attention" | "unavailable";

function stateFor(status: SystemStatus): IndicatorState {
  const apiReady = status.api?.toLowerCase() === "available";
  const databaseReady = status.database?.toLowerCase() === "available";
  if (!apiReady || !databaseReady) return "attention";
  return "ready";
}

const presentation: Record<IndicatorState, { label: string; dot: string; title: string }> = {
  checking: { label: "Checking status", dot: "bg-slate-400", title: "Checking authenticated API and database status" },
  ready: { label: "API & DB available", dot: "bg-emerald-500", title: "Authenticated API and database status are available" },
  attention: { label: "Needs attention", dot: "bg-amber-500", title: "The API or database did not report available status" },
  unavailable: { label: "Status unavailable", dot: "bg-red-500", title: "System status could not be loaded" },
};

/** A compact, truthful status summary for the workspace header. */
export function SystemStatusIndicator() {
  const [state, setState] = useState<IndicatorState>("checking");
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await loadSystemStatus();
      setState(stateFor(result));
      setCheckedAt(result.checked_at ?? null);
    } catch {
      // The detail page is the appropriate place for diagnostics. The shell
      // deliberately avoids exposing server error text in every workspace view.
      setState("unavailable");
      setCheckedAt(null);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(loadSystemStatus)
      .then((result) => {
        if (!active) return;
        setState(stateFor(result));
        setCheckedAt(result.checked_at ?? null);
      })
      .catch(() => {
        if (!active) return;
        setState("unavailable");
        setCheckedAt(null);
      });
    return () => { active = false; };
  }, []);

  const current = presentation[state];
  return (
    <div className="hidden items-center gap-1 md:flex">
      <Link
        href="/status"
        title={current.title}
        className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted hover:bg-surface-muted hover:text-foreground"
      >
        {state === "attention" || state === "unavailable"
          ? <AlertTriangle aria-hidden="true" size={14} className="text-warning" />
          : <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${current.dot}`} />}
        <span>{current.label}</span>
        {checkedAt && <span className="sr-only">, checked {new Date(checkedAt).toLocaleTimeString()}</span>}
      </Link>
      <button
        type="button"
        onClick={() => void refresh()}
        disabled={refreshing}
        aria-label="Refresh system status"
        title="Refresh system status"
        className="rounded-lg p-1.5 text-muted hover:bg-surface-muted hover:text-foreground disabled:opacity-50"
      >
        {refreshing ? <RefreshCw aria-hidden="true" size={14} className="animate-spin" /> : <Activity aria-hidden="true" size={14} />}
      </button>
    </div>
  );
}
