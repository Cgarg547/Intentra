"use client";

import { useEffect, useState } from "react";
import { loadSecurity, type SecuritySummary } from "@/lib/workspace/client";

export function AccountSessionStatus() {
  const [data, setData] = useState<SecuritySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { loadSecurity().then(setData).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Session status unavailable.")); }, []);
  return <section className="mt-5 rounded-2xl border border-border bg-surface p-5"><h2 className="font-semibold">Session status</h2>{data ? <p className="mt-2 text-sm text-muted">Current session: {data.current_session_valid ? "valid" : "not verified"}. {data.active_session_count} active session{data.active_session_count === 1 ? "" : "s"} for this account. Sign out here to revoke this browser session.</p> : error ? <p className="mt-2 text-sm text-muted">{error}</p> : <p role="status" className="mt-2 text-sm text-muted">Checking the current session…</p>}</section>;
}
