import { describe, expect, it } from "vitest";

import { isCheckJobEvent, parseConsoleEvent } from "./consoleEvent";

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
});
