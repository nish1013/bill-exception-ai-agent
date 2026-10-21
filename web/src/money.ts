// The API carries integer minor units (D14). The currency sets the number of decimals.
export function formatMoney(minorUnits: number, currency: string): string {
  const format = new Intl.NumberFormat("en-GB", { style: "currency", currency });
  const decimals = format.resolvedOptions().maximumFractionDigits ?? 2;
  return format.format(minorUnits / 10 ** decimals);
}
