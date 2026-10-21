import type { ConsoleEvent } from "../events/consoleEvent";

export interface JobRow {
  id: string;
  status: string;
  billCount: number;
  okCount: number;
  failedCount: number;
  seq: number;
  percent: number;
}

const DONE_STATUSES = new Set(["completed", "failed"]);

export function isDone(job: JobRow): boolean {
  return DONE_STATUSES.has(job.status);
}

// The row is the truth (D18). A shown event that is newer than the row read still counts.
export function mergeRow<T extends JobRow>(shown: T, read: T): T {
  return isDone(read) || read.seq >= shown.seq ? read : shown;
}

// An event with a seq at or below the last one shown changes nothing (D19).
export function applyEvent<T extends JobRow>(job: T, event: ConsoleEvent): T {
  if (event.jobId !== job.id || isDone(job)) {
    return job;
  }
  switch (event.type) {
    case "BillCheckProgress":
      if (event.seq <= job.seq) {
        return job;
      }
      return { ...job, status: "running", seq: event.seq, percent: event.percent };
    case "BillCheckCompleted":
      if (event.seq < job.seq) {
        return job;
      }
      return {
        ...job,
        status: event.status,
        seq: event.seq,
        percent: 100,
        okCount: job.billCount - event.failedCount,
        failedCount: event.failedCount,
      };
  }
}
