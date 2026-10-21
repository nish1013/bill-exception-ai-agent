import { ReasonForm } from "../forms/ReasonForm";

export interface IgnoreFormProps {
  onSubmit: (reason: string) => Promise<void>;
  onCancel: () => void;
}

export function IgnoreForm({ onSubmit, onCancel }: IgnoreFormProps) {
  return (
    <ReasonForm
      name="Ignore exception"
      submitLabel="Ignore"
      onSubmit={onSubmit}
      onCancel={onCancel}
    />
  );
}
