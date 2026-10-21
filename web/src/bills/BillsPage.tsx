import { useMutation, useQuery } from "@apollo/client";
import { Alert, Button, Paper, Snackbar, Stack, Typography } from "@mui/material";
import { DataGrid, type GridColDef, type GridRowSelectionModel } from "@mui/x-data-grid";
import { useState } from "react";

import type { BillsQuery } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { BILLS, START_BILL_CHECK } from "../graphql/operations";
import { formatMoney } from "../money";
import { BillIngestDialog } from "./BillIngestDialog";
import { CheckJobProgress } from "./CheckJobProgress";

type BillRow = BillsQuery["bills"][number];

const COLUMNS: GridColDef<BillRow>[] = [
  { field: "invoiceNumber", headerName: "Invoice number", flex: 1 },
  { field: "supplierName", headerName: "Supplier", flex: 1.5 },
  {
    field: "amount",
    headerName: "Amount",
    flex: 1,
    align: "right",
    headerAlign: "right",
    valueFormatter: (_value, row) => formatMoney(row.amount, row.currency),
  },
  { field: "issueDate", headerName: "Issue date", flex: 1 },
  {
    field: "hasReceipt",
    headerName: "Receipt",
    flex: 0.7,
    valueFormatter: (value) => (value ? "Yes" : "No"),
  },
  {
    field: "createdAt",
    headerName: "Ingested",
    flex: 1.3,
    valueFormatter: (value: string) => new Date(value).toLocaleString("en-GB"),
  },
];

export function BillsPage() {
  const { data, loading, error } = useQuery(BILLS, { fetchPolicy: "cache-and-network" });
  const [startCheck, startState] = useMutation(START_BILL_CHECK);
  const [selection, setSelection] = useState<GridRowSelectionModel>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const start = async () => {
    const result = await startCheck({ variables: { billIds: selection.map(String) } });
    if (result.data) {
      setJobId(result.data.startBillCheck.id);
      setSelection([]);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="h5" component="h1" sx={{ flexGrow: 1 }}>
          Bills
        </Typography>
        <Button variant="outlined" onClick={() => setIngestOpen(true)}>
          Ingest bill
        </Button>
        <Button
          variant="contained"
          disabled={selection.length === 0 || startState.loading}
          onClick={() => void start().catch(() => undefined)}
        >
          Start check
        </Button>
      </Stack>
      {startState.error && <Alert severity="error">{errorMessage(startState.error)}</Alert>}
      {jobId && <CheckJobProgress key={jobId} jobId={jobId} />}
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      <Paper variant="outlined">
        <DataGrid
          aria-label="Bills"
          rows={data?.bills ?? []}
          columns={COLUMNS}
          loading={loading && !data}
          checkboxSelection
          disableRowSelectionOnClick
          rowSelectionModel={selection}
          onRowSelectionModelChange={setSelection}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
          autoHeight
        />
      </Paper>
      <BillIngestDialog
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        onIngested={() => {
          setIngestOpen(false);
          setNotice("Bill ingested.");
        }}
      />
      <Snackbar
        open={notice !== null}
        autoHideDuration={4000}
        onClose={() => setNotice(null)}
        message={notice}
      />
    </Stack>
  );
}
