"use client";

import { FilePlus2, ShieldCheck, Store, Wallet } from "lucide-react";

type Props = {
  merchantId: string;
  maximumAmount: string;
  currency: string;
  saving: boolean;
  error: string | null;
  onMerchantChange: (value: string) => void;
  onAmountChange: (value: string) => void;
  onCurrencyChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export function ContractCreateForm({
  merchantId,
  maximumAmount,
  currency,
  saving,
  error,
  onMerchantChange,
  onAmountChange,
  onCurrencyChange,
  onSubmit,
}: Props) {
  return (
    <section className="app-card overflow-hidden rounded-3xl border border-border bg-surface">
      <div className="border-b border-border px-6 py-6 sm:px-8">
        <p className="page-kicker">SPENDING AUTHORIZATION</p>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              Create an intent contract
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Define the merchant and maximum spending amount.
              Every new contract starts as a draft and requires
              separate human approval.
            </p>
          </div>

          <span className="rounded-full border border-border bg-surface-muted px-3 py-2 text-xs font-semibold">
            Draft creation
          </span>
        </div>
      </div>

      <form onSubmit={onSubmit} className="p-6 sm:p-8">
        <div className="grid gap-5 md:grid-cols-3">
          <label className="space-y-2">
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Store size={16} aria-hidden="true" />
              Merchant ID
            </span>

            <input
              required
              maxLength={128}
              value={merchantId}
              onChange={(event) =>
                onMerchantChange(event.target.value)
              }
              placeholder="Registered merchant ID"
              className="block h-12 w-full rounded-xl border border-border bg-background px-4 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Wallet size={16} aria-hidden="true" />
              Maximum amount
            </span>

            <input
              required
              type="number"
              min="0.01"
              step="0.01"
              value={maximumAmount}
              onChange={(event) =>
                onAmountChange(event.target.value)
              }
              placeholder="250.00"
              className="block h-12 w-full rounded-xl border border-border bg-background px-4 text-sm tabular-nums"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-semibold">
              Currency
            </span>

            <input
              required
              minLength={3}
              maxLength={3}
              pattern="[A-Z]{3}"
              value={currency}
              onChange={(event) =>
                onCurrencyChange(event.target.value.toUpperCase())
              }
              className="block h-12 w-full rounded-xl border border-border bg-background px-4 text-sm uppercase"
            />
          </label>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-5 rounded-xl border border-red-500/30 p-4 text-sm text-red-600"
          >
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
          <p className="max-w-xl text-xs leading-6 text-muted">
            Creating a draft does not approve spending,
            reserve budget, or initiate PayPal checkout.
          </p>

          <button
            type="submit"
            disabled={saving}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-accent px-6 text-sm font-semibold text-accent-foreground disabled:opacity-50"
          >
            <FilePlus2 size={17} aria-hidden="true" />
            {saving ? "Creating draft…" : "Create draft contract"}
          </button>
        </div>
      </form>

      <div className="flex items-start gap-3 border-t border-border bg-surface-muted px-6 py-4 sm:px-8">
        <ShieldCheck
          size={18}
          className="mt-0.5 shrink-0 text-emerald-600"
          aria-hidden="true"
        />

        <p className="text-xs leading-6 text-muted">
          INTENTRA requires explicit human approval before
          a draft contract can authorize payment evaluation.
        </p>
      </div>
    </section>
  );
}
