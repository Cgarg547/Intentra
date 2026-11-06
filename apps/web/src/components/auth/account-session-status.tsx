"use client";

import { useEffect, useState } from "react";
import { ApiError, getCurrentUser } from "@/lib/auth/client";
import { loadSecurity, type SecuritySummary } from "@/lib/workspace/client";

export function AccountSessionStatus() {
  const [data, setData] = useState<SecuritySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthenticated, setUnauthenticated] = useState(false);

  useEffect(() => {
    let active = true;
    let requestVersion = 0;

    async function refresh() {
      const version = ++requestVersion;
      setLoading(true);
      setData(null);
      setError(null);
      setUnauthenticated(false);

      try {
        await getCurrentUser();
        const result = await loadSecurity();
        if (active && version === requestVersion) setData(result);
      } catch (cause) {
        if (!active || version !== requestVersion) return;
        if (cause instanceof ApiError && cause.status === 401) {
          setUnauthenticated(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Session status unavailable.");
        }
      } finally {
        if (active && version === requestVersion) setLoading(false);
      }
    }

    void refresh();
    window.addEventListener("intentra:auth-changed", refresh);

    return () => {
      active = false;
      ++requestVersion;
      window.removeEventListener("intentra:auth-changed", refresh);
    };
  }, []);

  return <section className="mt-5 rounded-2xl border border-border bg-surface p-5"><h2 className="font-semibold">Session status</h2>{data ? <p className="mt-2 text-sm text-muted">Current session: {data.current_session_valid ? "valid" : "not verified"}. {data.active_session_count} active session{data.active_session_count === 1 ? "" : "s"} for this account. Sign out here to revoke this browser session.</p> : unauthenticated ? <p className="mt-2 text-sm text-muted">Sign in to inspect session status for this account.</p> : error ? <p className="mt-2 text-sm text-muted">{error}</p> : loading && <p role="status" className="mt-2 text-sm text-muted">Checking the current session…</p>}</section>;
}
