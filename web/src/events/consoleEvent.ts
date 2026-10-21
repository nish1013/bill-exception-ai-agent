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

const consoleEvent = z.discriminatedUnion("type", [billCheckProgress, billCheckCompleted]);

export type BillCheckProgress = z.infer<typeof billCheckProgress>;
export type BillCheckCompleted = z.infer<typeof billCheckCompleted>;
export type ConsoleEvent = z.infer<typeof consoleEvent>;

// An event type that this console does not know yet is skipped, not an error.
export function parseConsoleEvent(text: string): ConsoleEvent | null {
  try {
    const result = consoleEvent.safeParse(JSON.parse(text));
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}
