import { useState } from "react";

import { formatMoney, formatScore, formatTime, scoreTone } from "../format";
import type { AlertDetail } from "../types";
import { ShapBars } from "./ShapBars";
import { StatusPill } from "./StatusPill";

interface Props {
  detail: AlertDetail | null;
  auditHash: string | null;
  onDecide: (decision: "approve" | "reject", reason: string) => Promise<void>;
}

export function CaseDetail({ detail, auditHash, onDecide }: Props) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  if (!detail) {
    return (
      <section className="panel detail empty">
        <h2>Case detail</h2>
        <p className="muted">Select an alert to inspect the transaction, its explanation, and linked entities.</p>
      </section>
    );
  }

  const { alert, transaction, top_features, prior_cases } = detail;
  const open = alert.status === "open";

  async function submit(decision: "approve" | "reject") {
    if (!reason.trim()) return;
    setBusy(true);
    try {
      await onDecide(decision, reason.trim());
      setReason("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel detail">
      <div className="panel-head">
        <h2>Case {alert.id.slice(0, 8)}</h2>
        <StatusPill status={alert.status} />
      </div>

      <dl className="facts">
        <div>
          <dt>Score</dt>
          <dd className={`big score-${scoreTone(alert.score)}`}>{formatScore(alert.score)}</dd>
        </div>
        <div>
          <dt>Amount</dt>
          <dd>{formatMoney(transaction.amount)}</dd>
        </div>
        <div>
          <dt>Card</dt>
          <dd className="mono">{transaction.card_id}</dd>
        </div>
        <div>
          <dt>When</dt>
          <dd>{formatTime(transaction.event_time)}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd className="mono">{transaction.model_version}</dd>
        </div>
        <div>
          <dt>Prior cases</dt>
          <dd>{prior_cases}</dd>
        </div>
      </dl>

      <h3>Why this score</h3>
      <p className="muted small">
        TreeSHAP contributions in log-odds space. Positive pushes toward fraud.
      </p>
      <ShapBars features={top_features} />

      <h3>Decision</h3>
      {open ? (
        <div className="decision">
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Reason (required, written to the audit log)"
            rows={3}
          />
          <div className="actions">
            <button
              type="button"
              className="approve"
              disabled={busy || !reason.trim()}
              onClick={() => submit("approve")}
            >
              Approve
            </button>
            <button
              type="button"
              className="reject"
              disabled={busy || !reason.trim()}
              onClick={() => submit("reject")}
            >
              Reject
            </button>
          </div>
        </div>
      ) : (
        <p className="muted">
          Decided by {alert.assignee ?? "unknown"}: {alert.reason}
        </p>
      )}

      {auditHash && (
        <p className="audit">
          Audit entry written · hash <span className="mono">{auditHash.slice(0, 16)}…</span>
        </p>
      )}
    </section>
  );
}
