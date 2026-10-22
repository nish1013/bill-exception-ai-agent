import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

import { createTenants } from "./compose";
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

// A new tenant for each run: the proposal quota counts the tenant's requests of the whole UTC day.
const TENANT: Tenant = { id: randomUUID(), name: `E2E proposal ready ${Date.now().toString(36)}` };
const C1 = clerkOf(TENANT);
// Only bounds the wait when the event came before the socket joined. The page then reads the row.
const READY_EVENT_WAIT_MS = 10_000;

function readyEventSeen(page: Page): Promise<void> {
  return new Promise((resolve) => {
    page.on("websocket", (socket) => {
      socket.on("framereceived", ({ payload }) => {
        if (String(payload).includes("FixProposalReady")) {
          resolve();
        }
      });
    });
  });
}

function after(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// The first read of the proposal answers "drafting" and stays in flight until the ready event
// arrives. The read that the event starts must not join it.
async function holdFirstProposalRead(page: Page): Promise<void> {
  const ready = readyEventSeen(page);
  let held = false;
  await page.route("**/graphql", async (route) => {
    if (held || route.request().postDataJSON()?.operationName !== "Proposal") {
      await route.fallback();
      return;
    }
    held = true;
    const response = await route.fetch();
    await Promise.race([ready, after(READY_EVENT_WAIT_MS)]);
    await route.fulfill({ response });
  });
}

test("us11: the page shows pending when the ready event arrives during a read", async ({
  signIn,
}) => {
  createTenants([TENANT]);
  const bill: BillEntry = {
    supplierName: runSupplier("Ready Co"),
    invoiceNumber: "INV-601",
    amount: "60100",
    issueDate: "2026-10-01",
    vatAmount: "10000",
    hasReceipt: false,
  };
  const page = await signIn(C1);
  await ingestBill(page, bill);
  await startCheckOf(page, [bill]);
  await page.getByRole("link", { name: "Open inbox" }).click();
  await selectRow(exceptionRows(page, bill.supplierName));

  await holdFirstProposalRead(page);
  await page.getByRole("button", { name: "Request proposal" }).click();

  await expect(page.getByRole("heading", { name: "Fix proposal" })).toBeVisible();
  await expect(page.getByText("pending", { exact: true })).toBeVisible();
});
