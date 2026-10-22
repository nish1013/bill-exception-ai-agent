export type ProposalStatusColor = "default" | "info" | "success" | "warning" | "error";

const COLORS: Record<string, ProposalStatusColor> = {
  drafting: "info",
  pending: "warning",
  approved: "success",
  syncing: "info",
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

// Only a pending proposal takes an approve or a reject (US12, US13).
export function canDecide(status: string): boolean {
  return status === "pending";
}

// Only a failed sync takes a retry, and only an approver starts it (US15, D32).
export function canRetrySync(status: string): boolean {
  return status === "sync_failed";
}

const APPROVED_STATUSES = ["approved", "syncing", "synced", "sync_failed"];

// The sync state of an action means something only after the approve (D9).
export function showsSync(status: string): boolean {
  return APPROVED_STATUSES.includes(status);
}
