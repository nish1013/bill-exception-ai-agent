import type { ConsoleEvent } from "../events/consoleEvent";
import { applyEvent, mergeRow, type JobRow } from "./jobBoard";

const J1 = "j1";

function row(changes: Partial<JobRow> = {}): JobRow {
  return {
    id: J1,
    status: "running",
    billCount: 10,
    okCount: 5,
    failedCount: 0,
    seq: 5,
    percent: 50,
    ...changes,
  };
}

function progress(seq: number, percent: number, jobId = J1): ConsoleEvent {
  return { type: "BillCheckProgress", jobId, seq, percent };
}

function completed(seq: number, failedCount = 0): ConsoleEvent {
  return { type: "BillCheckCompleted", jobId: J1, seq, status: "completed", failedCount };
}

function run(job: JobRow, ...events: ConsoleEvent[]): JobRow {
  return events.reduce(applyEvent, job);
}

describe("job board", () => {
  it("us7: seq 3, 40 % moves the board to 40 %", () => {
    const job = run(row({ status: "queued", seq: 0, percent: 0 }), progress(3, 40));

    expect(job).toMatchObject({ status: "running", seq: 3, percent: 40 });
  });

  it("d19: seq 4, 50 % after seq 5, 60 % leaves 60 %", () => {
    const job = run(row({ seq: 0, percent: 0 }), progress(5, 60), progress(4, 50));

    expect(job).toMatchObject({ seq: 5, percent: 60 });
  });

  it("d19: a repeat of the shown seq changes nothing", () => {
    expect(run(row(), progress(5, 99)).percent).toBe(50);
  });

  it("us7: completed shows the final status and failed count", () => {
    const job = run(row(), progress(10, 100), completed(10, 2));

    expect(job).toMatchObject({ status: "completed", okCount: 8, failedCount: 2, percent: 100 });
  });

  it("us7: a progress event after completed changes nothing", () => {
    expect(run(row(), completed(10), progress(11, 100)).status).toBe("completed");
  });

  it("us7: an event of another job changes nothing", () => {
    expect(run(row(), progress(9, 90, "j2"))).toEqual(row());
  });

  it("d18: a completed row read wins over a running board", () => {
    const read = row({ status: "completed", okCount: 10, seq: 10, percent: 100 });

    expect(mergeRow(run(row(), progress(7, 70)), read)).toEqual(read);
  });

  it("d18: a row read older than the shown event keeps the event", () => {
    const shown = run(row(), progress(7, 70));

    expect(mergeRow(shown, row({ seq: 6, percent: 60 }))).toEqual(shown);
  });
});
