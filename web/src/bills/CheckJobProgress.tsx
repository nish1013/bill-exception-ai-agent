import { useQuery } from "@apollo/client";
import { Alert, Button, LinearProgress, Stack, Typography } from "@mui/material";
import { useEffect } from "react";
import { Link } from "react-router";

import { errorMessage } from "../graphql/errorMessage";
import { CHECK_JOB, EXCEPTIONS } from "../graphql/operations";

export interface CheckJobProgressProps {
  jobId: string;
}

// The thin slice polls for the job status (D46).
const POLL_MS = 1000;
const FINAL_STATUSES = new Set(["completed", "failed"]);

export function CheckJobProgress({ jobId }: CheckJobProgressProps) {
  const { data, error, stopPolling, client } = useQuery(CHECK_JOB, {
    variables: { id: jobId },
    pollInterval: POLL_MS,
    fetchPolicy: "network-only",
    notifyOnNetworkStatusChange: false,
  });
  const job = data?.checkJob;
  const done = job ? FINAL_STATUSES.has(job.status) : false;

  useEffect(() => {
    if (done) {
      stopPolling();
      void client.refetchQueries({ include: [EXCEPTIONS] });
    }
  }, [done, stopPolling, client]);

  if (error) {
    return <Alert severity="error">{errorMessage(error)}</Alert>;
  }
  if (!job) {
    return <LinearProgress aria-label="Loading check job" />;
  }
  const checked = job.okCount + job.failedCount;
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
          Check {job.status}: {checked} of {job.billCount} bills checked, {job.failedCount} failed.
        </Typography>
        {!done && <LinearProgress variant="determinate" value={(100 * checked) / job.billCount} />}
      </Stack>
    </Alert>
  );
}
