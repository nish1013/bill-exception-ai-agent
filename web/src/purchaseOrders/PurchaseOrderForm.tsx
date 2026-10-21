import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, MenuItem, Stack, TextField } from "@mui/material";
import { useState } from "react";
import { Controller, useForm, type Path } from "react-hook-form";

import type { AddPurchaseOrderMutationVariables } from "../gql/graphql";
import {
  EMPTY_PURCHASE_ORDER_FORM,
  purchaseOrderFormSchema,
  toPurchaseOrderVariables,
  type PurchaseOrderFormValues,
} from "./purchaseOrderForm.schema";

export interface SupplierOption {
  id: string;
  name: string;
  vatNumber?: string | null;
}

export interface PurchaseOrderFormProps {
  suppliers: SupplierOption[];
  onSubmit: (variables: AddPurchaseOrderMutationVariables) => Promise<void>;
  onCancel: () => void;
}

interface TextFieldSpec {
  name: Path<PurchaseOrderFormValues>;
  label: string;
  helperText?: string;
}

const TEXT_FIELDS: TextFieldSpec[] = [
  { name: "poNumber", label: "PO number" },
  {
    name: "amount",
    label: "Amount (minor units)",
    helperText: "Pence or cents: 120000 is 1200.00.",
  },
  { name: "currency", label: "Currency" },
];

function supplierLabel(supplier: SupplierOption): string {
  return supplier.vatNumber ? `${supplier.name} (${supplier.vatNumber})` : supplier.name;
}

export function PurchaseOrderForm({ suppliers, onSubmit, onCancel }: PurchaseOrderFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { control, handleSubmit, formState } = useForm<PurchaseOrderFormValues>({
    resolver: zodResolver(purchaseOrderFormSchema),
    defaultValues: EMPTY_PURCHASE_ORDER_FORM,
  });

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await onSubmit(toPurchaseOrderVariables(purchaseOrderFormSchema.parse(values)));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : String(error));
    }
  });

  return (
    <form noValidate onSubmit={submit} aria-label="Add purchase order">
      <Stack spacing={2} sx={{ pt: 1 }}>
        <Controller
          name="supplierId"
          control={control}
          render={({ field, fieldState }) => (
            <TextField
              {...field}
              select
              label="Supplier"
              required
              error={Boolean(fieldState.error)}
              helperText={fieldState.error?.message}
            >
              {suppliers.map((supplier) => (
                <MenuItem key={supplier.id} value={supplier.id}>
                  {supplierLabel(supplier)}
                </MenuItem>
              ))}
            </TextField>
          )}
        />
        {TEXT_FIELDS.map((spec) => (
          <Controller
            key={spec.name}
            name={spec.name}
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                label={spec.label}
                required
                error={Boolean(fieldState.error)}
                helperText={fieldState.error?.message ?? spec.helperText}
              />
            )}
          />
        ))}
        {submitError && <Alert severity="error">{submitError}</Alert>}
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={formState.isSubmitting}>
            Save PO
          </Button>
        </Stack>
      </Stack>
    </form>
  );
}
