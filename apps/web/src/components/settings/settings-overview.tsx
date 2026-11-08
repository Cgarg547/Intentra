import {
  Bell,
  ChartNoAxesCombined,
  Palette,
  ShieldCheck,
} from "lucide-react";

const sections = [
  {
    title: "Appearance",
    description: "Theme and visual preferences",
    detail: "Browser preference",
    icon: Palette,
  },
  {
    title: "Analytics",
    description: "Default currency display filter",
    detail: "Account-scoped browser storage",
    icon: ChartNoAxesCombined,
  },
  {
    title: "Notifications",
    description: "Notification delivery preferences",
    detail: "Not configured",
    icon: Bell,
  },
  {
    title: "Financial controls",
    description: "Contracts, approvals, and payments",
    detail: "Managed in protected workflows",
    icon: ShieldCheck,
  },
];

export function SettingsOverview() {
  return (
    <section aria-label="Settings overview" className="space-y-5">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">
          Workspace configuration
        </p>

        <h2 className="mt-2 text-xl font-semibold text-foreground">
          Preferences overview
        </h2>

        <p className="mt-2 text-sm text-muted">
          Manage supported display preferences and understand
          which financial controls remain outside this page.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {sections.map((section) => {
          const Icon = section.icon;

          return (
            <article
              key={section.title}
              className="rounded-2xl border border-border bg-surface p-5 shadow-sm"
            >
              <span className="inline-flex rounded-xl bg-violet-500/10 p-3 text-accent">
                <Icon size={20} aria-hidden="true" />
              </span>

              <h3 className="mt-5 text-base font-semibold text-foreground">
                {section.title}
              </h3>

              <p className="mt-2 text-sm text-muted">
                {section.description}
              </p>

              <div className="mt-5 border-t border-border pt-4">
                <p className="text-xs font-medium text-muted">
                  {section.detail}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
