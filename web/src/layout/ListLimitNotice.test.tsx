import { render, screen } from "@testing-library/react";

import { ListLimitNotice } from "./ListLimitNotice";

describe("D15 list limit notice", () => {
  it("d15: 500 of 612 shows the hidden rows", () => {
    render(<ListLimitNotice shown={500} total={612} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Showing 500 of 612. Narrow the filter to see the rest.",
    );
  });

  it.each([
    [500, 500],
    [3, 3],
    [0, 0],
  ])("d15: %d of %d shows no notice", (shown, total) => {
    render(<ListLimitNotice shown={shown} total={total} />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
