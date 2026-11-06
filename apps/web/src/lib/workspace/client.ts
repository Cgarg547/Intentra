export type AuditItem = {
  event_id: string;
  correlation_id: string | null;
  entity_type: string;
  entity_id: string;
  related_ids: Record<string, string>;
  actor_id: string | null;
  actor_email: string | null;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
};

export type AuditPage = { items: AuditItem[]; limit: number; offset: number; next_offset: number | null };
export type MerchantItem = { internal_merchant_id: string; paypal_merchant_id: string; trust_source: string; provider_live_verified: boolean };
export type MerchantList = { items: MerchantItem[]; configured: boolean };
export type SecuritySummary = {
  authenticated: boolean; active_session_count: number; current_session_valid: boolean;
  contracts: Record<string, number>; trusted_merchant_count: number;
  payment_states: Record<string, number>; policy_decisions: Record<string, number>;
  unresolved_attempts: number; generated_at: string;
};
export type AnalyticsSummary = {
  payments: { count: number; successful_count: number; unknown_count: number };
  payment_states: { state: string; currency: string; count: number; amount: string }[];
  budget_by_contract: { contract_id: string; merchant_id: string; maximum_amount: string; currency: string; consumed_amount: string; remaining_amount: string; status: string }[];
  captured_by_merchant: { merchant_id: string; currency: string; amount: string; count: number }[];
  policy_decisions: Record<string, number>;
  proposals: Record<string, number>;
  daily_captured: { date: string; currency: string; amount: string; count: number }[];
  transactions: { attempt_id: string; reservation_id: string; contract_id: string; merchant_id: string; amount: string; currency: string; state: string; reservation_state: string; approval_state: string | null; created_at: string }[];
};
// The API currently returns all fields, but older deployments and partial
// status responses can omit optional provider diagnostics. Treat omissions as
// unknown in the UI rather than implying a healthy configuration.
export type SystemStatus = { api?: string; database?: string; paypal_sandbox?: string; trusted_merchants?: string; llm_mode?: string; llm_provider?: string; llm_runtime?: string; llm_model_status?: string; checked_at?: string };

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
      ? payload.detail : `Request failed (${response.status}).`;
    throw new Error(response.status === 401 ? "Your session has expired. Sign in again to view workspace data." : message);
  }
  return payload as T;
}

export function loadAudit(params: { entity_type?: string; event_type?: string; q?: string; offset?: number } = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") query.set(key, String(value));
  return request<AuditPage>(`/api/workspace/audit?${query.toString()}`);
}
export const loadMerchants = () => request<MerchantList>("/api/workspace/merchants");
export const loadSecurity = () => request<SecuritySummary>("/api/workspace/security");
export const loadAnalytics = () => request<AnalyticsSummary>("/api/workspace/analytics");
export const loadSystemStatus = () => request<SystemStatus>("/api/workspace/status");
