import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Stack, TextField } from "@mui/material";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { ignoreFormSchema, type IgnoreFormValues } from "./ignoreForm.schema";

export interface IgnoreFormProps {
  onSubmit: (reason: string) => Promise<void>;
  onCancel: () => void;
}

export function IgnoreForm({ onSubmit, onCancel }: IgnoreFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { control, handleSubmit, formState } = useForm<IgnoreFormValues>({
    resolver: zodResolver(ignoreFormSchema),
    defaultValues: { reason: "" },
  });

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await onSubmit(ignoreFormSchema.parse(values).reason);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    }
  });

  return (
    <form noValidate onSubmit={submit} aria-label="Ignore exception">
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
            Ignore
          </Button>
        </Stack>
      </Stack>
    </form>
  );
}
