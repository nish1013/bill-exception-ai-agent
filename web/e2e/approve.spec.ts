import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

import { createTenants } from "./compose";
import {
  approverOf,
  clerkOf,
  exceptionRows,
  ingestBill,
  runSupplier,
  selectRow,
  showStatus,
  startCheckOf,
  test,
  type BillEntry,
} from "./demo";
import type { Tenant } from "./tenants";

// A new tenant for each run: the proposal quota counts the tenant's requests of the whole UTC day.
const TENANT: Tenant = { id: randomUUID(), name: `E2E approve ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);
const A1 = approverOf(TENANT);
// The same person as A1, signed in with the clerk role.
const A1_AS_CLERK = clerkOf(TENANT, "a1");

test.beforeAll(() => {
  createTenants([TENANT]);
});

function billFor(label: string): BillEntry {
  return {
    supplierName: runSupplier(label),
    invoiceNumber: "INV-901",
    amount: "90100",
    issueDate: "2026-10-01",
    vatAmount: "15000",
    hasReceipt: false,
  };
}

// Ingests a bill with no receipt and requests a proposal for its exception. Returns its path.
async function requestProposal(page: Page, bill: BillEntry): Promise<string> {
  await ingestBill(page, bill);
  await startCheckOf(page, [bill]);
  await page.getByRole("link", { name: "Open inbox" }).click();
  await selectRow(exceptionRows(page, bill.supplierName));
  await page.getByRole("button", { name: "Request proposal" }).click();
  await expect(page.getByRole("heading", { name: "Fix proposal" })).toBeVisible();
  await expect(page.getByText("pending", { exact: true })).toBeVisible();
  return new URL(page.url()).pathname;
}

test("us12: C1 requests, A1 approves, the exception waits for the sync", async ({ signIn }) => {
  const bill = billFor("Approve Co");
  const proposal = await requestProposal(await signIn(C1), bill);

  const page = await signIn(A1);
  await page.goto(proposal);
  await page.getByRole("button", { name: "Approve" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Approved by a1" })).toBeVisible();
  await expect(page.getByText("approved", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeHidden();
  await page.getByRole("tab", { name: "Inbox" }).click();
  await showStatus(page, "pending_sync");
  await expect(exceptionRows(page, bill.supplierName)).toContainText("pending_sync");
});

test("us12: A1 cannot approve a proposal that A1 requested", async ({ signIn }) => {
  const proposal = await requestProposal(await signIn(A1_AS_CLERK), billFor("Four Eyes Co"));

  const page = await signIn(A1);
  await page.goto(proposal);
  await expect(page.getByText(/Request \d+ of 50 today, by a1/)).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();

  await expect(page.getByRole("alert")).toContainText(
    "an approver cannot approve a proposal they requested",
  );
  await page.reload();
  await expect(page.getByText("pending", { exact: true })).toBeVisible();
});

test("us13: A1 rejects with a reason, and the page shows it", async ({ signIn }) => {
  const proposal = await requestProposal(await signIn(C1), billFor("Reject Co"));

  const page = await signIn(A1);
  await page.goto(proposal);
  await page.getByRole("button", { name: "Reject" }).click();
  const form = page.getByRole("form", { name: "Reject proposal" });
  await form.getByRole("button", { name: "Reject" }).click();
  await expect(form.getByText("Enter a reason.")).toBeVisible();
  await form.getByLabel(/Reason/).fill("Wrong supplier");
  await form.getByRole("button", { name: "Reject" }).click();
  await expect(form).toBeHidden();

  await expect(
    page.getByRole("status").filter({ hasText: "Rejected: Wrong supplier" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("rejected", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Rejected: Wrong supplier" }),
  ).toBeVisible();
});
