import { randomUUID } from "node:crypto";

import { expect } from "@playwright/test";

import { createTenants, fillQuotaSlots } from "./compose";
import {
  clerkOf,
  exceptionRows,
  ingestBill,
  runSupplier,
  selectRow,
  startCheckOf,
  test,
  type BillEntry,
} from "./demo";
import type { Tenant } from "./tenants";

// A new tenant for each run: the quota counts the tenant's requests of the whole UTC day.
const TENANT: Tenant = { id: randomUUID(), name: `E2E proposal ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);

test("us10 us11: request a proposal, see it pending, the 51st request shows the quota error", async ({
  signIn,
}) => {
  createTenants([TENANT]);
  fillQuotaSlots(TENANT, 49);
  const bill: BillEntry = {
    supplierName: runSupplier("Proposal Co"),
    invoiceNumber: "INV-501",
    amount: "50100",
    issueDate: "2026-10-01",
    vatAmount: "8350",
    hasReceipt: false,
  };
  const page = await signIn(C1);
  await ingestBill(page, bill);
  await startCheckOf(page, [bill]);
  await page.getByRole("link", { name: "Open inbox" }).click();

  const row = exceptionRows(page, bill.supplierName);
  await expect(row).toHaveCount(1);
  await selectRow(row);
  await page.getByRole("button", { name: "Request proposal" }).click();

  await expect(page.getByRole("heading", { name: "Fix proposal" })).toBeVisible();
  await expect(page.getByText("Request 50 of 50 today, by c1")).toBeVisible();
  await expect(page.getByText("pending", { exact: true })).toBeVisible();
  const actions = page.getByRole("table", { name: "Draft actions" });
  await expect(actions.getByRole("row").filter({ hasText: "INV-501" })).toContainText("hold");

  await page.getByRole("tab", { name: "Inbox" }).click();
  await selectRow(exceptionRows(page, bill.supplierName));
  await page.getByRole("button", { name: "Request proposal" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "50 of 50" })).toContainText(
    "Too many requests",
  );
  await expect(page.getByRole("heading", { name: "Exception inbox" })).toBeVisible();
});
