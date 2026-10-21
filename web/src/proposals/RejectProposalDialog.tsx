import { useMutation } from "@apollo/client";
import { Dialog, DialogContent, DialogContentText, DialogTitle } from "@mui/material";

import { ReasonForm } from "../forms/ReasonForm";
import { errorMessage } from "../graphql/errorMessage";
import { REJECT_FIX_PROPOSAL } from "../graphql/operations";

export interface RejectProposalDialogProps {
  proposalId: string;
  open: boolean;
  onClose: () => void;
}

export function RejectProposalDialog({ proposalId, open, onClose }: RejectProposalDialogProps) {
  const [rejectFixProposal] = useMutation(REJECT_FIX_PROPOSAL);

  const submit = async (reason: string) => {
    try {
      await rejectFixProposal({ variables: { proposalId, reason } });
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Reject proposal</DialogTitle>
      <DialogContent>
        <DialogContentText>A rejected proposal is never applied.</DialogContentText>
        <ReasonForm
          name="Reject proposal"
          submitLabel="Reject"
          onSubmit={submit}
          onCancel={onClose}
        />
      </DialogContent>
    </Dialog>
  );
}
