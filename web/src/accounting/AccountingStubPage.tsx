import { useQuery } from "@apollo/client";
import { Alert, Paper, Stack, Typography } from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";

import type { AccountingLedgerQuery } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { ACCOUNTING_LEDGER } from "../graphql/operations";
import { ListLimitNotice } from "../layout/ListLimitNotice";

type LedgerRow = AccountingLedgerQuery["accountingLedger"]["items"][number];

const COLUMNS: GridColDef<LedgerRow>[] = [
  { field: "kind", headerName: "Action", flex: 0.6, sortable: false },
  { field: "supplierName", headerName: "Supplier", flex: 1.2, sortable: false },
  { field: "invoiceNumber", headerName: "Invoice number", flex: 0.9, sortable: false },
  { field: "poNumber", headerName: "PO number", flex: 0.8, sortable: false },
  { field: "answer", headerName: "Answer", flex: 0.7, sortable: false },
  {
    field: "syncKey",
    headerName: "Sync key",
    flex: 2,
    sortable: false,
    cellClassName: "sync-key",
  },
  {
    field: "receivedAt",
    headerName: "Received",
    flex: 1.2,
    sortable: false,
    valueFormatter: (value: string) => new Date(value).toLocaleString("en-GB"),
  },
];

// The demo accounting stub (D51): each action it received, once for each sync key.
export function AccountingStubPage() {
  const { data, loading, error } = useQuery(ACCOUNTING_LEDGER, {
    fetchPolicy: "cache-and-network",
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h1">
        Accounting (stub)
      </Typography>
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {data && (
        <ListLimitNotice
          shown={data.accountingLedger.items.length}
          total={data.accountingLedger.totalCount}
        />
      )}
      <Paper variant="outlined">
        <DataGrid
          aria-label="Ledger"
          rows={data?.accountingLedger.items ?? []}
          columns={COLUMNS}
          getRowId={(row) => row.syncKey}
          loading={loading && !data}
          disableRowSelectionOnClick
          localeText={{ noRowsLabel: "No actions received" }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
          sx={{ "& .sync-key": { fontFamily: "monospace" } }}
          autoHeight
        />
      </Paper>
    </Stack>
  );
}
