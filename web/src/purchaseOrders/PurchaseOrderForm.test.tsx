import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PurchaseOrderForm } from "./PurchaseOrderForm";

const S1 = {
  id: "5f0c7c1e-0000-4000-8000-000000000001",
  name: "Fresh Farms Ltd",
  vatNumber: "GB1",
};

async function fillPo999(amount: string) {
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/Supplier/));
  await user.click(within(screen.getByRole("listbox")).getByText("Fresh Farms Ltd (GB1)"));
  await user.type(screen.getByLabelText(/PO number/), "PO-999");
  await user.type(screen.getByLabelText(/^Amount/), amount);
  await user.click(screen.getByRole("button", { name: "Save PO" }));
}

describe("US3 add-PO form", () => {
  it("us3: refuses 1200.50 with no API call", async () => {
    const onSubmit = vi.fn();
    render(<PurchaseOrderForm suppliers={[S1]} onSubmit={onSubmit} onCancel={vi.fn()} />);

    await fillPo999("1200.50");

    expect(await screen.findByText(/whole number of minor units/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("us3: refuses a PO with no supplier", async () => {
    const onSubmit = vi.fn();
    render(<PurchaseOrderForm suppliers={[S1]} onSubmit={onSubmit} onCancel={vi.fn()} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Save PO" }));

    expect(await screen.findByText("Choose the supplier.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("us3: sends PO-999 for S1 in minor units", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<PurchaseOrderForm suppliers={[S1]} onSubmit={onSubmit} onCancel={vi.fn()} />);

    await fillPo999("120000");

    expect(onSubmit).toHaveBeenCalledWith({
      supplierId: S1.id,
      poNumber: "PO-999",
      amount: 120000,
      currency: "GBP",
    });
  });
});
