import { useState } from "react";

import type { Study } from "../types";

interface Props {
  study: Study;
  onDecision: (decision: "approve" | "reject", comment: string) => Promise<void>;
  auditHash: string | null;
}

export function DecisionForm({ study, onDecision, auditHash }: Props) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const reviewed = study.status === "reviewed";

  async function submit(decision: "approve" | "reject") {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      await onDecision(decision, comment.trim());
      setComment("");
    } catch {
      // keep the comment so the reviewer can retry
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="decision">
      {reviewed ? (
        <p className="muted">
          Reviewed · model {study.model_version}
        </p>
      ) : (
        <>
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Radiologist comment (required, written to the audit log)"
            rows={3}
            maxLength={1024}
          />
          <div className="actions">
            <button
              type="button"
              className="approve"
              disabled={busy || !comment.trim()}
              onClick={() => void submit("approve")}
            >
              Approve
            </button>
            <button
              type="button"
              className="reject"
              disabled={busy || !comment.trim()}
              onClick={() => void submit("reject")}
            >
              Reject
            </button>
          </div>
        </>
      )}
      {auditHash && (
        <p className="audit">
          Audit entry · <span className="mono">{auditHash.slice(0, 16)}…</span>
        </p>
      )}
    </div>
  );
}
