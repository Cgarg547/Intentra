import { expect, test } from "@playwright/test";
import { checkoutStatusMessage, hasVerifiedCapture } from "@/lib/payments/capture-status";
import type { PaymentAttempt } from "@/lib/payments/client";

function payment(overrides: Partial<PaymentAttempt> = {}): PaymentAttempt {
  return { attempt_id: "attempt", reservation_id: "reservation", contract_id: "contract", provider_order_id: "order", capture_id: null, attempt_state: "PENDING", reservation_state: "EXECUTION_PENDING", approval_state: "APPROVED", merchant_id: "merchant", amount: "25.00", currency: "USD", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), ...overrides };
}

test("only persisted successful captures count as captured", () => {
  expect(hasVerifiedCapture(payment())).toBe(false);
  expect(hasVerifiedCapture(payment({ attempt_state: "UNKNOWN", reservation_state: "OUTCOME_UNKNOWN", capture_id: "capture" }))).toBe(false);
  expect(hasVerifiedCapture(payment({ attempt_state: "SUCCEEDED", reservation_state: "CAPTURED" }))).toBe(false);
  expect(hasVerifiedCapture(payment({ attempt_state: "SUCCEEDED", reservation_state: "CAPTURED", capture_id: "capture" }))).toBe(true);
});

test("checkout notification uses persisted capture state", () => {
  expect(checkoutStatusMessage("verified", [payment()])).toContain("No payment was captured");
  expect(checkoutStatusMessage("verified", [payment({ attempt_state: "SUCCEEDED", reservation_state: "CAPTURED", capture_id: "capture" })])).toContain("capture was verified");
  expect(checkoutStatusMessage("verification-failed", [])).toContain("could not be verified");
});
