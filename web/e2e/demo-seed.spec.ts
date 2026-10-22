import { expect, type Page } from "@playwright/test";

import { C1, C9, exceptionRows, showStatus, test } from "./demo";

interface SeededException {
  supplierName: string;
  invoiceNumber: string;
  rule: string;
}

// make test-all seeds the demo tenants before the specs run, as make demo does (D55).
const ACME_EXCEPTIONS: SeededException[] = [
  { supplierName: "Fresh Farms Ltd", invoiceNumber: "inv 001", rule: "duplicate" },
  { supplierName: "Fresh Farms Ltd", invoiceNumber: "INV-002", rule: "possible_duplicate" },
  { supplierName: "Northern Packaging Ltd", invoiceNumber: "NP-7001", rule: "po_mismatch" },
  { supplierName: "City Cleaning BV", invoiceNumber: "CC-300", rule: "missing_vat" },
  { supplierName: "Riverside Logistics", invoiceNumber: "RL-88", rule: "missing_receipt" },
];
const BETA_EXCEPTIONS: SeededException[] = [
  { supplierName: "Mill Lane Flour Ltd", invoiceNumber: "ML 500", rule: "duplicate" },
  { supplierName: "Dairy Direct Ltd", invoiceNumber: "DD-41", rule: "missing_receipt" },
];

async function openInbox(page: Page): Promise<void> {
  await page.getByRole("tab", { name: "Inbox" }).click();
  // A demo user can change a status. The rows stay, so the spec reads all of them.
  await showStatus(page, "All");
}

async function expectEachOnce(page: Page, expected: SeededException[]): Promise<void> {
  for (const { supplierName, invoiceNumber, rule } of expected) {
    const rows = exceptionRows(page, supplierName).filter({
      has: page.getByRole("gridcell", { name: invoiceNumber, exact: true }),
    });
    await expect(rows).toHaveCount(1);
    await expect(rows.getByRole("gridcell", { name: rule, exact: true })).toBeVisible();
  }
  for (const supplierName of new Set(expected.map((exception) => exception.supplierName))) {
    const count = expected.filter((exception) => exception.supplierName === supplierName).length;
    await expect(exceptionRows(page, supplierName)).toHaveCount(count);
  }
}

async function expectNone(page: Page, other: SeededException[]): Promise<void> {
  for (const supplierName of new Set(other.map((exception) => exception.supplierName))) {
    await expect(exceptionRows(page, supplierName)).toHaveCount(0);
  }
}

test("d55: the T1 demo inbox shows one exception of each rule, and no T2 row", async ({
  signIn,
}) => {
  const page = await signIn(C1);
  await openInbox(page);

  await expectEachOnce(page, ACME_EXCEPTIONS);
  await expectNone(page, BETA_EXCEPTIONS);
});

test("d55 i1: the T2 demo inbox shows its own set only", async ({ signIn }) => {
  const page = await signIn(C9);
  await openInbox(page);

  await expectEachOnce(page, BETA_EXCEPTIONS);
  await expectNone(page, ACME_EXCEPTIONS);
});
