import { useCallback, useEffect, useState } from "react";

import {
  decide,
  getAlert,
  getAlerts,
  getDriftLatest,
  getHealth,
  getRetrainingRequests,
  getTransactions,
  resolveRetrainingRequest,
} from "./api";
import { AlertQueue } from "./components/AlertQueue";
import { CaseDetail } from "./components/CaseDetail";
import { LiveFeed } from "./components/LiveFeed";
import { ModelHealth } from "./components/ModelHealth";
import type {
  Alert,
  AlertDetail,
  DriftReport,
  Health,
  RetrainingRequest,
  Transaction,
} from "./types";

type Tab = "cases" | "feed" | "model";

export default function App() {
  const [tab, setTab] = useState<Tab>("cases");
  const [health, setHealth] = useState<Health | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [drift, setDrift] = useState<DriftReport | null>(null);
  const [requests, setRequests] = useState<RetrainingRequest[]>([]);
  const [selected, setSelected] = useState<AlertDetail | null>(null);
  const [status, setStatus] = useState("open");
  const [minScore, setMinScore] = useState(0.5);
  const [auditHash, setAuditHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [alertPage, transactionPage, driftPage, requestPage] = await Promise.all([
        getAlerts({ status: status || undefined, minScore, limit: 100 }),
        getTransactions(80),
        getDriftLatest(),
        getRetrainingRequests(),
      ]);
      setAlerts(alertPage.alerts);
      setTransactions(transactionPage.transactions);
      setDrift(driftPage.report);
      setRequests(requestPage.requests);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, [status, minScore]);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((cause: unknown) => setError(String(cause)));
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function select(alert: Alert) {
    try {
      setSelected(await getAlert(alert.id));
      setAuditHash(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  async function submitDecision(decision: "approve" | "reject", reason: string) {
    if (!selected) return;
    try {
      const result = await decide(selected.alert.id, {
        decision,
        reason,
        analyst: "demo-analyst",
      });
      setAuditHash(result.audit_hash);
      setSelected(await getAlert(selected.alert.id));
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      throw cause;
    }
  }

  async function resolveRequest(id: string, status: "approved" | "rejected") {
    try {
      await resolveRetrainingRequest(id, { status, resolved_by: "demo-analyst" });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            N
          </span>
          <div>
            <h1>Nexvia Fraud Review</h1>
            <p className="muted small">Real-time scoring · analyst case workflow</p>
          </div>
        </div>
        <div className="status">
          <span className={`dot ${health ? "ok" : "down"}`} />
          <span className="muted small">
            {health ? `model ${health.model_version}` : "API unreachable"}
          </span>
        </div>
      </header>

      <div className="banner">
        Demo system · synthetic data · not a production fraud engine
      </div>

      {error && <div className="error">{error}</div>}

      <nav className="tabs" aria-label="Views">
        <button
          type="button"
          className={tab === "cases" ? "active" : ""}
          onClick={() => setTab("cases")}
        >
          Case queue
        </button>
        <button
          type="button"
          className={tab === "feed" ? "active" : ""}
          onClick={() => setTab("feed")}
        >
          Live feed
        </button>
        <button
          type="button"
          className={tab === "model" ? "active" : ""}
          onClick={() => setTab("model")}
        >
          Model health
        </button>
      </nav>

      <main>
        {tab === "feed" && <LiveFeed transactions={transactions} />}
        {tab === "model" && (
          <ModelHealth report={drift} requests={requests} onResolve={resolveRequest} />
        )}
        {tab === "cases" && (
          <div className="split">
            <AlertQueue
              alerts={alerts}
              selectedId={selected?.alert.id ?? null}
              status={status}
              minScore={minScore}
              onSelect={select}
              onStatusChange={setStatus}
              onMinScoreChange={setMinScore}
            />
            <CaseDetail
              key={selected?.alert.id ?? "empty"}
              detail={selected}
              auditHash={auditHash}
              onDecide={submitDecision}
            />
          </div>
        )}
      </main>

      <footer className="muted small">
        Scores are illustrative. Every decision is written to a hash-chained audit log.
      </footer>
    </div>
  );
}
