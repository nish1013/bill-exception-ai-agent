import { z } from "zod";

// The API refuses an empty reason and a reason over 1000 characters (US9).
export const IGNORE_REASON_MAX = 1000;

export const ignoreFormSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, "Enter a reason.")
    .max(IGNORE_REASON_MAX, `Enter at most ${IGNORE_REASON_MAX} characters.`),
});

export type IgnoreFormValues = z.input<typeof ignoreFormSchema>;
