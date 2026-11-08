"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentUser,
  login,
  logout,
  register,
  type AuthUser,
} from "@/lib/auth/client";

type Mode = "login" | "register";

export function AuthPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then((result) => {
        if (active) setUser(result);
      })
      .catch((err: unknown) => {
        if (active && !(err instanceof ApiError && err.status === 401)) {
          setError("Unable to verify the current session.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const result =
        mode === "login"
          ? await login(email, password)
          : await register(email, password);

      setUser(result);
      setPassword("");
      window.dispatchEvent(new Event("intentra:auth-changed"));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Authentication failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function signOut() {
    setError(null);
    setSubmitting(true);

    try {
      await logout();
      setUser(null);
      window.dispatchEvent(new Event("intentra:auth-changed"));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Sign out failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-7">
      <h2 className="text-xl font-semibold tracking-tight text-foreground">
        Secure account access
      </h2>

      {loading ? (
        <p className="mt-4 text-sm text-muted">Checking session...</p>
      ) : user ? (
        <div className="mt-6 space-y-5">
          <p className="rounded-xl border border-border bg-background p-4 text-sm text-muted">
            Signed in as{" "}
            <strong className="text-foreground">{user.email}</strong>
          </p>
          <button
            type="button"
            onClick={signOut}
            disabled={submitting}
            className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Signing out..." : "Sign out"}
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-5">
          <div className="flex w-full gap-1 rounded-xl border border-border bg-background p-1">
            {(["login", "register"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  setMode(value);
                  setError(null);
                }}
                aria-pressed={mode === value}
                className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  mode === value
                    ? "bg-accent text-accent-foreground shadow-sm"
                    : "text-muted hover:bg-surface hover:text-foreground"
                }`}
              >
                {value === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <label className="block space-y-2 text-sm text-foreground">
            <span>Email address</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-foreground transition-colors hover:border-accent/50 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20"
            />
          </label>

          <label className="block space-y-2 text-sm text-foreground">
            <span>Password</span>
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-foreground transition-colors hover:border-accent/50 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-accent px-5 py-3.5 text-sm font-semibold text-accent-foreground transition-all duration-200 hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting
              ? "Please wait..."
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-500">
          {error}
        </p>
      )}
    </section>
  );
}
