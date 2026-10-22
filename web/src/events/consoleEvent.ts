import { z } from "zod";

const billCheckProgress = z.object({
  type: z.literal("BillCheckProgress"),
  jobId: z.string(),
  seq: z.number().int(),
  percent: z.number().int(),
});

const billCheckCompleted = z.object({
  type: z.literal("BillCheckCompleted"),
  jobId: z.string(),
  seq: z.number().int(),
  status: z.enum(["completed", "failed"]),
  failedCount: z.number().int(),
});

const fixProposalReady = z.object({
  type: z.literal("FixProposalReady"),
  proposalId: z.string(),
  status: z.enum(["pending", "failed"]),
});

const proposalSyncChanged = z.object({
  type: z.literal("ProposalSyncChanged"),
  proposalId: z.string(),
  status: z.enum(["syncing", "synced", "sync_failed"]),
});

const consoleEvent = z.discriminatedUnion("type", [
  billCheckProgress,
  billCheckCompleted,
  fixProposalReady,
  proposalSyncChanged,
]);

export type BillCheckProgress = z.infer<typeof billCheckProgress>;
export type BillCheckCompleted = z.infer<typeof billCheckCompleted>;
export type FixProposalReady = z.infer<typeof fixProposalReady>;
export type ProposalSyncChanged = z.infer<typeof proposalSyncChanged>;
export type CheckJobEvent = BillCheckProgress | BillCheckCompleted;
export type ConsoleEvent = z.infer<typeof consoleEvent>;

export function isCheckJobEvent(event: ConsoleEvent): event is CheckJobEvent {
  return event.type === "BillCheckProgress" || event.type === "BillCheckCompleted";
}

// Each proposal event only starts a read of the proposal row (D18).
export function isProposalEvent(event: ConsoleEvent, proposalId: string): boolean {
  return (
    (event.type === "FixProposalReady" || event.type === "ProposalSyncChanged") &&
    event.proposalId === proposalId
  );
}

// An event type that this console does not know yet is skipped, not an error.
export function parseConsoleEvent(text: string): ConsoleEvent | null {
  try {
    const result = consoleEvent.safeParse(JSON.parse(text));
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}
