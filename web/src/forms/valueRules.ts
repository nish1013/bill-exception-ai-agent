import { z } from "zod";

// These rules copy the API value objects, so the browser refuses a bad value before the API does.
const LETTER_OR_DIGIT = /[\p{L}\p{N}]/u;
const PUNCTUATION_AND_SPACE = /[\p{P}\s]/gu;
const WHOLE_NUMBER = /^\d+$/;
const CURRENCY_CODE = /^[A-Z]{3}$/;

const MINOR_UNITS_MESSAGE = "Enter a whole number of minor units, for example 120000 for 1200.00.";

function hasLetterOrDigit(value: string): boolean {
  return LETTER_OR_DIGIT.test(value.normalize("NFKC"));
}

export function hasNameText(value: string): boolean {
  return value.normalize("NFKC").replace(PUNCTUATION_AND_SPACE, "").length > 0;
}

function isSafeWholeNumber(value: string): boolean {
  return WHOLE_NUMBER.test(value) && Number.isSafeInteger(Number(value));
}

export const minorUnits = z.string().trim().refine(isSafeWholeNumber, MINOR_UNITS_MESSAGE);

export const optionalMinorUnits = z
  .string()
  .trim()
  .refine((value) => value === "" || isSafeWholeNumber(value), MINOR_UNITS_MESSAGE);

export const currencyCode = z
  .string()
  .trim()
  .regex(CURRENCY_CODE, "Enter a 3-letter ISO 4217 code, for example GBP.");

export const documentNumber = (label: string) =>
  z.string().trim().refine(hasLetterOrDigit, `${label} must hold a letter or a digit.`);

export const optionalDocumentNumber = (label: string) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === "" || hasLetterOrDigit(value),
      `${label} must hold a letter or a digit.`,
    );

// The API refuses an empty reason and a reason over 1000 characters (US9, US13).
export const REASON_MAX = 1000;

export const reasonText = z
  .string()
  .trim()
  .min(1, "Enter a reason.")
  .max(REASON_MAX, `Enter at most ${REASON_MAX} characters.`);
