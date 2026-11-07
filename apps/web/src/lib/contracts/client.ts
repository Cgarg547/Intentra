import { ApiError } from "@/lib/auth/client";
import type { IntentContract } from "./types";

function apiError(response: Response, payload: unknown, fallback: string): ApiError {
  const code = response.headers.get("X-Intentra-Error-Code")
    ?? (typeof payload === "object" && payload !== null && "code" in payload
      && typeof payload.code === "string" ? payload.code : null);
  const detail = typeof payload === "object" && payload !== null && "detail" in payload
    && typeof payload.detail === "string" ? payload.detail : fallback;
  const message = response.status === 401
    ? code === "SESSION_INVALID" ? "Your session has expired. Please sign in."
      : code === "AUTHENTICATION_REQUIRED" ? "Sign in to view contracts."
        : "The API is unavailable or protected by deployment access controls."
    : detail;
  return new ApiError(response.status, message, code);
}

export type ContractListResponse = {
  items: IntentContract[];
  total: number;
  limit: number;
  offset: number;
};

export async function listContracts(
  limit = 100,
  offset = 0,
): Promise<ContractListResponse> {
  const response = await fetch(
    `/api/contracts?limit=${limit}&offset=${offset}`,
    {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
    },
  );

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw apiError(response, payload, `Unable to load contracts (${response.status}).`);

  return payload as ContractListResponse;
}

async function mutateContract<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw apiError(response, payload, `Request failed (${response.status}).`);
  return payload as T;
}

export function createContract(input: { merchant_id: string; maximum_amount: string; currency: string }) {
  return mutateContract<IntentContract>("/api/contracts", input);
}

export function approveContract(id: string, expected_version: number) {
  return mutateContract<IntentContract>(`/api/contracts/${id}/approve`, { expected_version });
}

export function revokeContract(id: string, expected_version: number) {
  return mutateContract<IntentContract>(`/api/contracts/${id}/revoke`, { expected_version });
}
