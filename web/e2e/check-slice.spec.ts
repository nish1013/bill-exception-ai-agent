import { expect } from "@playwright/test";

import { C1, C9, fillBill, selectBill, ingestBill, runSupplier, dataGrid, test } from "./demo";

test("us4 us5 us8: two bills INV-001 and inv 001 give one duplicate", async ({ signIn }) => {
  const supplierName = runSupplier("Slice Foods");
  const first = {
    supplierName,
    invoiceNumber: "INV-001",
    amount: "120000",
    issueDate: "2026-10-01",
    vatAmount: "20000",
  };
  const second = { ...first, invoiceNumber: "inv 001" };
  const page = await signIn(C1);

  await ingestBill(page, first);
  await ingestBill(page, second);
  await selectBill(page, first);
  await selectBill(page, second);
  await page.getByRole("button", { name: "Start check" }).click();

  await expect(page.getByRole("status")).toHaveText(/Check completed: 2 of 2 bills checked/);
  await page.getByRole("link", { name: "Open inbox" }).click();

  const rows = dataGrid(page, "Exceptions").getByRole("row").filter({
    hasText: supplierName,
  });
  await expect(rows).toHaveCount(1);
  await expect(rows.getByRole("gridcell", { name: "duplicate", exact: true })).toBeVisible();
  await expect(rows.getByRole("gridcell", { name: "inv 001", exact: true })).toBeVisible();
  await expect(rows.getByRole("gridcell", { name: "open", exact: true })).toBeVisible();
});

test("us4: the form refuses 1200.50 with no API call", async ({ signIn }) => {
  const page = await signIn(C1);
  const ingestCalls: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/graphql") && request.postData()?.includes("IngestBill")) {
      ingestCalls.push(request.url());
    }
  });

  await fillBill(page, {
    supplierName: runSupplier("Float Co"),
    invoiceNumber: "INV-F1",
    amount: "1200.50",
    issueDate: "2026-10-01",
  });
  await page.getByRole("button", { name: "Save bill" }).click();

  await expect(page.getByText(/whole number of minor units/)).toBeVisible();
  expect(ingestCalls).toEqual([]);
});

test("i1: a T2 user sees an empty inbox", async ({ signIn }) => {
  const page = await signIn(C9);
  await page.getByRole("tab", { name: "Inbox" }).click();

  const grid = dataGrid(page, "Exceptions");
  await expect(grid.getByText("No exceptions")).toBeVisible();
  await expect(grid.getByRole("row").filter({ has: page.getByRole("gridcell") })).toHaveCount(0);
});
