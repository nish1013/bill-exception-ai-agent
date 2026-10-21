import { z } from "zod";

import type { BillInput } from "../gql/graphql";

// These rules copy the API value objects, so the browser refuses a bad value before the API does.
const LETTER_OR_DIGIT = /[\p{L}\p{N}]/u;
const PUNCTUATION_AND_SPACE = /[\p{P}\s]/gu;
const WHOLE_NUMBER = /^\d+$/;
const CURRENCY_CODE = /^[A-Z]{3}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const MINOR_UNITS_MESSAGE = "Enter a whole number of minor units, for example 120000 for 1200.00.";

function hasLetterOrDigit(value: string): boolean {
  return LETTER_OR_DIGIT.test(value.normalize("NFKC"));
}

function hasNameText(value: string): boolean {
  return value.normalize("NFKC").replace(PUNCTUATION_AND_SPACE, "").length > 0;
}

function isSafeWholeNumber(value: string): boolean {
  return WHOLE_NUMBER.test(value) && Number.isSafeInteger(Number(value));
}

const minorUnits = z.string().trim().refine(isSafeWholeNumber, MINOR_UNITS_MESSAGE);

const optionalMinorUnits = z
  .string()
  .trim()
  .refine((value) => value === "" || isSafeWholeNumber(value), MINOR_UNITS_MESSAGE);

const optionalDocumentNumber = (label: string) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === "" || hasLetterOrDigit(value),
      `${label} must hold a letter or a digit.`,
    );

export const billFormSchema = z.object({
  supplierName: z.string().trim().refine(hasNameText, "Enter the supplier name."),
  supplierVatNumber: optionalDocumentNumber("VAT number"),
  invoiceNumber: z
    .string()
    .trim()
    .refine(hasLetterOrDigit, "Invoice number must hold a letter or a digit."),
  amount: minorUnits,
  currency: z
    .string()
    .trim()
    .regex(CURRENCY_CODE, "Enter a 3-letter ISO 4217 code, for example GBP."),
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
