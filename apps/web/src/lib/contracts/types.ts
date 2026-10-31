export type ContractStatus = "DRAFT" | "APPROVED" | "REVOKED";

export type IntentContract = {
  id: string;
  owner_id: string | null;
  merchant_id: string;
  maximum_amount: string;
  currency: string;
  status: ContractStatus;
  version: number;
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
  revoked_at: string | null;
};

export type ContractSource = "demo" | "backend";
