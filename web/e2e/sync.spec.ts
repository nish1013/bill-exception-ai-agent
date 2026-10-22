import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

import { createTenants, setStubMode } from "./compose";
import {
  approverOf,
  clerkOf,
  dataGrid,
  exceptionRows,
  ingestBill,
  runSupplier,
  selectRow,
  startCheckOf,
  test,
  type BillEntry,
  type DemoUser,
} from "./demo";
import type { Tenant } from "./tenants";

// A new tenant for each run: the stub mode and the proposal quota belong to the tenant.
const TENANT: Tenant = { id: randomUUID(), name: `E2E sync ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);
const A1 = approverOf(TENANT);
// 5 attempts with waits of 1, 2, 4 and 8 s in make test-all (APPLY_FIRST_RETRY_SECONDS=1).
const SYNC_FAILED_TIMEOUT = 45_000;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  createTenants([TENANT]);
});

function billFor(label: string): BillEntry {
  return {
    supplierName: runSupplier(label),
    invoiceNumber: "INV-951",
    amount: "95100",
    issueDate: "2026-10-01",
    vatAmount: "15000",
    hasReceipt: false,
  };
}

// C1 requests a proposal for the bill's exception, A1 approves it. Returns A1's page.
async function approvedProposal(
  signIn: (user: DemoUser) => Promise<Page>,
  bill: BillEntry,
): Promise<Page> {
  const clerk = await signIn(C1);
  await ingestBill(clerk, bill);
  await startCheckOf(clerk, [bill]);
  await clerk.getByRole("link", { name: "Open inbox" }).click();
  await selectRow(exceptionRows(clerk, bill.supplierName));
  await clerk.getByRole("button", { name: "Request proposal" }).click();
  await expect(clerk.getByText("pending", { exact: true })).toBeVisible();

  const page = await signIn(A1);
  await page.goto(new URL(clerk.url()).pathname);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Approved by a1" })).toBeVisible();
  return page;
}

function syncKeyOf(page: Page): Promise<string> {
  const actions = page.getByRole("table", { name: "Draft actions" });
  return actions.getByRole("row").nth(1).getByRole("cell").last().innerText();
}

test("us14: mode ok, the proposal is synced and the stub holds the key once", async ({
  signIn,
}) => {
  setStubMode(TENANT, "ok");
  const bill = billFor("Sync Ok Co");
  const page = await approvedProposal(signIn, bill);

  await expect(page.getByText("synced", { exact: true }).first()).toBeVisible();
  const syncKey = await syncKeyOf(page);
  await page.getByRole("tab", { name: "Accounting (stub)" }).click();
  const rows = dataGrid(page, "Ledger").getByRole("row").filter({ hasText: bill.supplierName });
  await expect(rows).toHaveCount(1);
  await expect(rows).toContainText(syncKey);
  await expect(rows).toContainText("hold");
});

test("us14 us15: mode fail, sync_failed, then A1 retries and it is synced", async ({ signIn }) => {
  setStubMode(TENANT, "fail");
  const page = await approvedProposal(signIn, billFor("Sync Fail Co"));

  await expect(page.getByText("sync_failed", { exact: true })).toBeVisible({
    timeout: SYNC_FAILED_TIMEOUT,
  });
  await expect(page.getByRole("status").filter({ hasText: "after 5 attempts" })).toBeVisible();
  setStubMode(TENANT, "ok");
  await page.getByRole("button", { name: "Retry sync" }).click();

  await expect(page.getByText("synced", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry sync" })).toBeHidden();
});
