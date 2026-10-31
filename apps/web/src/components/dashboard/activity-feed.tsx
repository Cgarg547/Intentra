import {
  CheckCircle2,
  ShieldAlert,
  Clock3,
} from "lucide-react";

const activities = [
  {
    id: "DEC-1008",
    agent: "Procurement Agent",
    description: "Purchase approved within contract limits",
    status: "Allowed",
    time: "2 min ago",
    icon: CheckCircle2,
  },
  {
    id: "DEC-1007",
    agent: "Travel Booking Agent",
    description: "Merchant category outside approved scope",
    status: "Blocked",
    time: "8 min ago",
    icon: ShieldAlert,
  },
  {
    id: "DEC-1006",
    agent: "Operations Agent",
    description: "Additional human authorization requested",
    status: "Review",
    time: "15 min ago",
    icon: Clock3,
  },
];

export function ActivityFeed() {
  return (
    <section
      aria-labelledby="activity-heading"
      className="rounded-2xl border border-border bg-surface p-6"
    >
      <h2
        id="activity-heading"
        className="text-lg font-semibold text-foreground"
      >
        Recent agent decisions
      </h2>

      <p className="mt-1 text-sm text-muted">
        Simulated activity for the INTENTRA demonstration
      </p>

      <ol className="mt-6 divide-y divide-border">
        {activities.map((activity) => {
          const Icon = activity.icon;

          return (
            <li key={activity.id} className="flex gap-4 py-4">
              <div className="shrink-0 rounded-xl bg-surface-muted p-3">
                <Icon
                  aria-hidden="true"
                  className="h-5 w-5 text-foreground"
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap justify-between gap-2">
                  <p className="font-medium text-foreground">
                    {activity.agent}
                  </p>
                  <span className="text-xs text-muted">
                    {activity.time}
                  </span>
                </div>

                <p className="mt-1 text-sm text-muted">
                  {activity.description}
                </p>

                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md border border-border px-2 py-1 font-medium text-foreground">
                    {activity.status}
                  </span>
                  <span className="text-muted">{activity.id}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
