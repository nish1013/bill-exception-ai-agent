import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IgnoreForm } from "./IgnoreForm";

async function ignoreWith(reason: string) {
  const user = userEvent.setup();
  if (reason) {
    await user.type(screen.getByLabelText(/Reason/), reason);
  }
  await user.click(screen.getByRole("button", { name: "Ignore" }));
}

describe("US9 ignore form", () => {
  it.each(["", "   "])("us9: refuses the reason %j with no API call", async (reason) => {
    const onSubmit = vi.fn();
    render(<IgnoreForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await ignoreWith(reason);

    expect(await screen.findByText("Enter a reason.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("us9: refuses a reason of 1001 characters", async () => {
    const onSubmit = vi.fn();
    render(<IgnoreForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByLabelText(/Reason/));
    await user.paste("x".repeat(1001));
    await user.click(screen.getByRole("button", { name: "Ignore" }));

    expect(await screen.findByText("Enter at most 1000 characters.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("us9: sends the trimmed reason", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<IgnoreForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await ignoreWith("  Agreed with supplier ");

    expect(onSubmit).toHaveBeenCalledWith("Agreed with supplier");
  });

  it("us9: shows the API conflict in the form", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("This conflicts with the current data."));
    render(<IgnoreForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await ignoreWith("Agreed with supplier");

    expect(await screen.findByRole("alert")).toHaveTextContent("This conflicts");
  });
});
