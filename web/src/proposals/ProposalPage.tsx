import { useMutation, useQuery } from "@apollo/client";
import {
  Alert,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useParams } from "react-router";

import { isProposalEvent } from "../events/consoleEvent";
import { useConsoleEvents } from "../events/useConsoleEvents";
import { errorMessage } from "../graphql/errorMessage";
import {
  APPROVE_FIX_PROPOSAL,
  EXCEPTIONS,
  PROPOSAL,
  RETRY_SYNC,
  VIEWER,
} from "../graphql/operations";
import { ProposalStatusChip } from "./ProposalStatusChip";
import { RejectProposalDialog } from "./RejectProposalDialog";
import { canDecide, canRetrySync, failedReasonText, isDrafting, showsSync } from "./proposalStatus";

export function ProposalPage() {
  const { proposalId = "" } = useParams();
  const { data, error, refetch } = useQuery(PROPOSAL, {
    variables: { id: proposalId },
    fetchPolicy: "cache-and-network",
  });
  const { data: viewer } = useQuery(VIEWER);
  const [approveFixProposal, approval] = useMutation(APPROVE_FIX_PROPOSAL, {
    variables: { proposalId },
    // A stale approve changes the proposal with no data in the reply. The page reads it again.
    refetchQueries: [PROPOSAL, EXCEPTIONS],
    onError: () => undefined,
  });
  const [retrySync, retry] = useMutation(RETRY_SYNC, {
    variables: { proposalId },
    onError: () => undefined,
  });
  const [rejecting, setRejecting] = useState(false);
  // The row is the truth. The event and each socket open only start a read of it (D18).
  useConsoleEvents({
    onEvent: (event) => {
      if (isProposalEvent(event, proposalId)) {
        void refetch();
      }
    },
    onOpen: () => void refetch(),
  });

  if (error && !data) {
    return <Alert severity="error">{errorMessage(error)}</Alert>;
  }
  if (!data) {
    return <LinearProgress aria-label="Loading proposal" />;
  }
  const proposal = data.proposal;
  const isApprover = viewer?.viewer.role === "approver";
  const withSync = showsSync(proposal.status);

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="h5" component="h1" sx={{ flexGrow: 1 }}>
          Fix proposal
        </Typography>
        <Typography variant="body2">
          Request {proposal.quotaSlot} of 50 today, by {proposal.requestedBy}
        </Typography>
        <ProposalStatusChip status={proposal.status} />
      </Stack>
      {isDrafting(proposal.status) && (
        <Alert severity="info" role="status">
          The agent is drafting the plan.
        </Alert>
      )}
      {proposal.failedReason && (
        <Alert severity="error" role="status">
          The draft failed: {failedReasonText(proposal.failedReason)}
        </Alert>
      )}
      {proposal.approvedBy && (
        <Alert severity="success" role="status">
          Approved by {proposal.approvedBy}
        </Alert>
      )}
      {proposal.rejectReason && (
        <Alert severity="info" role="status">
          Rejected: {proposal.rejectReason}
        </Alert>
      )}
      {proposal.status === "stale" && (
        <Alert severity="warning" role="status">
          An exception of this proposal has changed. Request a new proposal.
        </Alert>
      )}
      {proposal.status === "syncing" && (
        <Alert severity="info" role="status">
          The actions are on their way to accounting.
        </Alert>
      )}
      {proposal.status === "sync_failed" && (
        <Alert severity="error" role="status">
          Accounting did not take the actions after 5 attempts.
        </Alert>
      )}
      {approval.error && <Alert severity="error">{errorMessage(approval.error)}</Alert>}
      {retry.error && <Alert severity="error">{errorMessage(retry.error)}</Alert>}
      {isApprover && canRetrySync(proposal.status) && (
        <Stack direction="row" justifyContent="flex-end">
          <Button variant="contained" disabled={retry.loading} onClick={() => void retrySync()}>
            Retry sync
          </Button>
        </Stack>
      )}
      {isApprover && canDecide(proposal.status) && (
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button variant="outlined" onClick={() => setRejecting(true)}>
            Reject
          </Button>
          <Button
            variant="contained"
            disabled={approval.loading}
            onClick={() => void approveFixProposal()}
          >
            Approve
          </Button>
        </Stack>
      )}
      <RejectProposalDialog
        proposalId={proposal.id}
        open={rejecting}
        onClose={() => setRejecting(false)}
      />
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="h6" component="h2">
          Exceptions
        </Typography>
        <List dense aria-label="Proposal exceptions">
          {proposal.exceptions.map((exception) => (
            <ListItem key={exception.id}>
              <ListItemText primary={exception.rule} secondary={exception.invoiceNumber} />
            </ListItem>
          ))}
        </List>
      </Paper>
      <Paper variant="outlined">
        <Table size="small" aria-label="Draft actions">
          <TableHead>
            <TableRow>
              <TableCell>Action</TableCell>
              <TableCell>Supplier</TableCell>
              <TableCell>Invoice number</TableCell>
              <TableCell>PO number</TableCell>
              {withSync && <TableCell>Sync</TableCell>}
              {withSync && <TableCell>Sync key</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {proposal.actions.map((action) => (
              <TableRow key={action.syncKey}>
                <TableCell>{action.kind}</TableCell>
                <TableCell>{action.supplierName}</TableCell>
                <TableCell>{action.invoiceNumber}</TableCell>
                <TableCell>{action.poNumber ?? ""}</TableCell>
                {withSync && <TableCell>{action.status}</TableCell>}
                {withSync && (
                  <TableCell sx={{ fontFamily: "monospace" }}>{action.syncKey}</TableCell>
                )}
              </TableRow>
            ))}
            {proposal.actions.length === 0 && (
              <TableRow>
                <TableCell colSpan={withSync ? 6 : 4}>No draft actions</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
