import { useQuery } from "@apollo/client";
import { Alert, Button, Paper, Stack, Typography } from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { Link } from "react-router";

import type { ProposalsQuery } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { PROPOSALS } from "../graphql/operations";
import { ListLimitNotice } from "../layout/ListLimitNotice";
import { ProposalStatusChip } from "./ProposalStatusChip";

type ProposalRow = ProposalsQuery["proposals"]["items"][number];

const COLUMNS: GridColDef<ProposalRow>[] = [
  {
    field: "status",
    headerName: "Status",
    flex: 0.8,
    sortable: false,
    renderCell: ({ row }) => <ProposalStatusChip status={row.status} />,
  },
  {
    field: "exceptions",
    headerName: "Exceptions",
    flex: 0.7,
    sortable: false,
    valueGetter: (_value, row) => row.exceptions.length,
  },
  {
    field: "actions",
    headerName: "Actions",
    flex: 0.7,
    sortable: false,
    valueGetter: (_value, row) => row.actions.length,
  },
  { field: "requestedBy", headerName: "Requested by", flex: 0.8, sortable: false },
  {
    field: "createdAt",
    headerName: "Requested",
    flex: 1.3,
    sortable: false,
    valueFormatter: (value: string) => new Date(value).toLocaleString("en-GB"),
  },
  {
    field: "open",
    headerName: "",
    flex: 0.6,
    sortable: false,
    renderCell: ({ row }) => (
      <Button size="small" component={Link} to={`/proposals/${row.id}`}>
        Open
      </Button>
    ),
  },
];

export function ProposalsPage() {
  const { data, loading, error } = useQuery(PROPOSALS, { fetchPolicy: "cache-and-network" });

  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h1">
        Fix proposals
      </Typography>
      {error && <Alert severity="error">{errorMessage(error)}</Alert>}
      {data && (
        <ListLimitNotice shown={data.proposals.items.length} total={data.proposals.totalCount} />
      )}
      <Paper variant="outlined">
        <DataGrid
          aria-label="Proposals"
          rows={data?.proposals.items ?? []}
          columns={COLUMNS}
          loading={loading && !data}
          disableRowSelectionOnClick
          localeText={{ noRowsLabel: "No proposals" }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
          autoHeight
        />
      </Paper>
    </Stack>
  );
}
