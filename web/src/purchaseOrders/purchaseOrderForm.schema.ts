import { z } from "zod";

import type { AddPurchaseOrderMutationVariables } from "../gql/graphql";
import { currencyCode, documentNumber, minorUnits } from "../forms/valueRules";

export const purchaseOrderFormSchema = z.object({
  supplierId: z.string().min(1, "Choose the supplier."),
  poNumber: documentNumber("PO number"),
  amount: minorUnits,
  currency: currencyCode,
});

export type PurchaseOrderFormValues = z.input<typeof purchaseOrderFormSchema>;

export const EMPTY_PURCHASE_ORDER_FORM: PurchaseOrderFormValues = {
  supplierId: "",
  poNumber: "",
  amount: "",
  currency: "GBP",
};

export function toPurchaseOrderVariables(
  values: z.output<typeof purchaseOrderFormSchema>,
): AddPurchaseOrderMutationVariables {
  return {
    supplierId: values.supplierId,
    poNumber: values.poNumber,
    amount: Number(values.amount),
    currency: values.currency,
  };
}
