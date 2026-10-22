import { describe, expect, it } from "vitest";

import {
  canDecide,
  canRetrySync,
  failedReasonText,
  isDrafting,
  proposalStatusColor,
  showsSync,
} from "./proposalStatus";

describe("proposal status", () => {
  it.each([
    ["drafting", "info"],
    ["pending", "warning"],
    ["failed", "error"],
    ["stale", "default"],
    ["approved", "success"],
    ["rejected", "default"],
    ["syncing", "info"],
    ["synced", "success"],
    ["sync_failed", "error"],
  ])("us11 us14: %s shows as %s", (status, color) => {
    expect(proposalStatusColor(status)).toBe(color);
  });

  it("us11: max_tool_calls names the bound of 8 calls", () => {
    expect(failedReasonText("max_tool_calls")).toBe("The agent made more than 8 tool calls.");
  });

  it("us11: an unknown reason shows as it is", () => {
    expect(failedReasonText("new_reason")).toBe("new_reason");
  });

  it("us11: only drafting waits for the agent", () => {
    expect([isDrafting("drafting"), isDrafting("pending")]).toEqual([true, false]);
  });

  it.each([
    ["pending", true],
    ["drafting", false],
    ["approved", false],
    ["rejected", false],
    ["stale", false],
  ])("us12 us13: %s takes a decision: %s", (status, decides) => {
    expect(canDecide(status)).toBe(decides);
  });

  it.each([
    ["sync_failed", true],
    ["syncing", false],
    ["synced", false],
    ["approved", false],
  ])("us15: %s takes a retry: %s", (status, retries) => {
    expect(canRetrySync(status)).toBe(retries);
  });

  it.each([
    ["pending", false],
    ["rejected", false],
    ["approved", true],
    ["syncing", true],
    ["synced", true],
    ["sync_failed", true],
  ])("us14: %s shows the sync of each action: %s", (status, shows) => {
    expect(showsSync(status)).toBe(shows);
  });
});
