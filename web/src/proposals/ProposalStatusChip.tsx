import { Chip } from "@mui/material";

import { proposalStatusColor } from "./proposalStatus";

export interface ProposalStatusChipProps {
  status: string;
}

export function ProposalStatusChip({ status }: ProposalStatusChipProps) {
  return <Chip size="small" label={status} color={proposalStatusColor(status)} />;
}
