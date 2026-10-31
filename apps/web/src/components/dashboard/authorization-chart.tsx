const decisions = [
  {
    label: "Allowed",
    count: 68,
    percent: 68,
    color: "var(--chart-allowed, #16a34a)",
  },
  {
    label: "Blocked",
    count: 22,
    percent: 22,
    color: "var(--chart-blocked, #dc2626)",
  },
  {
    label: "Needs review",
    count: 10,
    percent: 10,
    color: "var(--chart-review, #ca8a04)",
  },
];

export function AuthorizationChart() {
  return (
    <section
      aria-labelledby="authorization-heading"
      className="rounded-2xl border border-border bg-surface p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="authorization-heading"
            className="text-lg font-semibold text-foreground"
          >
            Authorization intelligence
          </h2>
          <p className="mt-1 text-sm text-muted">
            Illustrative authorization outcomes
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1 text-xs text-muted">
          Demo data
        </span>
      </div>

      <div className="mt-7 space-y-6">
        {decisions.map((decision) => (
          <div key={decision.label}>
            <div className="mb-2 flex justify-between gap-4 text-sm">
              <span className="font-medium text-foreground">
                {decision.label}
              </span>
              <span className="font-semibold text-foreground">
                {decision.percent}%
              </span>
            </div>

            <div
              role="progressbar"
              aria-label={`${decision.label} authorization share`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={decision.percent}
              className="h-3 overflow-hidden rounded-full bg-surface-muted"
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${decision.percent}%`,
                  backgroundColor: decision.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="mt-7 border-t border-border pt-4 text-xs text-muted">
        Sample distribution across 100 simulated authorization decisions.
        No live payment activity is represented.
      </p>
    </section>
  );
}
