import { expect, type Page, type WebSocketRoute } from "@playwright/test";

import { clerkOf, ingestBill, runSupplier, selectBill, test, type BillEntry } from "./demo";
import { SPEC_TENANTS } from "./tenants";

const { home, other } = SPEC_TENANTS.liveProgress;
const C1 = clerkOf(home);
const C9 = clerkOf(other, "c9");
const EVENTS = /\/ws\/events\//;

function bills(supplierName: string, count: number): BillEntry[] {
  return Array.from({ length: count }, (_, i) => ({
    supplierName,
    invoiceNumber: `INV-${i + 1}`,
    amount: String(1000 * (i + 1)),
    issueDate: "2026-10-01",
    vatAmount: "100",
  }));
}

function countCheckJobReads(page: Page): () => number {
  let reads = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/graphql") && request.postData()?.includes("query CheckJob")) {
      reads += 1;
    }
  });
  return () => reads;
}

async function startCheck(page: Page, entries: BillEntry[]): Promise<string> {
  for (const bill of entries) {
    await selectBill(page, bill);
  }
  const started = page.waitForResponse(
    (r) =>
      r.url().endsWith("/graphql") && (r.request().postData() ?? "").includes("StartBillCheck"),
  );
  await page.getByRole("button", { name: "Start check" }).click();
  const body = await (await started).json();
  return body.data.startBillCheck.id as string;
}

function status(page: Page) {
  return page.getByRole("status");
}

test("us7: the board moves to completed with no reload and no polling", async ({ signIn }) => {
  const entries = bills(runSupplier("Live Co"), 4);
  const page = await signIn(C1);
  for (const bill of entries) {
    await ingestBill(page, bill);
  }
  const reads = countCheckJobReads(page);
  const frames: string[] = [];
  page.on("websocket", (socket) =>
    socket.on("framereceived", (f) => frames.push(String(f.payload))),
  );
  let navigations = 0;
  page.on("framenavigated", () => (navigations += 1));

  const jobId = await startCheck(page, entries);

  await expect(status(page)).toHaveText("Check completed: 4 of 4 bills checked, 0 failed.");
  await page.waitForTimeout(3000);
  expect(navigations).toBe(0);
  // One read on mount and one when the socket opens. No poll after that.
  expect(reads()).toBeLessThanOrEqual(2);
  expect(frames.some((f) => f.includes(jobId) && f.includes("BillCheckCompleted"))).toBe(true);
});

test("i1: a T2 socket gets no T1 event", async ({ signIn }) => {
  const entries = bills(runSupplier("Isolated Co"), 2);
  const c9 = await signIn(C9);
  const t2Frames = await openRawSocket(c9);
  const c1 = await signIn(C1);
  for (const bill of entries) {
    await ingestBill(c1, bill);
  }
  const t1Frames: string[] = [];
  c1.on("websocket", (socket) =>
    socket.on("framereceived", (f) => t1Frames.push(String(f.payload))),
  );

  const jobId = await startCheck(c1, entries);

  await expect(status(c1)).toHaveText(/Check completed/);
  await expect.poll(() => t1Frames.filter((f) => f.includes(jobId)).length).toBeGreaterThan(0);
  expect(await t2Frames()).toEqual([]);
});

test("d19: an event with a lower seq does not change the board", async ({ signIn }) => {
  const entries = bills(runSupplier("Seq Co"), 1);
  const page = await signIn(C1);
  await ingestBill(page, entries[0]!);
  let socket: WebSocketRoute | undefined;
  await page.routeWebSocket(EVENTS, (ws) => {
    socket = ws;
  });
  // The route applies to the sockets of a page that loads after it.
  await page.reload();
  await routeCheckJob(page, { status: "running", billCount: 10, okCount: 5, seq: 5, percent: 50 });

  const jobId = await startCheck(page, entries);
  await expect(status(page)).toHaveText("Check running: 50 %");
  await expect.poll(() => socket).toBeDefined();

  socket!.send(JSON.stringify({ type: "BillCheckProgress", jobId, seq: 6, percent: 60 }));
  await expect(status(page)).toHaveText("Check running: 60 %");
  socket!.send(JSON.stringify({ type: "BillCheckProgress", jobId, seq: 4, percent: 50 }));
  await page.waitForTimeout(500);

  await expect(status(page)).toHaveText("Check running: 60 %");
});

test("d18: after the socket was down, the board reads the job row first", async ({ signIn }) => {
  const entries = bills(runSupplier("Reconnect Co"), 2);
  const page = await signIn(C1);
  for (const bill of entries) {
    await ingestBill(page, bill);
  }
  const sockets: WebSocketRoute[] = [];
  await page.routeWebSocket(EVENTS, (ws) => {
    sockets.push(ws);
    // The first socket is down: it never passes a server event on. Later sockets are real.
    if (sockets.length > 1) {
      ws.connectToServer();
    }
  });
  await page.reload();
  const queued = { status: "queued", billCount: 2, okCount: 0, seq: 0, percent: 0 };
  const stale = await routeCheckJob(page, queued);

  const jobId = await startCheck(page, entries);
  await expect(status(page)).toHaveText("Check queued: 0 %");
  await expect.poll(() => jobStatus(page, jobId)).toBe("completed");
  await expect(status(page)).toHaveText("Check queued: 0 %");

  await stale.stop();
  await sockets[0]!.close();

  await expect(status(page)).toHaveText("Check completed: 2 of 2 bills checked, 0 failed.");
  expect(sockets.length).toBeGreaterThanOrEqual(2);
});

interface RowValues {
  status: string;
  billCount: number;
  okCount: number;
  seq: number;
  percent: number;
}

interface StaleRoute {
  stop: () => Promise<void>;
}

// Answers each CheckJob read with fixed values. Other GraphQL calls reach the API.
async function routeCheckJob(page: Page, values: RowValues): Promise<StaleRoute> {
  const handler = async (route: import("@playwright/test").Route) => {
    const body = route.request().postDataJSON() as { query: string; variables: { id: string } };
    if (!body.query.includes("query CheckJob")) {
      return route.fallback();
    }
    return route.fulfill({
      json: {
        data: {
          checkJob: {
            __typename: "CheckJob",
            id: body.variables.id,
            failedCount: 0,
            ...values,
          },
        },
      },
    });
  };
  await page.route("**/graphql", handler);
  return { stop: () => page.unroute("**/graphql", handler) };
}

async function accessToken(page: Page): Promise<string> {
  return page.evaluate(() => {
    const key = Object.keys(sessionStorage).find((k) => k.startsWith("oidc.user:"));
    return (JSON.parse(sessionStorage.getItem(key ?? "") ?? "{}") as { access_token: string })
      .access_token;
  });
}

async function jobStatus(page: Page, jobId: string): Promise<string> {
  const token = await accessToken(page);
  const response = await page.request.post("/graphql", {
    headers: { Authorization: `Bearer ${token}` },
    data: { query: "query($id: UUID!) { checkJob(id: $id) { status } }", variables: { id: jobId } },
  });
  return (await response.json()).data.checkJob.status as string;
}

// A socket that the page opens outside the board. It returns the frames that it got so far.
async function openRawSocket(page: Page): Promise<() => Promise<string[]>> {
  const token = await accessToken(page);
  await page.evaluate(async (t) => {
    const w = window as unknown as { rawFrames: string[] };
    w.rawFrames = [];
    const socket = new WebSocket(`ws://${location.host}/ws/events/?token=${t}`);
    socket.onmessage = (m) => w.rawFrames.push(String(m.data));
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = reject;
    });
  }, token);
  return () => page.evaluate(() => (window as unknown as { rawFrames: string[] }).rawFrames);
}
