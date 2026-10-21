import { useMutation } from "@apollo/client";
import { Dialog, DialogContent, DialogTitle } from "@mui/material";
import { useState } from "react";

import type { BillInput } from "../gql/graphql";
import { errorMessage } from "../graphql/errorMessage";
import { BILLS, INGEST_BILL } from "../graphql/operations";
import { BillIngestForm } from "./BillIngestForm";

export interface BillIngestDialogProps {
  open: boolean;
  onClose: () => void;
  onIngested: () => void;
}

export function BillIngestDialog({ open, onClose, onIngested }: BillIngestDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Ingest bill</DialogTitle>
      <DialogContent>
        {open && <IngestBillContent onClose={onClose} onIngested={onIngested} />}
      </DialogContent>
    </Dialog>
  );
}

interface IngestBillContentProps {
  onClose: () => void;
  onIngested: () => void;
}

function IngestBillContent({ onClose, onIngested }: IngestBillContentProps) {
  // One key for each opened form: a resend after a lost response stores the bill once (D2).
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [ingestBill] = useMutation(INGEST_BILL, { refetchQueries: [BILLS] });

  const submit = async (bill: BillInput) => {
    try {
      await ingestBill({ variables: { idempotencyKey, bill } });
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    onIngested();
  };

  return <BillIngestForm onSubmit={submit} onCancel={onClose} />;
}
