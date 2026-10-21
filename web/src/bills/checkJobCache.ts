import type { ApolloCache } from "@apollo/client";

import type { ConsoleEvent } from "../events/consoleEvent";
import { CHECK_JOB_ROW } from "../graphql/operations";
import { applyEvent, mergeRow, type JobRow } from "./jobBoard";

// The console keeps one copy of each job: its Apollo cache entry (D47).

export function applyJobEvent(cache: ApolloCache<unknown>, event: ConsoleEvent): void {
  updateJob(cache, event.jobId, (shown) => shown && applyEvent(shown, event));
}

export function mergeJobRead(cache: ApolloCache<unknown>, read: JobRow): void {
  updateJob(cache, read.id, (shown) => (shown ? mergeRow(shown, read) : read));
}

function updateJob(
  cache: ApolloCache<unknown>,
  jobId: string,
  update: (shown: JobRow | null) => JobRow | null,
): void {
  const id = cache.identify({ __typename: "CheckJob", id: jobId });
  if (id) {
    cache.updateFragment({ id, fragment: CHECK_JOB_ROW }, (shown) => {
      const next = update(shown);
      return next && { ...next, __typename: "CheckJob" as const };
    });
  }
}
