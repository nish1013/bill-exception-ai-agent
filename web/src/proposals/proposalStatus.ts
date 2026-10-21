export type ProposalStatusColor = "default" | "info" | "success" | "warning" | "error";

const COLORS: Record<string, ProposalStatusColor> = {
  drafting: "info",
  pending: "warning",
  approved: "success",
  synced: "success",
  failed: "error",
  sync_failed: "error",
};

const REASONS: Record<string, string> = {
  max_tool_calls: "The agent made more than 8 tool calls.",
  timeout: "The agent ran for more than 60 seconds.",
  no_actions: "The agent drafted no action.",
  error: "The draft failed 3 times.",
};

export function proposalStatusColor(status: string): ProposalStatusColor {
  return COLORS[status] ?? "default";
}

export function failedReasonText(reason: string): string {
  return REASONS[reason] ?? reason;
}

export function isDrafting(status: string): boolean {
  return status === "drafting";
}
