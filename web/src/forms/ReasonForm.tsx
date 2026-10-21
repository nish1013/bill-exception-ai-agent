import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Stack, TextField } from "@mui/material";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { reasonText } from "./valueRules";

const reasonFormSchema = z.object({ reason: reasonText });

type ReasonFormValues = z.input<typeof reasonFormSchema>;

export interface ReasonFormProps {
  name: string;
  submitLabel: string;
  onSubmit: (reason: string) => Promise<void>;
  onCancel: () => void;
}

export function ReasonForm({ name, submitLabel, onSubmit, onCancel }: ReasonFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { control, handleSubmit, formState } = useForm<ReasonFormValues>({
    resolver: zodResolver(reasonFormSchema),
    defaultValues: { reason: "" },
  });

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await onSubmit(reasonFormSchema.parse(values).reason);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    }
  });

  return (
    <form noValidate onSubmit={submit} aria-label={name}>
      <Stack spacing={2} sx={{ pt: 1 }}>
        <Controller
          name="reason"
          control={control}
          render={({ field, fieldState }) => (
            <TextField
              {...field}
              label="Reason"
              required
              multiline
              minRows={2}
              error={Boolean(fieldState.error)}
              helperText={fieldState.error?.message}
            />
          )}
        />
        {submitError && <Alert severity="error">{submitError}</Alert>}
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={formState.isSubmitting}>
            {submitLabel}
          </Button>
        </Stack>
      </Stack>
    </form>
  );
}
