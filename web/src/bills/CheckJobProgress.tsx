import { useApolloClient, useFragment } from "@apollo/client";
import { Alert, Button, LinearProgress, Stack, Typography } from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import { useConsoleEvents } from "../events/useConsoleEvents";
import { errorMessage } from "../graphql/errorMessage";
import { CHECK_JOB, CHECK_JOB_ROW, EXCEPTIONS } from "../graphql/operations";
import { applyJobEvent, mergeJobRead } from "./checkJobCache";
import { isDone } from "./jobBoard";

export interface CheckJobProgressProps {
  jobId: string;
}

export function CheckJobProgress({ jobId }: CheckJobProgressProps) {
  const client = useApolloClient();
  // startBillCheck put the job in the cache. Events and row reads update that one entry.
  const { data, complete } = useFragment({
    fragment: CHECK_JOB_ROW,
    from: { __typename: "CheckJob", id: jobId },
  });
  const [readError, setReadError] = useState<unknown>(null);
  const job = complete ? data : undefined;
  const done = job ? isDone(job) : false;

  // Each socket open reads the job row first, so a socket that was down misses nothing (D18).
  const readRow = useCallback(() => {
    client
      .query({ query: CHECK_JOB, variables: { id: jobId }, fetchPolicy: "no-cache" })
      .then(({ data: read }) => {
        setReadError(null);
        mergeJobRead(client.cache, read.checkJob);
      })
      .catch(setReadError);
  }, [client, jobId]);
  useConsoleEvents({ onEvent: (event) => applyJobEvent(client.cache, event), onOpen: readRow });

  useEffect(() => {
    if (done) {
      void client.refetchQueries({ include: [EXCEPTIONS] });
    }
  }, [done, client]);

  if (readError && !job) {
    return <Alert severity="error">{errorMessage(readError)}</Alert>;
  }
  if (!job) {
    return <LinearProgress aria-label="Loading check job" />;
  }
  return (
    <Alert
      severity={job.status === "failed" ? "error" : done ? "success" : "info"}
      action={
        done && (
          <Button component={Link} to="/inbox" color="inherit" size="small">
            Open inbox
          </Button>
        )
      }
    >
      <Stack spacing={1}>
        <Typography variant="body2" role="status">
          {done
            ? `Check ${job.status}: ${job.billCount} of ${job.billCount} bills checked, ${job.failedCount} failed.`
            : `Check ${job.status}: ${job.percent} %`}
        </Typography>
        {!done && (
          <LinearProgress variant="determinate" value={job.percent} aria-label="Check progress" />
        )}
        {readError !== null && (
          <Typography variant="caption">
            The job status may be out of date. {errorMessage(readError)}
          </Typography>
        )}
      </Stack>
    </Alert>
  );
}
