import { safeReturnPath } from "./returnPath";

describe("sign-in return path", () => {
  it.each([
    ["/inbox?status=open", "/inbox?status=open"],
    ["//evil.example/x", "/"],
    ["https://evil.example", "/"],
    [undefined, "/"],
    [42, "/"],
  ])("us1: state %s returns to %s", (state, expected) => {
    expect(safeReturnPath(state)).toBe(expected);
  });
});
