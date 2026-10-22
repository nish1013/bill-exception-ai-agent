import { useQuery } from "@apollo/client";
import {
  Alert,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import { errorMessage } from "../graphql/errorMessage";
import { REPORT } from "../graphql/operations";
import { formatMoney } from "../money";

// One total for each currency: v1 has no exchange rates (D13).
export function ReportPage() {
  const { data, error } = useQuery(REPORT, { fetchPolicy: "cache-and-network" });
  const totals = data?.report.moneyAtRisk ?? [];

  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h1">
        Report
      </Typography>
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {data && (
        <>
          <Typography aria-label="Open exceptions">
            Open exceptions: {data.report.openExceptions}
          </Typography>
          <Paper variant="outlined">
            <Table aria-label="Money at risk" size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Currency</TableCell>
                  <TableCell align="right">Money at risk</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {totals.map((total) => (
                  <TableRow key={total.currency}>
                    <TableCell>{total.currency}</TableCell>
                    <TableCell align="right">{formatMoney(total.amount, total.currency)}</TableCell>
                  </TableRow>
                ))}
                {totals.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={2}>No money at risk</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </>
      )}
    </Stack>
  );
}
