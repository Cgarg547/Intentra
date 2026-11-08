import { expect, test, type Route } from "@playwright/test";
import type { AgentProposal } from "../../src/lib/agents/client";

const allowedId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const deniedId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function proposal(
  id: string,
  policy: "ALLOW" | "DENY",
): AgentProposal {
  return {
    proposal_id: id,
    owner_id: "synthetic-owner",
    request: "Buy office equipment for USD 20",
    requested_purpose: policy === "ALLOW"
      ? "Approved keyboard"
      : "Restricted equipment",
    merchant_id: "synthetic-merchant",
    proposed_amount: "20.00",
    currency: "USD",
    contract_id: null,
    contract_version: null,
    explanation: "Synthetic test proposal",
    missing_information: [],
    policy_decision: policy,
    policy_reason: policy === "ALLOW"
      ? "Within policy"
      : "Outside policy",
    status: "READY_FOR_REVIEW",
    provider_mode: "SIMULATED",
    version: 2,
    created_at: "2026-11-07T00:00:00Z",
    updated_at: "2026-11-07T00:00:00Z",
    payment_preparation: null,
    events: [],
  };
}

test("approval policy, rejection validation and payment separation", async ({
  page,
}) => {
  let items = [
    proposal(allowedId, "ALLOW"),
    proposal(deniedId, "DENY"),
  ];

  const writes: string[] = [];
  const pending: Route[] = [];

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (!url.pathname.startsWith("/api/")) {
      return route.continue();
    }

    const path = url.pathname;
    const method = request.method();

    if (path === "/api/auth/me") {
      return route.fulfill({
        json: {
          id: "synthetic-owner",
          email: "synthetic@example.com",
        },
      });
    }

    if (path === "/api/agents/proposals" && method === "GET") {
      return route.fulfill({
        json: { items },
      });
    }

    if (
      path === `/api/agents/proposals/${allowedId}/confirm` &&
      method === "POST"
    ) {
      writes.push(`${method} ${path}`);
      pending.push(route);
      return;
    }

    if (
      path === `/api/agents/proposals/${deniedId}/reject` &&
      method === "POST"
    ) {
      writes.push(`${method} ${path}`);
      const body = request.postDataJSON() as { reason?: string };

      expect(body.reason).toBe("Outside approved purchasing policy");

      items = items.map((item) =>
        item.proposal_id === deniedId
          ? { ...item, status: "REJECTED" }
          : item
      );

      return route.fulfill({
        json: items.find((item) => item.proposal_id === deniedId),
      });
    }

    if (method !== "GET") {
      writes.push(`${method} ${path}`);
    }

    return route.fulfill({
      status: 403,
      json: { detail: "Blocked synthetic API request" },
    });
  });

  try {
    await page.goto("/approvals");

    const allowed = page.getByRole("article").filter({
      hasText: "Approved keyboard",
    });

    const denied = page.getByRole("article").filter({
      hasText: "Restricted equipment",
    });

    await expect(
      allowed.getByRole("button", { name: "Confirm proposal" })
    ).toBeEnabled();

    await expect(
      denied.getByRole("button", { name: "Confirm proposal" })
    ).toBeDisabled();

    const reject = denied.getByRole("button", {
      name: "Reject proposal",
    });

    await expect(reject).toBeDisabled();

    await denied.getByPlaceholder(
      "Explain why this proposal should be rejected"
    ).fill("Outside approved purchasing policy");

    await expect(reject).toBeEnabled();
    await reject.click();

    await expect(
      page.getByText("Proposal rejected and recorded in its audit history.")
    ).toBeVisible();

    page.once("dialog", (dialog) => dialog.accept());

    await allowed.getByRole("button", {
      name: "Confirm proposal",
    }).click();

    await expect(
      allowed.getByRole("button", { name: "Saving…" })
    ).toBeDisabled();

    expect(writes).toEqual([
      `POST /api/agents/proposals/${deniedId}/reject`,
      `POST /api/agents/proposals/${allowedId}/confirm`,
    ]);

    expect(
      writes.filter((path) =>
        /prepare-payment|checkout|capture|reserve/.test(path)
      )
    ).toEqual([]);
  } finally {
    for (const route of pending) {
      await route.abort().catch(() => {});
    }
  }
});
