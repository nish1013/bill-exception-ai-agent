import { randomUUID } from "node:crypto";

import { expect } from "@playwright/test";

import { createTenants } from "./compose";
import { clerkOf, ingestBill, runSupplier, startCheckOf, test, type BillEntry } from "./demo";
import type { Tenant } from "./tenants";

// A new tenant for each run, so the report holds only the bills of this run.
const TENANT: Tenant = { id: randomUUID(), name: `E2E report ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);

test.beforeAll(() => {
  createTenants([TENANT]);
});

// No VAT and no receipt: two open exceptions on one bill.
const GBP_BILL: BillEntry = {
  supplierName: runSupplier("Report Gbp Co"),
  invoiceNumber: "INV-171",
  amount: "120000",
  issueDate: "2026-10-01",
  hasReceipt: false,
};
const EUR_BILL: BillEntry = {
  supplierName: runSupplier("Report Eur Co"),
  invoiceNumber: "INV-172",
  amount: "5000",
  currency: "EUR",
  vatAmount: "0",
  issueDate: "2026-10-01",
  hasReceipt: false,
};

test("us17: money at risk shows one GBP and one EUR total, each bill once", async ({ signIn }) => {
  const page = await signIn(C1);
  await ingestBill(page, GBP_BILL);
  await ingestBill(page, EUR_BILL);
  await startCheckOf(page, [GBP_BILL, EUR_BILL]);

  await page.getByRole("tab", { name: "Report" }).click();

  await expect(page.getByLabel("Open exceptions")).toHaveText("Open exceptions: 3");
  const totals = page.getByRole("table", { name: "Money at risk" }).getByRole("row");
  await expect(totals).toHaveCount(3);
  await expect(totals.nth(1)).toHaveText(/EUR\s*€50\.00/);
  await expect(totals.nth(2)).toHaveText(/GBP\s*£1,200\.00/);
});
