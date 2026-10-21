import { Alert } from "@mui/material";

export interface ListLimitNoticeProps {
  shown: number;
  total: number;
}

// The API returns at most 500 rows (D15). The notice tells the user that rows are hidden.
export function ListLimitNotice({ shown, total }: ListLimitNoticeProps) {
  if (total <= shown) {
    return null;
  }
  return (
    <Alert severity="warning">
      Showing {shown} of {total}. Narrow the filter to see the rest.
    </Alert>
  );
}
