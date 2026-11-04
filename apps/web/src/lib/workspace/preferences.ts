export type WorkspacePreferences = { analyticsCurrency: string };
const defaultPreferences: WorkspacePreferences = { analyticsCurrency: "ALL" };
const key = (ownerId: string) => `intentra.preferences.v1.${ownerId}`;

export function readWorkspacePreferences(ownerId: string): WorkspacePreferences {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key(ownerId)) ?? "null");
    if (typeof value === "object" && value !== null && "analyticsCurrency" in value
      && typeof value.analyticsCurrency === "string"
      && ["ALL", "USD", "CAD", "EUR", "GBP", "AUD", "JPY"].includes(value.analyticsCurrency)) {
      return { analyticsCurrency: value.analyticsCurrency };
    }
  } catch { /* Corrupt browser preference falls back safely. */ }
  return defaultPreferences;
}

export function saveWorkspacePreferences(ownerId: string, value: WorkspacePreferences) {
  localStorage.setItem(key(ownerId), JSON.stringify(value));
}
