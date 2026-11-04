import type { IntentContract } from "./types";

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

  if (response.status === 401) {
    throw new Error("Your session has expired. Please sign in.");
  }

  if (!response.ok) {
    throw new Error(`Unable to load contracts (${response.status}).`);
  }

  return (await response.json()) as ContractListResponse;
}

async function mutateContract<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
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
