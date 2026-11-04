export type AgentProposal = {
  proposal_id: string;
  owner_id: string;
  request: string;
  requested_purpose: string | null;
  merchant_id: string | null;
  proposed_amount: string | null;
  currency: string | null;
  contract_id: string | null;
  contract_version: number | null;
  explanation: string;
  missing_information: string[];
  policy_decision: "ALLOW" | "DENY" | "NEEDS_INFORMATION" | null;
  policy_reason: string | null;
  status: "DRAFT" | "NEEDS_INFORMATION" | "READY_FOR_REVIEW" | "REJECTED" | "CONFIRMED";
  provider_mode: "SIMULATED" | "LLM";
  version: number;
  created_at: string;
  updated_at: string;
  payment_preparation: { reservation_id: string; attempt_id: string; contract_version: number; created_at: string; status: string } | null;
  events?: { event_type: string; actor_id: string | null; event_data: Record<string, unknown>; created_at: string }[];
};

export class AgentApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "AgentApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
      ? payload.detail : `Request failed (${response.status}).`;
    throw new AgentApiError(detail, response.status);
  }
  return payload as T;
}

export async function listAgentProposals() {
  return (await request<{ items: AgentProposal[] }>("/api/agents/proposals")).items;
}

export function createAgentProposal(requestText: string, contractId: string, idempotencyKey: string) {
  return request<AgentProposal>("/api/agents/proposals", {
    method: "POST", headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ request: requestText, contract_id: contractId }),
  });
}

export function evaluateAgentProposal(id: string) {
  return request<AgentProposal>(`/api/agents/proposals/${id}/evaluate`, { method: "POST" });
}

export function confirmAgentProposal(id: string) {
  return request<AgentProposal>(`/api/agents/proposals/${id}/confirm`, { method: "POST" });
}

export function rejectAgentProposal(id: string, reason?: string) {
  return request<AgentProposal>(`/api/agents/proposals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
}

export function prepareAgentProposalPayment(id: string) {
  return request<AgentProposal>(`/api/agents/proposals/${id}/prepare-payment`, { method: "POST" });
}
