import { test as base, expect, type Browser, type Locator, type Page } from "@playwright/test";

import type { Tenant } from "./tenants";

export interface DemoUser {
  username: string;
  role: string;
  tenant: Tenant;
  // A demo user signs in with its own button. Other users sign in with their claims.
  button?: string;
}

const ACME: Tenant = { id: "11111111-1111-1111-1111-111111111111", name: "Acme Foods" };
const BETA: Tenant = { id: "22222222-2222-2222-2222-222222222222", name: "Beta Bakery" };

export const C1: DemoUser = {
  username: "c1",
  role: "clerk",
  tenant: ACME,
  button: "C1, clerk, Acme Foods",
};
export const A1: DemoUser = {
  username: "a1",
  role: "approver",
  tenant: ACME,
  button: "A1, approver, Acme Foods",
};
export const A2: DemoUser = {
  username: "a2",
  role: "approver",
  tenant: ACME,
  button: "A2, approver, Acme Foods",
};
export const C9: DemoUser = {
  username: "c9",
  role: "clerk",
  tenant: BETA,
  button: "C9, clerk, Beta Bakery",
};

export function clerkOf(tenant: Tenant, username = "c1"): DemoUser {
  return { username, role: "clerk", tenant };
}

export interface BillEntry {
  supplierName: string;
  invoiceNumber: string;
  amount: string;
  issueDate: string;
  vatAmount?: string;
  poNumber?: string;
  hasReceipt?: boolean;
}

// Each run uses its own supplier, so the rows of an earlier run on the same stack do not match.
export function runSupplier(label: string): string {
  return `${label} ${Date.now().toString(36)}`;
}

export interface DemoFixtures {
  signIn: (user: DemoUser) => Promise<Page>;
}

// Each user gets an own browser context, so two users can be signed in at the same time.
export const test = base.extend<DemoFixtures>({
  signIn: async ({ browser }, use) => {
    const pages: Page[] = [];
    await use(async (user) => {
      const page = await signedInPage(browser, user);
      pages.push(page);
      return page;
    });
    await Promise.all(pages.map((page) => page.context().close()));
  },
});

async function signedInPage(browser: Browser, user: DemoUser): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/bills");
  if (user.button) {
    await page.getByRole("button", { name: user.button }).click();
  } else {
    await signInWithClaims(page, user);
  }
  await expect(page.getByLabel("Signed in as")).toHaveText(`${user.tenant.name} · ${user.role}`);
  return page;
}

// The mock provider puts the posted claims in the token. The form of the first demo user is
// reused with the claims of this user.
async function signInWithClaims(page: Page, user: DemoUser): Promise<void> {
  const form = page.locator("form").first();
  const claims = JSON.stringify({ tenant_id: user.tenant.id, role: user.role });
  await form.locator('input[name="username"]').evaluate(setValue, user.username);
  await form.locator('input[name="claims"]').evaluate(setValue, claims);
  await form.getByRole("button").click();
}

function setValue(input: Element, value: string): void {
  (input as HTMLInputElement).value = value;
}

export async function fillBill(page: Page, bill: BillEntry): Promise<void> {
  await page.getByRole("button", { name: "Ingest bill" }).click();
  const form = page.getByRole("form", { name: "Ingest bill" });
  await form.getByLabel("Supplier name").fill(bill.supplierName);
  await form.getByLabel("Invoice number").fill(bill.invoiceNumber);
  await form.getByLabel(/^Amount/).fill(bill.amount);
  await form.getByLabel("Issue date").fill(bill.issueDate);
  if (bill.vatAmount !== undefined) {
    await form.getByLabel(/^VAT amount/).fill(bill.vatAmount);
  }
  if (bill.poNumber !== undefined) {
    await form.getByLabel("PO number").fill(bill.poNumber);
  }
  if (bill.hasReceipt ?? true) {
    await form.getByLabel("Receipt received").check();
  }
}

export async function ingestBill(page: Page, bill: BillEntry): Promise<void> {
  await fillBill(page, bill);
  await page.getByRole("button", { name: "Save bill" }).click();
  await expect(page.getByRole("form", { name: "Ingest bill" })).toBeHidden();
  await expect(billRow(page, bill)).toBeVisible();
}

// The DataGrid puts its label on the root element, not on the grid role.
export function dataGrid(page: Page, label: string): Locator {
  return page.getByLabel(label, { exact: true }).getByRole("grid");
}

export function billRow(page: Page, bill: BillEntry): Locator {
  return dataGrid(page, "Bills")
    .getByRole("row")
    .filter({ hasText: bill.supplierName })
    .filter({ has: page.getByRole("gridcell", { name: bill.invoiceNumber, exact: true }) });
}

// A click on a grid checkbox re-renders the row. The test asserts the state after the click.
export async function selectBill(page: Page, bill: BillEntry): Promise<void> {
  const checkbox = billRow(page, bill).getByRole("checkbox");
  await checkbox.click();
  await expect(checkbox).toBeChecked();
}

export async function startCheckOf(page: Page, bills: BillEntry[]): Promise<void> {
  for (const bill of bills) {
    await selectBill(page, bill);
  }
  await page.getByRole("button", { name: "Start check" }).click();
  const total = bills.length;
  await expect(page.getByRole("status")).toHaveText(
    new RegExp(`Check completed: ${total} of ${total} bills checked`),
  );
}

export function exceptionRows(page: Page, supplierName: string): Locator {
  return dataGrid(page, "Exceptions").getByRole("row").filter({ hasText: supplierName });
}

export async function showStatus(page: Page, status: string): Promise<void> {
  await page.getByRole("combobox", { name: "Status" }).click();
  await page.getByRole("option", { name: status, exact: true }).click();
}
