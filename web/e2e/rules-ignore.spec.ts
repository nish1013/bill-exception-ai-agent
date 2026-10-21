import { expect, type Locator, type Page } from "@playwright/test";

import {
  clerkOf,
  exceptionRows,
  ingestBill,
  runSupplier,
  showStatus,
  startCheckOf,
  test,
  type BillEntry,
} from "./demo";
import { SPEC_TENANTS } from "./tenants";

const C1 = clerkOf(SPEC_TENANTS.rulesIgnore.home);

const RULES = ["duplicate", "possible_duplicate", "po_mismatch", "missing_vat", "missing_receipt"];

function cell(scope: Page | Locator, name: string): Locator {
  return scope.getByRole("gridcell", { name, exact: true });
}

test("us6 us9: one exception of each rule, ignore one with a reason", async ({ signIn }) => {
  const supplierName = runSupplier("Rules Co");
  const clean = { supplierName, issueDate: "2026-10-01", vatAmount: "20000" };
  const bills: BillEntry[] = [
    { ...clean, invoiceNumber: "INV-001", amount: "120000" },
    { ...clean, invoiceNumber: "inv 001", amount: "120000" },
    { ...clean, invoiceNumber: "INV-002", amount: "120000", issueDate: "2026-10-05" },
    { ...clean, invoiceNumber: "INV-003", amount: "3000", poNumber: `PO-${supplierName}` },
    { ...clean, invoiceNumber: "INV-004", amount: "4000", vatAmount: undefined },
    { ...clean, invoiceNumber: "INV-005", amount: "5000", hasReceipt: false },
  ];
  const page = await signIn(C1);
  for (const bill of bills) {
    await ingestBill(page, bill);
  }

  await startCheckOf(page, bills);
  await page.getByRole("link", { name: "Open inbox" }).click();

  const rows = exceptionRows(page, supplierName);
  await expect(rows).toHaveCount(RULES.length);
  for (const rule of RULES) {
    await expect(rows.filter({ has: cell(page, rule) })).toHaveCount(1);
  }

  const receiptRow = rows.filter({ has: cell(page, "missing_receipt") });
  await receiptRow.getByRole("button", { name: "Ignore" }).click();
  const form = page.getByRole("form", { name: "Ignore exception" });
  await form.getByRole("button", { name: "Ignore" }).click();
  await expect(form.getByText("Enter a reason.")).toBeVisible();
  await form.getByLabel(/Reason/).fill("Agreed with supplier");
  await form.getByRole("button", { name: "Ignore" }).click();
  await expect(form).toBeHidden();

  await expect(rows).toHaveCount(RULES.length - 1);
  await expect(rows.filter({ has: cell(page, "missing_receipt") })).toHaveCount(0);

  await showStatus(page, "ignored");
  const ignored = exceptionRows(page, supplierName);
  await expect(ignored).toHaveCount(1);
  await expect(cell(ignored, "missing_receipt")).toBeVisible();
  await expect(cell(ignored, "Agreed with supplier")).toBeVisible();
  await expect(cell(ignored, "c1")).toBeVisible();
});

test("i16: adding the missing PO resolves the po_mismatch by system", async ({ signIn }) => {
  const supplierName = runSupplier("PO Co");
  const poNumber = `PO-${supplierName}`;
  const bill: BillEntry = {
    supplierName,
    invoiceNumber: "INV-999",
    amount: "9900",
    issueDate: "2026-10-01",
    vatAmount: "1650",
    poNumber,
  };
  const page = await signIn(C1);
  await ingestBill(page, bill);
  await startCheckOf(page, [bill]);

  await page.getByRole("button", { name: "Add PO" }).click();
  const form = page.getByRole("form", { name: "Add purchase order" });
  await form.getByLabel(/Supplier/).click();
  await page.getByRole("option", { name: supplierName }).click();
  await form.getByLabel(/PO number/).fill(poNumber);
  await form.getByLabel(/^Amount/).fill(bill.amount);
  await form.getByRole("button", { name: "Save PO" }).click();
  await expect(form).toBeHidden();

  await page.getByRole("tab", { name: "Inbox" }).click();
  await expect(async () => {
    await page.reload();
    await showStatus(page, "resolved");
    const resolved = exceptionRows(page, supplierName);
    await expect(resolved).toHaveCount(1, { timeout: 1000 });
    await expect(cell(resolved, "po_mismatch")).toBeVisible({ timeout: 1000 });
    await expect(cell(resolved, "system")).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 30_000 });
});
