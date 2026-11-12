import { formatScore, formatTime, scoreTone } from "../format";
import type { Alert } from "../types";
import { StatusPill } from "./StatusPill";

interface Props {
  alerts: Alert[];
  selectedId: string | null;
  status: string;
  minScore: number;
  onSelect: (alert: Alert) => void;
  onStatusChange: (status: string) => void;
  onMinScoreChange: (score: number) => void;
}

export function AlertQueue({
  alerts,
  selectedId,
  status,
  minScore,
  onSelect,
  onStatusChange,
  onMinScoreChange,
}: Props) {
  return (
    <section className="panel queue">
      <div className="panel-head">
        <h2>Case queue</h2>
        <span className="muted">{alerts.length} shown</span>
      </div>

      <div className="filters">
        <label>
          Status
          <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
            <option value="open">Open</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </select>
        </label>
        <label>
          Min score
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={minScore}
            onChange={(event) => onMinScoreChange(Number(event.target.value))}
          />
        </label>
      </div>

      <ol className="alert-list">
        {alerts.map((alert) => (
          <li key={alert.id}>
            <button
              type="button"
              className={`alert-row ${selectedId === alert.id ? "selected" : ""}`}
              onClick={() => onSelect(alert)}
            >
              <span className={`score-dot score-${scoreTone(alert.score)}`} />
              <span className="alert-main">
                <span className="mono">{alert.transaction_id}</span>
                <span className="muted">{formatTime(alert.created_at)}</span>
              </span>
              <span className="alert-side">
                <span className={`score-${scoreTone(alert.score)}`}>{formatScore(alert.score)}</span>
                <StatusPill status={alert.status} />
              </span>
            </button>
          </li>
        ))}
      </ol>
      {alerts.length === 0 && <p className="muted pad">No alerts match these filters.</p>}
    </section>
  );
}
