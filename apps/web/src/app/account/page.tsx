import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Fingerprint,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { AuthPanel } from "@/components/auth/auth-panel";
import { AccountSessionStatus } from "@/components/auth/account-session-status";

export const metadata: Metadata = {
  title: "Account Access",
};

export default function AccountPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">

        <section className="relative flex min-h-[390px] flex-col overflow-hidden bg-[#0c1023] px-7 py-8 text-white sm:px-12 lg:min-h-screen lg:px-16 lg:py-12">

          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_20%,rgba(111,87,255,.32),transparent_40%),radial-gradient(ellipse_at_85%_75%,rgba(39,116,255,.19),transparent_45%)]" />

          <div className="pointer-events-none absolute right-[-100px] top-[20%] h-80 w-80 rounded-full border border-violet-300/20 [transform:rotateX(65deg)_rotateZ(-25deg)]" />
          <div className="pointer-events-none absolute right-[-60px] top-[23%] h-64 w-64 rounded-full border border-violet-300/20 [transform:rotateX(65deg)_rotateZ(25deg)]" />

          <div className="relative z-10 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-violet-500 shadow-lg shadow-violet-500/30">
              <ShieldCheck size={25} />
            </div>
            <div>
              <p className="text-xl font-extrabold tracking-[-0.06em]">
                INTENTRA
              </p>
              <p className="text-[10px] tracking-[0.2em] text-slate-400">
                FINANCIAL INTELLIGENCE
              </p>
            </div>
          </div>

          <div className="relative z-10 my-auto max-w-xl py-14">
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-300/20 bg-white/5 px-4 py-2 text-xs text-violet-200 backdrop-blur">
              <Sparkles size={14} />
              Intelligent purchasing. Human control.
            </div>

            <h1 className="text-4xl font-semibold leading-[1.12] tracking-[-0.055em] sm:text-6xl">
              Financial decisions,
              <span className="block bg-gradient-to-r from-violet-300 via-purple-300 to-blue-300 bg-clip-text text-transparent">
                made intelligent.
              </span>
            </h1>

            <p className="mt-7 max-w-lg text-sm leading-7 text-slate-300 sm:text-base">
              Let AI understand your purchasing intent, evaluate spending
              policies and prepare proposals. You remain in control of every
              financial authorization.
            </p>

            <div className="mt-12 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur-xl">
                <Workflow className="mb-4 text-violet-300" size={25} />
                <h2 className="text-sm font-semibold">Intelligent workflows</h2>
                <p className="mt-2 text-xs leading-5 text-slate-400">
                  Turn purchasing requests into structured proposals.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur-xl">
                <Fingerprint className="mb-4 text-blue-300" size={25} />
                <h2 className="text-sm font-semibold">Human authorization</h2>
                <p className="mt-2 text-xs leading-5 text-slate-400">
                  Keep approvals, spending limits and execution separate.
                </p>
              </div>
            </div>
          </div>

          <div className="relative z-10 flex flex-wrap justify-between gap-3 border-t border-white/10 pt-6 text-xs text-slate-400">
            <span>© 2026 INTENTRA</span>
            <span>Sandbox-first financial operations</span>
          </div>
        </section>

        <section className="flex flex-col justify-center px-5 py-10 sm:px-12 lg:px-16">
          <div className="mx-auto w-full max-w-md">

            <Link
              href="/"
              className="mb-12 inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-medium text-muted transition hover:border-accent hover:text-accent"
            >
              <ArrowLeft size={16} />
              Return to workspace
            </Link>

            <div className="mb-8">
              <p className="text-xs font-bold uppercase tracking-[0.17em] text-accent">
                Welcome to INTENTRA
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
                Your workspace awaits.
              </h2>
              <p className="mt-3 text-sm leading-6 text-muted">
                Sign in to access your purchasing intelligence,
                authorization policies and financial operations.
              </p>
            </div>

            <AuthPanel />
            <AccountSessionStatus />

            <div className="mt-8 flex items-center justify-center gap-2 text-xs text-muted">
              <ShieldCheck size={15} className="text-accent" />
              Secure, session-based account access
              <ArrowRight size={13} />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
