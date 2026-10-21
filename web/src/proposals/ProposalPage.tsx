import { useQuery } from "@apollo/client";
import {
  Alert,
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
import { useParams } from "react-router";

import { useConsoleEvents } from "../events/useConsoleEvents";
import { errorMessage } from "../graphql/errorMessage";
import { PROPOSAL } from "../graphql/operations";
import { ProposalStatusChip } from "./ProposalStatusChip";
import { failedReasonText, isDrafting } from "./proposalStatus";

export function ProposalPage() {
  const { proposalId = "" } = useParams();
  const { data, error, refetch } = useQuery(PROPOSAL, {
    variables: { id: proposalId },
    fetchPolicy: "cache-and-network",
  });
  // The row is the truth. The event and each socket open only start a read of it (D18).
  useConsoleEvents({
    onEvent: (event) => {
      if (event.type === "FixProposalReady" && event.proposalId === proposalId) {
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
            </TableRow>
          </TableHead>
          <TableBody>
            {proposal.actions.map((action) => (
              <TableRow key={`${action.kind}-${action.billId}`}>
                <TableCell>{action.kind}</TableCell>
                <TableCell>{action.supplierName}</TableCell>
                <TableCell>{action.invoiceNumber}</TableCell>
                <TableCell>{action.poNumber ?? ""}</TableCell>
              </TableRow>
            ))}
            {proposal.actions.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>No draft actions</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
