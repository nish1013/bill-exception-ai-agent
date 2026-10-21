import { formatMoney } from "./money";

describe("money display", () => {
  it.each([
    [120000, "GBP", "£1,200.00"],
    [5000, "EUR", "€50.00"],
    [1200, "JPY", "JP¥1,200"],
  ])("d14: %d %s shows as %s", (minor, currency, expected) => {
    expect(formatMoney(minor, currency)).toBe(expected);
  });
});
