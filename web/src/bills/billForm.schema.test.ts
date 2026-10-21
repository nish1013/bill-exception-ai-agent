import {
  billFormSchema,
  EMPTY_BILL_FORM,
  toBillInput,
  type BillFormValues,
} from "./billForm.schema";

const B1: BillFormValues = {
  ...EMPTY_BILL_FORM,
  supplierName: "Fresh Farms Ltd",
  supplierVatNumber: "GB123456789",
  invoiceNumber: "INV-001",
  amount: "120000",
  currency: "GBP",
  vatAmount: "20000",
  issueDate: "2026-10-01",
  poNumber: "PO-100",
  hasReceipt: true,
};

function refused(changes: Partial<BillFormValues>): string[] {
  const result = billFormSchema.safeParse({ ...B1, ...changes });
  return result.success ? [] : result.error.issues.map((issue) => String(issue.path[0]));
}

describe("US4 bill form copies the value-object rules", () => {
  it("us4: B1 becomes the API input in minor units", () => {
    expect(toBillInput(billFormSchema.parse(B1))).toEqual({
      supplierName: "Fresh Farms Ltd",
      supplierVatNumber: "GB123456789",
      invoiceNumber: "INV-001",
      amount: 120000,
      currency: "GBP",
      vatAmount: 20000,
      issueDate: "2026-10-01",
      poNumber: "PO-100",
      hasReceipt: true,
    });
  });

  it.each([
    ["1200.50", "amount"],
    ["1200.0", "amount"],
    ["-1", "amount"],
    ["", "amount"],
    ["1e5", "amount"],
    ["9007199254740992", "amount"],
  ])("d14: amount %s is refused", (amount, field) => {
    expect(refused({ amount })).toEqual([field]);
  });

  it.each(["0", "120000", "9007199254740991"])("d14: amount %s is accepted", (amount) => {
    expect(refused({ amount })).toEqual([]);
  });

  it.each(["20.5", "x"])("d14: VAT amount %s is refused", (vatAmount) => {
    expect(refused({ vatAmount })).toEqual(["vatAmount"]);
  });

  it("us4: blank optional fields become null", () => {
    const input = toBillInput(
      billFormSchema.parse({ ...B1, supplierVatNumber: " ", vatAmount: "", poNumber: "" }),
    );
    expect([input.supplierVatNumber, input.vatAmount, input.poNumber]).toEqual([null, null, null]);
  });

  it.each([
    [{ currency: "gbp" }, "currency"],
    [{ currency: "XXX1" }, "currency"],
    [{ supplierName: " ... " }, "supplierName"],
    [{ invoiceNumber: "--" }, "invoiceNumber"],
    [{ poNumber: "#" }, "poNumber"],
    [{ supplierVatNumber: "-" }, "supplierVatNumber"],
    [{ issueDate: "" }, "issueDate"],
  ])("us4: %o is refused", (changes, field) => {
    expect(refused(changes)).toEqual([field]);
  });
});
