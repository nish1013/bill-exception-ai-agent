import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BillIngestForm } from "./BillIngestForm";

async function fillB1(amount: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/Supplier name/), "Fresh Farms Ltd");
  await user.type(screen.getByLabelText(/Invoice number/), "INV-001");
  await user.type(screen.getByLabelText(/^Amount/), amount);
  await user.type(screen.getByLabelText(/Issue date/), "2026-10-01");
  await user.click(screen.getByRole("button", { name: "Save bill" }));
}

describe("US4 ingest form", () => {
  it("us4: refuses 1200.50 with no API call", async () => {
    const onSubmit = vi.fn();
    render(<BillIngestForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await fillB1("1200.50");

    expect(await screen.findByText(/whole number of minor units/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("us4: sends 120000 minor units", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<BillIngestForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await fillB1("120000");

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit.mock.calls[0]?.[0]).toMatchObject({ amount: 120000, currency: "GBP" });
  });

  it("us4: shows the API refusal in the form", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("The API refused a value."));
    render(<BillIngestForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await fillB1("120000");

    expect(await screen.findByRole("alert")).toHaveTextContent("The API refused a value.");
  });
});
