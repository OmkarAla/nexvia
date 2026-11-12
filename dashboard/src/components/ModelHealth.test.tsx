import { fireEvent, render, screen } from "@testing-library/react";

import type { DriftReport, RetrainingRequest } from "../types";
import { ModelHealth } from "./ModelHealth";

const report: DriftReport = {
  id: "r1",
  created_at: "2026-01-05T10:00:00Z",
  drift_share: 0.4,
  dataset_drift: true,
  n_reference: 3500,
  n_current: 120,
  method: "evidently:DataDriftPreset",
  columns: [
    { column: "amount_zscore", p_value: 0.001, drifted: true },
    { column: "velocity_1h", p_value: 0.7, drifted: false },
  ],
};

const request: RetrainingRequest = {
  id: "q1",
  drift_report_id: "r1",
  reason: "drift share 0.40 >= 0.30",
  status: "open",
  created_at: "2026-01-05T10:00:00Z",
  resolved_at: null,
  resolved_by: null,
};

describe("ModelHealth", () => {
  it("renders the drift share and per-feature status", () => {
    render(<ModelHealth report={report} requests={[request]} onResolve={async () => {}} />);

    expect(screen.getByText("40.0%")).toBeInTheDocument();
    expect(screen.getByText("amount zscore")).toBeInTheDocument();
    expect(screen.getByText("drifted")).toBeInTheDocument();
    expect(screen.getByText("stable")).toBeInTheDocument();
  });

  it("resolves an open request", () => {
    const calls: Array<[string, string]> = [];
    render(
      <ModelHealth
        report={report}
        requests={[request]}
        onResolve={async (id, status) => {
          calls.push([id, status]);
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(calls).toEqual([["q1", "approved"]]);
  });

  it("shows an empty state before the first report", () => {
    render(<ModelHealth report={null} requests={[]} onResolve={async () => {}} />);
    expect(screen.getByText(/no drift report yet/i)).toBeInTheDocument();
  });
});
