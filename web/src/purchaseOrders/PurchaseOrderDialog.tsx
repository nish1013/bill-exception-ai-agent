import { useMutation, useQuery } from "@apollo/client";
import { Alert, Dialog, DialogContent, DialogTitle, LinearProgress, Stack } from "@mui/material";

import type { AddPurchaseOrderMutationVariables } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { ADD_PURCHASE_ORDER, SUPPLIERS } from "../graphql/operations";
import { ListLimitNotice } from "../layout/ListLimitNotice";
import { PurchaseOrderForm } from "./PurchaseOrderForm";

export interface PurchaseOrderDialogProps {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
}

export function PurchaseOrderDialog({ open, onClose, onAdded }: PurchaseOrderDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add purchase order</DialogTitle>
      <DialogContent>
        {open && <PurchaseOrderContent onClose={onClose} onAdded={onAdded} />}
      </DialogContent>
    </Dialog>
  );
}

interface PurchaseOrderContentProps {
  onClose: () => void;
  onAdded: () => void;
}

function PurchaseOrderContent({ onClose, onAdded }: PurchaseOrderContentProps) {
  const { data, loading, error } = useQuery(SUPPLIERS, { fetchPolicy: "network-only" });
  const [addPurchaseOrder] = useMutation(ADD_PURCHASE_ORDER);

  const submit = async (variables: AddPurchaseOrderMutationVariables) => {
    try {
      await addPurchaseOrder({ variables });
    } catch (submitError) {
      throw new Error(errorMessage(submitError));
    }
    onAdded();
  };

  if (error) {
    return <Alert severity="error">{errorMessage(error)}</Alert>;
  }
  if (loading || !data) {
    return <LinearProgress aria-label="Loading suppliers" />;
  }
  return (
    <Stack spacing={2}>
      <ListLimitNotice shown={data.suppliers.items.length} total={data.suppliers.totalCount} />
      <PurchaseOrderForm suppliers={data.suppliers.items} onSubmit={submit} onCancel={onClose} />
    </Stack>
  );
}
