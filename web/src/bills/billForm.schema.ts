import { z } from "zod";

import type { BillInput } from "../gql/graphql";
import {
  currencyCode,
  documentNumber,
  hasNameText,
  minorUnits,
  optionalDocumentNumber,
  optionalMinorUnits,
} from "../forms/valueRules";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export const billFormSchema = z.object({
  supplierName: z.string().trim().refine(hasNameText, "Enter the supplier name."),
  supplierVatNumber: optionalDocumentNumber("VAT number"),
  invoiceNumber: documentNumber("Invoice number"),
  amount: minorUnits,
  currency: currencyCode,
  vatAmount: optionalMinorUnits,
  issueDate: z.string().regex(ISO_DATE, "Enter the issue date."),
  poNumber: optionalDocumentNumber("PO number"),
  hasReceipt: z.boolean(),
});

export type BillFormValues = z.input<typeof billFormSchema>;

export const EMPTY_BILL_FORM: BillFormValues = {
  supplierName: "",
  supplierVatNumber: "",
  invoiceNumber: "",
  amount: "",
  currency: "GBP",
  vatAmount: "",
  issueDate: "",
  poNumber: "",
  hasReceipt: false,
};

export function toBillInput(values: z.output<typeof billFormSchema>): BillInput {
  return {
    supplierName: values.supplierName,
    supplierVatNumber: values.supplierVatNumber || null,
    invoiceNumber: values.invoiceNumber,
    amount: Number(values.amount),
    currency: values.currency,
    vatAmount: values.vatAmount === "" ? null : Number(values.vatAmount),
    issueDate: values.issueDate,
    poNumber: values.poNumber || null,
    hasReceipt: values.hasReceipt,
  };
}
