import { expect } from "@playwright/test";

import { A1, A2, C1, C9, billRow, clerkOf, ingestBill, runSupplier, dataGrid, test } from "./demo";
import { SPEC_TENANTS } from "./tenants";

const { home, other } = SPEC_TENANTS.auth;

for (const user of [C1, A1, A2, C9]) {
  test(`us1: ${user.button} signs in and sees the tenant and role`, async ({ signIn }) => {
    const page = await signIn(user);

    await expect(page.getByRole("heading", { name: "Bills" })).toBeVisible();
  });
}

test("i1: a T2 user sees no T1 bill", async ({ signIn }) => {
  const bill = {
    supplierName: runSupplier("Isolation Co"),
    invoiceNumber: "INV-T1",
    amount: "5000",
    issueDate: "2026-10-01",
  };
  const c1 = await signIn(clerkOf(home));
  await ingestBill(c1, bill);

  const c9 = await signIn(clerkOf(other, "c9"));

  await expect(dataGrid(c9, "Bills")).toBeVisible();
  await expect(c9.getByText(bill.supplierName)).toHaveCount(0);
  await expect(billRow(c9, bill)).toHaveCount(0);
});
