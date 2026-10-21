import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Checkbox, FormControlLabel, Stack, TextField } from "@mui/material";
import { useState } from "react";
import { Controller, useForm, type Path } from "react-hook-form";

import type { BillInput } from "../gql/graphql";
import {
  EMPTY_BILL_FORM,
  billFormSchema,
  toBillInput,
  type BillFormValues,
} from "./billForm.schema";

export interface BillIngestFormProps {
  onSubmit: (bill: BillInput) => Promise<void>;
  onCancel: () => void;
}

interface TextFieldSpec {
  name: Path<BillFormValues>;
  label: string;
  required?: boolean;
  type?: string;
  helperText?: string;
}

const TEXT_FIELDS: TextFieldSpec[] = [
  { name: "supplierName", label: "Supplier name", required: true },
  { name: "supplierVatNumber", label: "Supplier VAT number" },
  { name: "invoiceNumber", label: "Invoice number", required: true },
  {
    name: "amount",
    label: "Amount (minor units)",
    required: true,
    helperText: "Pence or cents: 120000 is 1200.00.",
  },
  { name: "currency", label: "Currency", required: true },
  { name: "vatAmount", label: "VAT amount (minor units)" },
  { name: "issueDate", label: "Issue date", required: true, type: "date" },
  { name: "poNumber", label: "PO number" },
];

export function BillIngestForm({ onSubmit, onCancel }: BillIngestFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { control, handleSubmit, formState } = useForm<BillFormValues>({
    resolver: zodResolver(billFormSchema),
    defaultValues: EMPTY_BILL_FORM,
  });

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await onSubmit(toBillInput(billFormSchema.parse(values)));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    }
  });

  return (
    <form noValidate onSubmit={submit} aria-label="Ingest bill">
      <Stack spacing={2} sx={{ pt: 1 }}>
        {TEXT_FIELDS.map((field) => (
          <Controller
            key={field.name}
            name={field.name}
            control={control}
            render={({ field: input, fieldState }) => (
              <TextField
                {...input}
                value={input.value as string}
                label={field.label}
                required={field.required}
                type={field.type ?? "text"}
                error={Boolean(fieldState.error)}
                helperText={fieldState.error?.message ?? field.helperText}
                slotProps={{ inputLabel: field.type === "date" ? { shrink: true } : undefined }}
              />
            )}
          />
        ))}
        <Controller
          name="hasReceipt"
          control={control}
          render={({ field }) => (
            <FormControlLabel
              label="Receipt received"
              control={
                <Checkbox
                  checked={field.value}
                  onChange={(event) => field.onChange(event.target.checked)}
                />
              }
            />
          )}
        />
        {submitError && <Alert severity="error">{submitError}</Alert>}
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={formState.isSubmitting}>
            Save bill
          </Button>
        </Stack>
      </Stack>
    </form>
  );
}
