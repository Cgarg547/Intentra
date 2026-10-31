"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import { navigation } from "@/lib/navigation";
import { ThemeSelector } from "./theme-selector";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;

    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [menuOpen]);

  const navLinks = navigation.map(({ label, href, icon: Icon }) => {
    const active =
      pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));

    return (
      <Link
        key={href}
        href={href}
        aria-current={active ? "page" : undefined}
        onClick={() => setMenuOpen(false)}
        className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-colors ${
          active
            ? "bg-accent text-accent-foreground"
            : "text-muted hover:bg-surface-muted hover:text-foreground"
        }`}
      >
        <Icon size={19} aria-hidden="true" />
        {label}
      </Link>
    );
  });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-3 focus:text-accent-foreground"
      >
        Skip to main content
      </a>

      <div className="lg:flex">
        <aside
          id="primary-navigation"
          aria-label="Primary navigation"
          className={`fixed inset-y-0 left-0 z-40 w-72 overflow-y-auto border-r border-border bg-surface p-5 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
            menuOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-8 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-3">
              <span className="rounded-xl bg-accent p-2 text-accent-foreground">
                <ShieldCheck size={24} aria-hidden="true" />
              </span>
              <span>
                <span className="block text-lg font-extrabold tracking-wide">
                  INTENTRA
                </span>
                <span className="block text-xs text-muted">
                  Financial Intelligence
                </span>
              </span>
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              aria-label="Close navigation"
              className="rounded-lg p-2 lg:hidden"
            >
              <X aria-hidden="true" />
            </button>
          </div>

          <nav aria-label="Workspace">
            <p className="mb-3 px-3 text-xs font-bold uppercase tracking-widest text-muted">
              Workspace
            </p>
            <div className="space-y-1">{navLinks}</div>
          </nav>
        </aside>

        {menuOpen && (
          <button
            type="button"
            aria-label="Close navigation overlay"
            className="fixed inset-0 z-30 bg-black/60 lg:hidden"
            onClick={() => setMenuOpen(false)}
          />
        )}

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-8">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setMenuOpen(true)}
                aria-label="Open navigation"
                aria-expanded={menuOpen}
                aria-controls="primary-navigation"
                className="rounded-lg border border-border p-2 lg:hidden"
              >
                <Menu size={21} aria-hidden="true" />
              </button>
              <div>
                <p className="text-sm font-bold">INTENTRA Workspace</p>
                <p className="text-xs text-muted">
                  Human-governed AI payments
                </p>
              </div>
            </div>
            <ThemeSelector />
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 outline-none sm:px-8"
          >
            {children}
          </main>

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-5 text-xs text-muted sm:px-8">
            <span>© 2026 INTENTRA. Human Intent. Agent Execution.</span>
            <span>Accessible by design · Sandbox-first development</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
