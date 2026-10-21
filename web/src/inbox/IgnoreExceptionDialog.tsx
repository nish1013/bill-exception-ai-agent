import { useMutation } from "@apollo/client";
import { Dialog, DialogContent, DialogContentText, DialogTitle } from "@mui/material";

import { errorMessage } from "../graphql/errorMessage";
import { EXCEPTIONS, IGNORE_EXCEPTION } from "../graphql/operations";
import { IgnoreForm } from "./IgnoreForm";

export interface IgnoredException {
  id: string;
  rule: string;
  invoiceNumber: string;
}

export interface IgnoreExceptionDialogProps {
  exception: IgnoredException | null;
  onClose: () => void;
  onIgnored: () => void;
}

export function IgnoreExceptionDialog({
  exception,
  onClose,
  onIgnored,
}: IgnoreExceptionDialogProps) {
  const [ignoreException] = useMutation(IGNORE_EXCEPTION, { refetchQueries: [EXCEPTIONS] });

  const submit = async (reason: string) => {
    if (!exception) {
      return;
    }
    try {
      await ignoreException({ variables: { exceptionId: exception.id, reason } });
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    onIgnored();
  };

  return (
    <Dialog open={exception !== null} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Ignore exception</DialogTitle>
      <DialogContent>
        {exception && (
          <>
            <DialogContentText>
              {exception.rule} on {exception.invoiceNumber}. An ignored exception stays ignored.
            </DialogContentText>
            <IgnoreForm onSubmit={submit} onCancel={onClose} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
