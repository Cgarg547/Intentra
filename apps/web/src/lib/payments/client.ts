export type PaymentAttempt = {
  attempt_id: string;
  reservation_id: string;
  contract_id: string;
  provider_order_id: string | null;
  capture_id: string | null;
  attempt_state: string;
  reservation_state: string;
  approval_state: string | null;
  approval_expires_at?: string | null;
  approval_consumed_at?: string | null;
  merchant_id: string;
  amount: string;
  currency: string;
  created_at: string;
  updated_at: string;
  approval_verified_at?: string | null;
  events?: { event_type: string; event_correlation_id: string; event_data: Record<string, unknown>; created_at: string }[];
};

export type PaymentReservation = {
  reservation_id: string;
  contract_id: string;
  merchant_id: string;
  amount: string;
  currency: string;
  status: string;
  reason: string;
  created_at: string;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init, credentials: "same-origin", cache: "no-store",
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
  });
  const payload: unknown = response.status === 204 ? undefined : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return payload as T;
}

export function listPayments() {
  return request<{ items: PaymentAttempt[] }>("/api/payments/history");
}

export function listReservations() {
  return request<{ items: PaymentReservation[] }>("/api/payments/reservations");
}

export function getPayment(attemptId: string) {
  return request<PaymentAttempt>(`/api/payments/attempts/${attemptId}`);
}

export function evaluatePayment(input: { contract_id: string; merchant_id: string; amount: string; currency: string }) {
  return request<{ evaluation_id: string; decision: string; reason: string; contract_version: number }>("/api/payments/evaluate", { method: "POST", body: JSON.stringify(input) });
}

export function reservePayment(input: { contract_id: string; idempotency_key: string; merchant_id: string; amount: string; currency: string }) {
  return request<{ reservation_id: string; status: string; reason: string; remaining_amount: string }>("/api/payments/reserve", { method: "POST", body: JSON.stringify(input) });
}

export function launchCheckout(reservationId: string) {
  return request<{ approval_url: string; attempt_id: string }>("/checkout/handoff", { method: "POST", body: JSON.stringify({ reservation_id: reservationId }) });
}

export function capturePayment(attemptId: string) {
  return request<{ attempt_id: string; state: string; capture_id: string | null; action: string }>(`/api/payments/attempts/${attemptId}/capture`, { method: "POST" });
}

export function reconcilePayment(attemptId: string) {
  return request<{ attempt_id: string; action: string; provider_status: string | null; capture_id: string | null }>(`/api/payments/attempts/${attemptId}/reconcile`, { method: "POST" });
}
