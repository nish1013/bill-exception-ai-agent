import { test as base, expect, type Browser, type Locator, type Page } from "@playwright/test";

export interface DemoUser {
  button: string;
  tenantName: string;
  role: string;
}

export const C1: DemoUser = {
  button: "C1, clerk, Acme Foods",
  tenantName: "Acme Foods",
  role: "clerk",
};
export const A1: DemoUser = {
  button: "A1, approver, Acme Foods",
  tenantName: "Acme Foods",
  role: "approver",
};
export const A2: DemoUser = {
  button: "A2, approver, Acme Foods",
  tenantName: "Acme Foods",
  role: "approver",
};
export const C9: DemoUser = {
  button: "C9, clerk, Beta Bakery",
  tenantName: "Beta Bakery",
  role: "clerk",
};

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
  await page.getByRole("button", { name: user.button }).click();
  await expect(page.getByLabel("Signed in as")).toHaveText(`${user.tenantName} · ${user.role}`);
  return page;
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
