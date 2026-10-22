import { randomUUID } from "node:crypto";

import { expect } from "@playwright/test";

import { createTenants, setStubMode } from "./compose";
import {
  approverOf,
  clerkOf,
  dataGrid,
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

// A new tenant for each run: the proposal quota and the stub mode belong to the tenant.
const TENANT: Tenant = { id: randomUUID(), name: `E2E full path ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);
const A1 = approverOf(TENANT);

test("full path: a duplicate bill goes in, A1 approves the fix, accounting holds it once", async ({
  signIn,
}) => {
  createTenants([TENANT]);
  setStubMode(TENANT, "ok");
  const first: BillEntry = {
    supplierName: runSupplier("Full Path Foods"),
    invoiceNumber: "INV-001",
    amount: "120000",
    issueDate: "2026-10-01",
    vatAmount: "20000",
  };
  const second: BillEntry = { ...first, invoiceNumber: "inv 001" };

  const clerk = await signIn(C1);
  await ingestBill(clerk, first);
  await ingestBill(clerk, second);
  await startCheckOf(clerk, [first, second]);
  await clerk.getByRole("link", { name: "Open inbox" }).click();
  const exception = exceptionRows(clerk, first.supplierName);
  await expect(exception).toHaveCount(1);
  await expect(exception.getByRole("gridcell", { name: "duplicate", exact: true })).toBeVisible();
  await selectRow(exception);
  await clerk.getByRole("button", { name: "Request proposal" }).click();
  await expect(clerk.getByText("pending", { exact: true })).toBeVisible();
  const proposal = new URL(clerk.url()).pathname;

  const approver = await signIn(A1);
  await approver.goto(proposal);
  await approver.getByRole("button", { name: "Approve" }).click();
  await expect(approver.getByRole("status").filter({ hasText: "Approved by a1" })).toBeVisible();
  await expect(approver.getByText("synced", { exact: true }).first()).toBeVisible();
  const actions = approver.getByRole("table", { name: "Draft actions" });
  const syncKey = await actions.getByRole("row").nth(1).getByRole("cell").last().innerText();

  await approver.getByRole("tab", { name: "Inbox" }).click();
  await showStatus(approver, "resolved");
  await expect(exceptionRows(approver, first.supplierName)).toContainText("resolved");

  await approver.getByRole("tab", { name: "Accounting (stub)" }).click();
  const ledger = dataGrid(approver, "Ledger")
    .getByRole("row")
    .filter({ hasText: first.supplierName });
  await expect(ledger).toHaveCount(1);
  await expect(ledger).toContainText(syncKey);
});
