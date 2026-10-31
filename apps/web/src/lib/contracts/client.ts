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
