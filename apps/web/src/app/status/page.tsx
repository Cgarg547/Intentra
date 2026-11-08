"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Bot,
  Clock3,
  Cpu,
  RefreshCw,
  Server,
  ShieldCheck,
  FlaskConical,
} from "lucide-react";

import { SystemHealthOverview } from "@/components/status/system-health-overview";
import {
  loadSystemStatus,
  type SystemStatus,
} from "@/lib/workspace/client";

function formatTime(value?: string): string {
  if (!value) return "Not reported";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Invalid timestamp"
    : date.toLocaleString();
}

function reportedValue(value?: string): string {
  return value?.trim()
    ? value.replaceAll("_", " ")
    : "Not reported";
}

function InfrastructureCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value?: string;
  description: string;
  icon: typeof Cpu;
}) {
  return (
    <article className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted">{title}</p>
        <span className="rounded-xl bg-violet-500/10 p-3 text-accent">
          <Icon size={20} aria-hidden="true" />
        </span>
      </div>

      <p className="mt-5 break-words text-xl font-semibold capitalize text-foreground">
        {reportedValue(value)}
      </p>

      <p className="mt-3 text-xs leading-5 text-muted">
        {description}
      </p>

      <p className="mt-3 break-all font-mono text-xs text-muted">
        Reported: {value ?? "Not provided"}
      </p>
    </article>
  );
}

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestVersion = useRef(0);

  const refresh = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    setStatus(null);

    try {
      const result = await loadSystemStatus();
      if (version === requestVersion.current) {
        setStatus(result);
      }
    } catch (cause) {
      if (version === requestVersion.current) {
        setError(
          cause instanceof Error
            ? cause.message
            : "System status is unavailable."
        );
      }
    } finally {
      if (version === requestVersion.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => refresh());
    return () => {
      requestVersion.current += 1;
    };
  }, [refresh]);

  return (
    <main className="mx-auto min-h-screen max-w-7xl space-y-8 bg-background px-4 py-8 text-foreground sm:px-8 lg:px-10">
      <header className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="page-kicker">
            Infrastructure & operations
          </p>

          <h1 className="page-title mt-2 text-3xl sm:text-4xl">
            System Status
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Monitor INTENTRA infrastructure, payment configuration,
            and AI runtime diagnostics through authenticated,
            backend-reported information.
          </p>
        </div>

        <button
          type="button"
          disabled={loading}
          onClick={() => void refresh()}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-5 py-3 text-sm font-semibold transition-colors hover:bg-surface-muted disabled:opacity-50"
        >
          <RefreshCw
            size={17}
            className={loading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          {loading ? "Checking…" : "Refresh status"}
        </button>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-5"
        >
          <p className="font-semibold text-rose-600 dark:text-rose-400">
            System status unavailable
          </p>
          <p className="mt-2 text-sm text-muted">{error}</p>
          <p className="mt-2 text-xs text-muted">
            No service health can be confirmed from this failed request.
          </p>
        </div>
      )}

      <SystemHealthOverview data={status} loading={loading} />

      <section className="space-y-5">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
            AI infrastructure
          </p>
          <h2 className="mt-2 text-xl font-semibold">
            AI runtime & provider
          </h2>
          <p className="mt-2 text-sm text-muted">
            Configuration and diagnostic values reported by the backend.
            These indicators do not initiate AI inference.
          </p>
        </div>

        {(status?.llm_mode?.toLowerCase() === "simulated" ||
          status?.llm_provider?.toLowerCase() === "mock") && (
          <div
            role="status"
            className="flex items-start gap-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5"
          >
            <span className="rounded-xl bg-amber-500/10 p-3 text-amber-600 dark:text-amber-400">
              <FlaskConical size={22} aria-hidden="true" />
            </span>

            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-semibold text-foreground">
                  AI Simulation Mode
                </h3>

                <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                  Simulated
                </span>
              </div>

              <p className="mt-2 text-sm leading-6 text-muted">
                The backend currently reports a simulated AI mode
                or mock provider. AI responses may be generated
                through test behavior rather than live model inference.
                This status does not establish Ollama connectivity
                or successful real-model generation.
              </p>

              <p className="mt-3 font-mono text-xs text-muted">
                Mode: {status.llm_mode ?? "Not reported"}
                {" · "}
                Provider: {status.llm_provider ?? "Not reported"}
              </p>
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <InfrastructureCard
            title="AI mode"
            value={status?.llm_mode}
            description="Configured AI execution mode."
            icon={Bot}
          />
          <InfrastructureCard
            title="AI provider"
            value={status?.llm_provider}
            description="Selected language-model provider."
            icon={Server}
          />
          <InfrastructureCard
            title="AI runtime"
            value={status?.llm_runtime}
            description="Reported runtime diagnostic."
            icon={Activity}
          />
          <InfrastructureCard
            title="Local model"
            value={status?.llm_model_status}
            description="Reported local-model availability."
            icon={Cpu}
          />
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-violet-500/10 p-3 text-accent">
              <Clock3 size={20} aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-semibold">Last status report</h2>
              <p className="mt-1 text-sm text-muted">
                {formatTime(status?.checked_at)}
              </p>
            </div>
          </div>

          <span className="rounded-full bg-surface-muted px-3 py-1.5 text-xs font-medium text-muted">
            Read-only diagnostics
          </span>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-surface-muted p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck
            size={20}
            className="mt-0.5 shrink-0 text-accent"
            aria-hidden="true"
          />
          <div>
            <h2 className="text-sm font-semibold">
              Operational transparency
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              Status reflects the latest authenticated API response.
              Configured PayPal credentials do not verify PayPal
              connectivity or successful payment capture. AI runtime
              diagnostics do not prove generation success. Missing
              fields and failed requests must not be interpreted as healthy.
            </p>
          </div>
        </div>
      </section>

      <Link
        href="/"
        className="inline-flex items-center gap-2 text-sm font-semibold text-accent hover:underline"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        Return to workspace
      </Link>
    </main>
  );
}
