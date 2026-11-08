"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  LockKeyhole,
  Search,
  ServerCog,
  ShieldCheck,
  Store,
} from "lucide-react";

import type { MerchantItem } from "@/lib/workspace/client";

type Props = {
  items: MerchantItem[];
  filtered: MerchantItem[];
  configured: boolean;
  loading: boolean;
  query: string;
  onQueryChange: (value: string) => void;
};

export function MerchantRegistry({
  items,
  filtered,
  configured,
  loading,
  query,
  onQueryChange,
}: Props) {
  const verifiedCount = items.filter(
    (item) => item.provider_live_verified
  ).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-border bg-surface p-6">
          <div className="flex items-start justify-between">
            <span className="text-sm font-medium text-muted">
              Configured mappings
            </span>
            <span className="rounded-xl bg-violet-500/10 p-3 text-violet-600">
              <Store size={20} />
            </span>
          </div>
          <p className="mt-5 text-3xl font-bold tabular-nums">
            {loading ? "—" : items.length}
          </p>
          <p className="mt-2 text-xs text-muted">
            Server-controlled merchant identities
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6">
          <div className="flex items-start justify-between">
            <span className="text-sm font-medium text-muted">
              Registry configuration
            </span>
            <span className="rounded-xl bg-emerald-500/10 p-3 text-emerald-600">
              <ServerCog size={20} />
            </span>
          </div>
          <p className="mt-5 text-xl font-bold">
            {loading
              ? "Checking…"
              : configured
                ? "Configured"
                : "Unavailable"}
          </p>
          <p className="mt-2 text-xs text-muted">
            Protected backend configuration
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6">
          <div className="flex items-start justify-between">
            <span className="text-sm font-medium text-muted">
              Provider live verified
            </span>
            <span className="rounded-xl bg-sky-500/10 p-3 text-sky-600">
              <ShieldCheck size={20} />
            </span>
          </div>
          <p className="mt-5 text-3xl font-bold tabular-nums">
            {loading ? "—" : verifiedCount}
          </p>
          <p className="mt-2 text-xs text-muted">
            Based on recorded provider verification flags
          </p>
        </div>
      </div>

      <section className="overflow-hidden rounded-3xl border border-border bg-surface">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-6 sm:px-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
              Merchant governance
            </p>
            <h2 className="mt-2 text-xl font-semibold">
              Trusted merchant registry
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Review merchant identities authorized by protected
              server configuration. These records cannot be
              modified through the browser.
            </p>
          </div>

          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold ${
              loading
                ? "border-border text-muted"
                : configured
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
            }`}
          >
            {loading ? (
              <ServerCog size={15} />
            ) : configured ? (
              <CheckCircle2 size={15} />
            ) : (
              <AlertTriangle size={15} />
            )}
            {loading
              ? "CHECKING"
              : configured
                ? "CONFIGURED"
                : "UNAVAILABLE"}
          </span>
        </div>

        <div className="border-b border-border px-6 py-5 sm:px-8">
          <label className="block max-w-lg">
            <span className="mb-2 block text-xs font-semibold text-muted">
              Search merchant mappings
            </span>
            <div className="relative">
              <Search
                size={18}
                aria-hidden="true"
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                type="search"
                value={query}
                onChange={(event) =>
                  onQueryChange(event.target.value)
                }
                placeholder="Search internal or PayPal merchant ID"
                className="w-full rounded-xl border border-border bg-background py-3 pl-11 pr-4 text-sm outline-none focus:border-accent"
              />
            </div>
          </label>
        </div>

        {loading ? (
          <div
            role="status"
            className="space-y-3 px-6 py-8 sm:px-8"
          >
            <div className="h-12 animate-pulse rounded-xl bg-surface-muted" />
            <div className="h-12 animate-pulse rounded-xl bg-surface-muted" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-muted text-muted">
              <Store size={25} />
            </div>
            <h3 className="mt-5 font-semibold">
              {query.trim()
                ? "No matching merchants"
                : configured
                  ? "No merchant mappings returned"
                  : "No trusted merchant registry available"}
            </h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
              {query.trim()
                ? "Try searching for another merchant identifier."
                : "Trusted merchant mappings are managed through protected backend configuration, not this browser."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto px-6 py-5 sm:px-8">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="bg-surface-muted text-xs uppercase tracking-wider text-muted">
                  <th className="px-4 py-4 font-semibold">
                    Internal merchant
                  </th>
                  <th className="px-4 py-4 font-semibold">
                    PayPal merchant ID
                  </th>
                  <th className="px-4 py-4 font-semibold">
                    Trust source
                  </th>
                  <th className="px-4 py-4 font-semibold">
                    Provider verification
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {filtered.map((item) => (
                  <tr
                    key={item.internal_merchant_id}
                    className="transition-colors hover:bg-surface-muted"
                  >
                    <th
                      scope="row"
                      className="px-4 py-5 font-semibold"
                    >
                      <span className="inline-flex items-center gap-3">
                        <span className="rounded-lg bg-violet-500/10 p-2 text-violet-600">
                          <Store size={17} />
                        </span>
                        <span className="break-all">
                          {item.internal_merchant_id}
                        </span>
                      </span>
                    </th>

                    <td className="px-4 py-5 font-mono text-xs text-muted">
                      <span className="break-all">
                        {item.paypal_merchant_id}
                      </span>
                    </td>

                    <td className="px-4 py-5">
                      <span className="inline-flex items-center gap-2 text-xs font-medium">
                        <LockKeyhole
                          size={15}
                          className="text-muted"
                        />
                        Server configuration
                      </span>
                    </td>

                    <td className="px-4 py-5">
                      {item.provider_live_verified ? (
                        <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                          <CheckCircle2 size={14} />
                          Live verified
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2 rounded-full bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
                          <AlertTriangle size={14} />
                          Not reverified here
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-muted px-6 py-4 sm:px-8">
          <span className="text-xs text-muted">
            {loading
              ? "Loading merchant mappings…"
              : `Showing ${filtered.length} of ${items.length} mappings`}
          </span>

          <span className="inline-flex items-center gap-2 text-xs text-muted">
            <ShieldCheck size={15} className="text-emerald-600" />
            Read-only registry
          </span>
        </div>
      </section>

      <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted p-5">
        <LockKeyhole
          size={19}
          className="mt-0.5 shrink-0 text-accent"
        />
        <div>
          <p className="text-sm font-semibold">
            Merchant identity protection
          </p>
          <p className="mt-1 text-xs leading-6 text-muted">
            INTENTRA resolves payment recipients through trusted
            backend mappings. An AI proposal or browser request
            cannot substitute a PayPal merchant identity.
            A configured mapping does not by itself establish
            live provider verification.
          </p>
        </div>
        <ArrowUpRight
          size={17}
          className="ml-auto shrink-0 text-muted"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
