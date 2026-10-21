import { useQuery } from "@apollo/client";
import { Alert, Chip, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useState } from "react";

import type { ExceptionsQuery } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { EXCEPTIONS } from "../graphql/operations";
import { ListLimitNotice } from "../layout/ListLimitNotice";

type ExceptionRow = ExceptionsQuery["exceptions"]["items"][number];
type ChipColor = "error" | "warning" | "default";

const ALL = "all";
const STATUSES = ["open", "ignored", "resolved", "pending_sync"];
const SEVERITIES = ["high", "medium", "low"];
const SEVERITY_COLORS: Record<string, ChipColor> = {
  high: "error",
  medium: "warning",
  low: "default",
};

const COLUMNS: GridColDef<ExceptionRow>[] = [
  {
    field: "severity",
    headerName: "Severity",
    flex: 0.8,
    sortable: false,
    renderCell: ({ value }) => (
      <Chip size="small" label={value} color={SEVERITY_COLORS[value as string] ?? "default"} />
    ),
  },
  { field: "rule", headerName: "Rule", flex: 1.2, sortable: false },
  { field: "supplierName", headerName: "Supplier", flex: 1.5, sortable: false },
  { field: "invoiceNumber", headerName: "Invoice number", flex: 1, sortable: false },
  { field: "status", headerName: "Status", flex: 0.8, sortable: false },
  {
    field: "createdAt",
    headerName: "Found",
    flex: 1.3,
    sortable: false,
    valueFormatter: (value: string) => new Date(value).toLocaleString("en-GB"),
  },
];

function filterValue(value: string): string | null {
  return value === ALL ? null : value;
}

export function InboxPage() {
  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState(ALL);
  const { data, loading, error } = useQuery(EXCEPTIONS, {
    variables: { status: filterValue(status), severity: filterValue(severity) },
    fetchPolicy: "cache-and-network",
  });

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="h5" component="h1" sx={{ flexGrow: 1 }}>
          Exception inbox
        </Typography>
        <TextField
          select
          size="small"
          label="Status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value={ALL}>All</MenuItem>
          {STATUSES.map((value) => (
            <MenuItem key={value} value={value}>
              {value}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Severity"
          value={severity}
          onChange={(event) => setSeverity(event.target.value)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value={ALL}>All</MenuItem>
          {SEVERITIES.map((value) => (
            <MenuItem key={value} value={value}>
              {value}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {data && (
        <ListLimitNotice shown={data.exceptions.items.length} total={data.exceptions.totalCount} />
      )}
      <Paper variant="outlined">
        <DataGrid
          aria-label="Exceptions"
          rows={data?.exceptions.items ?? []}
          columns={COLUMNS}
          loading={loading && !data}
          disableRowSelectionOnClick
          localeText={{ noRowsLabel: "No exceptions" }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
          autoHeight
        />
      </Paper>
    </Stack>
  );
}
