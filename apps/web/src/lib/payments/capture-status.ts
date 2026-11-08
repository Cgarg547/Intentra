import type { PaymentAttempt } from "./client";

/** A capture is only displayed after the persisted terminal read model proves it. */
export function hasVerifiedCapture(payment: PaymentAttempt): boolean {
  return payment.attempt_state === "SUCCEEDED"
    && payment.reservation_state === "CAPTURED"
    && Boolean(payment.capture_id);
}

export function checkoutStatusMessage(result: string | null, payments: PaymentAttempt[]): string | null {
  if (result === "verified") {
    return payments.some(hasVerifiedCapture)
      ? "Payment capture was verified by INTENTRA."
      : "PayPal buyer approval was verified by INTENTRA. No payment was captured; review the attempt below and choose Capture when ready.";
  }
  if (result === "cancelled") return "Checkout was cancelled. The payment reservation remains available for review.";
  if (result === "cancel-review") return "Checkout could not be safely marked cancelled. Review the payment state before retrying.";
  if (result?.startsWith("verification")) return "PayPal returned to INTENTRA, but approval could not be verified. Review the payment before taking another action.";
  return null;
}
