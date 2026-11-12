import { render, screen } from "@testing-library/react";

import { ShapBars } from "./ShapBars";

describe("ShapBars", () => {
  it("renders one row per feature with signed values", () => {
    render(
      <ShapBars
        features={[
          { feature: "device_share_count", value: 4, contribution: 0.42 },
          { feature: "amount_zscore", value: 2.1, contribution: -0.13 },
        ]}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("device share count")).toBeInTheDocument();
    expect(screen.getByText("+0.420")).toBeInTheDocument();
    expect(screen.getByText("-0.130")).toBeInTheDocument();
  });

  it("shows an empty state when there is no explanation", () => {
    render(<ShapBars features={[]} />);
    expect(screen.getByText(/no explanation stored/i)).toBeInTheDocument();
  });
});
