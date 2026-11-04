import type { Metadata } from "next";
import { AuthPanel } from "@/components/auth/auth-panel";
import { AccountSessionStatus } from "@/components/auth/account-session-status";

export const metadata: Metadata = {
  title: "Account",
};

export default function AccountPage() {
  return (
    <main className="mx-auto min-h-screen max-w-xl px-5 py-16">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">
          INTENTRA
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-foreground">
          Account access
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Sign in to manage your human-governed intent contracts.
          This local development environment uses FastAPI session
          authentication.
        </p>
      </div>

      <AuthPanel />
      <AccountSessionStatus />
    </main>
  );
}
