import type { ComponentProps, ReactNode } from "react";

type Tone = "neutral" | "positive" | "warning" | "danger";

const badgeTone: Record<Tone, string> = {
  neutral: "border-border bg-surface-muted text-foreground",
  positive: "border-emerald-800/20 bg-emerald-800/10 text-emerald-950 dark:text-emerald-200",
  warning: "border-amber-800/20 bg-amber-700/10 text-amber-950 dark:text-amber-200",
  danger: "border-red-800/20 bg-red-700/10 text-red-950 dark:text-red-200",
};

export function Badge({ children, tone = "neutral", className = "" }: { children: ReactNode; tone?: Tone; className?: string }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeTone[tone]} ${className}`}>{children}</span>;
}

export function Card({ children, className = "", ...props }: ComponentProps<"section">) {
  return <section className={`rounded-2xl border border-border bg-surface ${className}`} {...props}>{children}</section>;
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center"><h3 className="font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">{children}</p></div>;
}
