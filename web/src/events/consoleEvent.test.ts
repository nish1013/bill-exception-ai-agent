import { describe, expect, it } from "vitest";

import { isCheckJobEvent, isProposalEvent, parseConsoleEvent } from "./consoleEvent";

describe("parseConsoleEvent", () => {
  it("us11: reads FixProposalReady", () => {
    const event = parseConsoleEvent(
      JSON.stringify({ type: "FixProposalReady", proposalId: "p1", status: "pending" }),
    );

    expect(event).toEqual({ type: "FixProposalReady", proposalId: "p1", status: "pending" });
    expect(event && isCheckJobEvent(event)).toBe(false);
  });

  it("us11: skips a proposal event with an unknown status", () => {
    const text = JSON.stringify({ type: "FixProposalReady", proposalId: "p1", status: "approved" });

    expect(parseConsoleEvent(text)).toBeNull();
  });

  it("us14: reads ProposalSyncChanged", () => {
    const event = parseConsoleEvent(
      JSON.stringify({ type: "ProposalSyncChanged", proposalId: "p1", status: "synced" }),
    );

    expect(event).toEqual({ type: "ProposalSyncChanged", proposalId: "p1", status: "synced" });
    expect(event && isCheckJobEvent(event)).toBe(false);
  });

  it("us14: a sync event of another proposal is not for this page", () => {
    const event = parseConsoleEvent(
      JSON.stringify({ type: "ProposalSyncChanged", proposalId: "p2", status: "sync_failed" }),
    );

    expect(event && [isProposalEvent(event, "p1"), isProposalEvent(event, "p2")]).toEqual([
      false,
      true,
    ]);
  });
});
