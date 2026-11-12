import { driftTone, formatTime } from "../format";
import type { DriftReport, RetrainingRequest } from "../types";
import { StatusPill } from "./StatusPill";

interface Props {
  report: DriftReport | null;
  requests: RetrainingRequest[];
  onResolve: (id: string, status: "approved" | "rejected") => Promise<void>;
}

export function ModelHealth({ report, requests, onResolve }: Props) {
  if (!report) {
    return (
      <section className="panel">
        <div className="panel-head">
          <h2>Model health</h2>
        </div>
        <p className="muted">
          No drift report yet. The scheduled `drift-monitor` job writes one after at least 50
          scored transactions exist.
        </p>
      </section>
    );
  }

  const tone = driftTone(report.drift_share);
  const open = requests.filter((request) => request.status === "open");

  return (
    <div className="model-grid">
      <section className="panel">
        <div className="panel-head">
          <h2>Feature drift</h2>
          <span className="muted small">{report.method}</span>
        </div>

        <div className={`drift-hero drift-${tone}`}>
          <span className="drift-value">{(report.drift_share * 100).toFixed(1)}%</span>
          <span className="muted small">of features drifted</span>
        </div>
        <div className="drift-track">
          <div
            className={`drift-fill drift-${tone}`}
            style={{ width: `${Math.min(100, report.drift_share * 100)}%` }}
          />
        </div>
        <p className="muted small">
          Reference {report.n_reference} rows · current {report.n_current} rows · generated{" "}
          {formatTime(report.created_at)}
        </p>

        <table className="feed drift-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th className="right">p-value</th>
              <th className="right">Status</th>
            </tr>
          </thead>
          <tbody>
            {report.columns.map((column) => (
              <tr key={column.column}>
                <td>{column.column.replaceAll("_", " ")}</td>
                <td className="right mono">{column.p_value.toExponential(2)}</td>
                <td className="right">
                  <span className={`pill ${column.drifted ? "pill-rejected" : "pill-approved"}`}>
                    {column.drifted ? "drifted" : "stable"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Retraining requests</h2>
          <span className="muted small">{open.length} open</span>
        </div>
        <p className="muted small">
          A request is a human decision. Nothing retrains or promotes automatically.
        </p>

        {requests.length === 0 ? (
          <p className="muted">No requests raised.</p>
        ) : (
          <ul className="request-list">
            {requests.map((request) => (
              <li key={request.id} className="request">
                <div className="request-main">
                  <span>{request.reason}</span>
                  <span className="muted small">
                    {formatTime(request.created_at)}
                    {request.resolved_by ? ` · ${request.resolved_by}` : ""}
                  </span>
                </div>
                <div className="request-actions">
                  <StatusPill status={request.status} />
                  {request.status === "open" && (
                    <>
                      <button type="button" onClick={() => void onResolve(request.id, "approved")}>
                        Approve
                      </button>
                      <button type="button" onClick={() => void onResolve(request.id, "rejected")}>
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
