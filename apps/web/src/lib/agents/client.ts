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
  provider_mode: "SIMULATED" | "LLM" | "OPENAI" | "OLLAMA";
  version: number;
  created_at: string;
  updated_at: string;
  payment_preparation: { reservation_id: string; attempt_id: string; contract_version: number; created_at: string; status: string } | null;
  events?: { event_type: string; actor_id: string | null; event_data: Record<string, unknown>; created_at: string }[];
};

export class AgentApiError extends Error {
  constructor(message: string, readonly status: number, readonly correlationId: string | null = null) {
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
    const code = response.headers.get("X-Intentra-Error-Code")
      ?? (typeof payload === "object" && payload !== null && "code" in payload && typeof payload.code === "string" ? payload.code : null);
    const message = response.status === 401
      ? code === "SESSION_INVALID" ? "Your session has expired. Sign in to continue."
        : code === "AUTHENTICATION_REQUIRED" ? "Sign in to view proposal history."
          : "The API is unavailable or protected by deployment access controls."
      : response.status === 403 ? "This request was blocked. Open INTENTRA on the same address where you signed in."
      : response.status === 422 ? "Check your request and contract selection, then submit again."
      : response.status === 429 ? "Too many requests. Wait a few minutes before starting a new proposal."
      : detail;
    throw new AgentApiError(message, response.status,
      response.headers.get("X-Correlation-ID") ?? response.headers.get("X-Intentra-Correlation-ID"));
  }
  return payload as T;
}

// A successful HTTP response still needs the actual snake_case API contract.
// Never treat an absent identifier or an HTML proxy response as a saved result.
function proposalPayload(payload: unknown): AgentProposal {
  const item = payload as Partial<AgentProposal> | null;
  const nullableText = (value: unknown) => value === null || typeof value === "string";
  if (!item || typeof item !== "object"
    || typeof item.proposal_id !== "string" || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(item.proposal_id)
    || typeof item.status !== "string" || typeof item.provider_mode !== "string"
    || typeof item.created_at !== "string" || typeof item.request !== "string"
    || !["DRAFT", "NEEDS_INFORMATION", "READY_FOR_REVIEW", "REJECTED", "CONFIRMED"].includes(item.status)
    || !["SIMULATED", "LLM", "OPENAI", "OLLAMA"].includes(item.provider_mode)
    || (item.policy_decision !== null && !["ALLOW", "DENY", "NEEDS_INFORMATION"].includes(item.policy_decision ?? ""))
    || !nullableText(item.requested_purpose) || !nullableText(item.merchant_id)
    || !nullableText(item.proposed_amount) || !nullableText(item.currency)
    || !nullableText(item.contract_id) || !nullableText(item.policy_reason)
    || (item.payment_preparation !== null && (!item.payment_preparation
      || typeof item.payment_preparation.reservation_id !== "string"
      || typeof item.payment_preparation.status !== "string"))
    || typeof item.explanation !== "string" || !Array.isArray(item.missing_information)
    || !item.missing_information.every((value) => typeof value === "string")) {
    throw new AgentApiError("The response could not be verified. Refresh history before submitting again; a proposal may already exist.", 200);
  }
  return item as AgentProposal;
}

export async function listAgentProposals() {
  const payload = await request<{ items: unknown[] }>("/api/agents/proposals");
  if (!payload || !Array.isArray(payload.items)) throw new AgentApiError("Proposal history could not be verified.", 200);
  return payload.items.map(proposalPayload);
}

export async function createAgentProposal(requestText: string, contractId: string | null, idempotencyKey: string, signal?: AbortSignal) {
  return proposalPayload(await request<unknown>("/api/agents/proposals", {
    method: "POST", headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ request: requestText, contract_id: contractId }), signal,
  }));
}

export async function getAgentProposal(id: string, signal?: AbortSignal) {
  return proposalPayload(await request<unknown>(`/api/agents/proposals/${encodeURIComponent(id)}`, { signal }));
}

export function evaluateAgentProposal(id: string) {
  return request<unknown>(`/api/agents/proposals/${encodeURIComponent(id)}/evaluate`, { method: "POST" }).then(proposalPayload);
}

export function confirmAgentProposal(id: string) {
  return request<unknown>(`/api/agents/proposals/${encodeURIComponent(id)}/confirm`, { method: "POST" }).then(proposalPayload);
}

export function rejectAgentProposal(id: string, reason?: string) {
  return request<unknown>(`/api/agents/proposals/${encodeURIComponent(id)}/reject`, { method: "POST", body: JSON.stringify({ reason }) }).then(proposalPayload);
}

export function prepareAgentProposalPayment(id: string) {
  return request<unknown>(`/api/agents/proposals/${encodeURIComponent(id)}/prepare-payment`, { method: "POST" }).then(proposalPayload);
}
