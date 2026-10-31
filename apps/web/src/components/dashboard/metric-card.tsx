import type { LucideIcon } from "lucide-react";

type MetricCardProps = {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "positive" | "warning";
};

const tones = {
  default: "text-accent",
  positive: "text-emerald-500",
  warning: "text-amber-500",
};

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: MetricCardProps) {
  return (
    <article className="group rounded-2xl border border-border bg-surface p-5 transition-shadow hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted">{label}</p>
        <div className="rounded-xl bg-surface-muted p-2.5">
          <Icon
            aria-hidden="true"
            className={`h-5 w-5 ${tones[tone]}`}
          />
        </div>
      </div>

      <p className="mt-4 text-3xl font-semibold tracking-tight text-foreground">
        {value}
      </p>

      <p className="mt-2 text-xs text-muted">{detail}</p>
    </article>
  );
}
