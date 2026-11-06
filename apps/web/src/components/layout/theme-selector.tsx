"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

const choices = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
  { value: "contrast", label: "High contrast" },
];

const subscribe = () => () => {};

function useIsClient() {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );
}

export function ThemeSelector() {
  const { theme, setTheme } = useTheme();
  const mounted = useIsClient();

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden text-muted sm:inline">Appearance</span>

      <select
        aria-label="Appearance theme"
        value={mounted ? theme ?? "system" : "system"}
        onChange={(event) => setTheme(event.target.value)}
        disabled={!mounted}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-foreground"
      >
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    </label>
  );
}
