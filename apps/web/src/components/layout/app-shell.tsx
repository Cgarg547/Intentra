"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  Menu,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { navigation } from "@/lib/navigation";
import { ThemeSelector } from "./theme-selector";
import { SessionMenu } from "./session-menu";
import { SystemStatusIndicator } from "./system-status-indicator";

const groups = [
  {
    title: "WORKSPACE",
    links: ["/", "/agents", "/approvals"],
  },
  {
    title: "FINANCIAL OPERATIONS",
    links: ["/contracts", "/payments", "/merchants", "/analytics"],
  },
  {
    title: "GOVERNANCE",
    links: ["/security", "/audit", "/status"],
  },
  {
    title: "PREFERENCES",
    links: ["/settings", "/account"],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const wasMenuOpen = useRef(false);

  useEffect(() => {
    if (!menuOpen) return;

    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [menuOpen]);

  useEffect(() => {
    if (menuOpen) {
      closeButtonRef.current?.focus();
    } else if (wasMenuOpen.current) {
      menuButtonRef.current?.focus();
    }

    wasMenuOpen.current = menuOpen;
  }, [menuOpen]);

  const currentPage =
    navigation.find(
      (item) =>
        pathname === item.href ||
        (item.href !== "/" && pathname.startsWith(`${item.href}/`)),
    )?.label ?? "Workspace";

  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-3 focus:text-accent-foreground"
      >
        Skip to main content
      </a>

      <div className="lg:flex">
        {/* Sidebar */}
        <aside
          id="primary-navigation"
          aria-label="Primary navigation"
          className={`fixed inset-y-0 left-0 z-50 flex w-[17rem] flex-col overflow-y-auto border-r border-border bg-surface p-5 shadow-2xl shadow-black/20 transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none ${
            menuOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-9 flex items-center justify-between">
            <Link
              href="/"
              onClick={() => setMenuOpen(false)}
              className="group flex items-center gap-3"
            >
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-700 text-white shadow-lg shadow-violet-500/25 transition-transform group-hover:scale-105">
                <ShieldCheck size={25} />
              </span>
              <span>
                <span className="block text-xl font-black tracking-[-0.07em]">
                  INTENTRA
                </span>
                <span className="block text-[10px] font-semibold tracking-[0.18em] text-muted">
                  FINANCIAL INTELLIGENCE
                </span>
              </span>
            </Link>

            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              aria-label="Close navigation"
              ref={closeButtonRef}
              className="rounded-lg p-2 hover:bg-surface-muted lg:hidden"
            >
              <X size={20} />
            </button>
          </div>

          <div className="mb-7 rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-500/10 via-indigo-500/5 to-transparent p-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,.7)]" />
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted">
                Environment
              </span>
            </div>
            <p className="mt-2 text-sm font-bold">Sandbox workspace</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              Controlled purchasing with explicit human authorization.
            </p>
          </div>

          <nav aria-label="Workspace" className="flex-1 space-y-7">
            {groups.map((group) => (
              <section key={group.title}>
                <p className="mb-3 px-3 text-[10px] font-extrabold tracking-[0.16em] text-muted/80">
                  {group.title}
                </p>

                <div className="space-y-1">
                  {navigation
                    .filter((item) => group.links.includes(item.href))
                    .map(({ label, href, icon: Icon }) => {
                      const active =
                        pathname === href ||
                        (href !== "/" && pathname.startsWith(`${href}/`));

                      return (
                        <Link
                          key={href}
                          href={href}
                          aria-current={active ? "page" : undefined}
                          onClick={() => setMenuOpen(false)}
                          className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-200 ${
                            active
                              ? "bg-accent text-accent-foreground shadow-md shadow-violet-500/15"
                              : "text-muted hover:translate-x-0.5 hover:bg-surface-muted hover:text-foreground"
                          }`}
                        >
                          <Icon
                            size={18}
                            className={
                              active
                                ? "text-accent-foreground"
                                : "text-muted transition-colors group-hover:text-accent"
                            }
                            aria-hidden="true"
                          />
                          <span>{label}</span>
                          {active && (
                            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-current" />
                          )}
                        </Link>
                      );
                    })}
                </div>
              </section>
            ))}
          </nav>

          <div className="mt-8 rounded-2xl border border-border bg-surface-muted/70 p-4">
            <div className="flex items-center gap-2 text-accent">
              <Sparkles size={16} />
              <span className="text-xs font-bold">Human-first AI</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted">
              AI assists with decisions. People retain financial authority.
            </p>
            <Link
              href="/security"
              onClick={() => setMenuOpen(false)}
              className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline"
            >
              Explore security
              <ArrowUpRight size={13} />
            </Link>
          </div>

          <div className="mt-5 border-t border-border pt-4 text-[10px] text-muted">
            INTENTRA · 2026
            <span className="float-right">v1.0</span>
          </div>
        </aside>

        {menuOpen && (
          <button
            type="button"
            aria-label="Close navigation overlay"
            className="fixed inset-y-0 right-0 left-[min(17rem,calc(100vw-3rem))] z-40 bg-slate-950/60 backdrop-blur-sm lg:hidden"
            onClick={() => setMenuOpen(false)}
          />
        )}

        {/* Main workspace */}
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex min-h-[4.5rem] items-center justify-between gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-2xl sm:px-7 lg:px-9">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMenuOpen(true)}
                aria-label="Open navigation"
                ref={menuButtonRef}
                aria-expanded={menuOpen}
                aria-controls="primary-navigation"
                className="rounded-xl border border-border bg-surface p-2 hover:border-accent lg:hidden"
              >
                <Menu size={19} />
              </button>

              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{currentPage}</p>
                <p className="hidden text-[11px] text-muted sm:block">
                  INTENTRA / Financial operations
                </p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2 sm:gap-3">
              <SystemStatusIndicator />
              <div className="hidden h-7 w-px bg-border sm:block" />
              <ThemeSelector />
              <SessionMenu />
            </div>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto w-full max-w-[100rem] flex-1 px-4 py-6 outline-none sm:px-7 sm:py-8 lg:px-9 lg:py-9"
          >
            {children}
          </main>

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-5 text-[11px] text-muted sm:px-7 lg:px-9">
            <span>© 2026 INTENTRA · Financial intelligence</span>
            <span className="flex items-center gap-2">
              <ShieldCheck size={13} className="text-accent" />
              Human-authorized financial operations
            </span>
          </footer>
        </div>
      </div>
    </div>
  );
}
