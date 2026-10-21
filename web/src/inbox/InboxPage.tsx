import { useMutation, useQuery } from "@apollo/client";
import {
  Alert,
  Button,
  Chip,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef, type GridRowSelectionModel } from "@mui/x-data-grid";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";

import type { ExceptionsQuery } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { EXCEPTIONS, REQUEST_FIX_PROPOSAL } from "../graphql/operations";
import { ListLimitNotice } from "../layout/ListLimitNotice";
import { IgnoreExceptionDialog, type IgnoredException } from "./IgnoreExceptionDialog";

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

function columns(onIgnore: (row: ExceptionRow) => void): GridColDef<ExceptionRow>[] {
  return [
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
    { field: "resolvedBy", headerName: "Resolved by", flex: 0.8, sortable: false },
    { field: "reason", headerName: "Reason", flex: 1.5, sortable: false },
    {
      field: "actions",
      headerName: "",
      flex: 0.7,
      sortable: false,
      renderCell: ({ row }) =>
        row.status === "open" && (
          <Button size="small" onClick={() => onIgnore(row)}>
            Ignore
          </Button>
        ),
    },
  ];
}

function filterValue(value: string): string | null {
  return value === ALL ? null : value;
}

export function InboxPage() {
  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState(ALL);
  const [ignoring, setIgnoring] = useState<IgnoredException | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { data, loading, error } = useQuery(EXCEPTIONS, {
    variables: { status: filterValue(status), severity: filterValue(severity) },
    fetchPolicy: "cache-and-network",
  });
  const gridColumns = useMemo(() => columns(setIgnoring), []);
  const [selection, setSelection] = useState<GridRowSelectionModel>([]);
  const [requestProposal, requestState] = useMutation(REQUEST_FIX_PROPOSAL);
  const navigate = useNavigate();

  const request = async () => {
    const result = await requestProposal({ variables: { exceptionIds: selection.map(String) } });
    if (result.data) {
      void navigate(`/proposals/${result.data.requestFixProposal.id}`);
    }
  };

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
        <Button
          variant="contained"
          disabled={selection.length === 0 || requestState.loading}
          onClick={() => void request().catch(() => undefined)}
        >
          Request proposal
        </Button>
      </Stack>
      {requestState.error && <Alert severity="error">{errorMessage(requestState.error)}</Alert>}
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {data && (
        <ListLimitNotice shown={data.exceptions.items.length} total={data.exceptions.totalCount} />
      )}
      <Paper variant="outlined">
        <DataGrid
          aria-label="Exceptions"
          rows={data?.exceptions.items ?? []}
          columns={gridColumns}
          loading={loading && !data}
          checkboxSelection
          isRowSelectable={({ row }) => row.status === "open"}
          rowSelectionModel={selection}
          onRowSelectionModelChange={setSelection}
          disableRowSelectionOnClick
          localeText={{ noRowsLabel: "No exceptions" }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
          autoHeight
        />
      </Paper>
      <IgnoreExceptionDialog
        exception={ignoring}
        onClose={() => setIgnoring(null)}
        onIgnored={() => {
          setIgnoring(null);
          setNotice("Exception ignored.");
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
