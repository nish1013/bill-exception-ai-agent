import { InMemoryCache } from "@apollo/client";

import { CHECK_JOB } from "../graphql/operations";
import { applyJobEvent, mergeJobRead } from "./checkJobCache";
import type { JobRow } from "./jobBoard";

const J1 = "11111111-1111-4111-8111-111111111111";

function row(seq: number, percent: number, status = "running"): JobRow {
  return { id: J1, status, billCount: 10, okCount: seq, failedCount: 0, seq, percent };
}

function cacheWith(job: JobRow): InMemoryCache {
  const cache = new InMemoryCache();
  cache.writeQuery({
    query: CHECK_JOB,
    variables: { id: J1 },
    data: { checkJob: { __typename: "CheckJob", ...job } },
  });
  return cache;
}

function shown(cache: InMemoryCache) {
  return cache.readQuery({ query: CHECK_JOB, variables: { id: J1 } })?.checkJob;
}

describe("check job in the Apollo cache", () => {
  it("d47: a progress event updates the cached job", () => {
    const cache = cacheWith(row(5, 50));

    applyJobEvent(cache, { type: "BillCheckProgress", jobId: J1, seq: 6, percent: 60 });

    expect(shown(cache)).toMatchObject({ status: "running", seq: 6, percent: 60 });
  });

  it("d19: a lower seq leaves the cached job", () => {
    const cache = cacheWith(row(6, 60));

    applyJobEvent(cache, { type: "BillCheckProgress", jobId: J1, seq: 4, percent: 40 });

    expect(shown(cache)).toMatchObject({ seq: 6, percent: 60 });
  });

  it("d18: an older row read keeps the newer event", () => {
    const cache = cacheWith(row(5, 50));
    applyJobEvent(cache, { type: "BillCheckProgress", jobId: J1, seq: 7, percent: 70 });

    mergeJobRead(cache, row(6, 60));

    expect(shown(cache)).toMatchObject({ seq: 7, percent: 70 });
  });

  it("d18: a completed row read replaces a running job", () => {
    const cache = cacheWith(row(5, 50));

    mergeJobRead(cache, row(10, 100, "completed"));

    expect(shown(cache)).toMatchObject({ status: "completed", seq: 10 });
  });

  it("us7: an event for a job that is not cached changes nothing", () => {
    const cache = cacheWith(row(5, 50));
    const other = "22222222-2222-4222-8222-222222222222";

    applyJobEvent(cache, { type: "BillCheckProgress", jobId: other, seq: 1, percent: 10 });

    expect(shown(cache)).toMatchObject({ seq: 5 });
  });
});
