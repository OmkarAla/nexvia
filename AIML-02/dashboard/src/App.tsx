import { useCallback, useEffect, useState } from "react";

import { decide, getStudies, getStudy, overlayUrl } from "./api";
import { DecisionForm } from "./components/DecisionForm";
import { DicomViewer } from "./components/DicomViewer";
import { FindingsPanel } from "./components/FindingsPanel";
import { StudyList } from "./components/StudyList";
import type { Study } from "./types";

export default function App() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Study | null>(null);
  const [overlayIndex, setOverlayIndex] = useState(0);
  const [showOverlay, setShowOverlay] = useState(true);
  const [auditHash, setAuditHash] = useState<string | null>(null);
  const [modelVersion, setModelVersion] = useState("…");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const page = await getStudies(status || undefined);
      setStudies(page.studies);
      setSelected((current) => {
        if (!current) return current;
        return page.studies.find((study) => study.id === current.id) ?? current;
      });
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, [status]);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/health`)
      .then((response) => response.json())
      .then((body: { model_version: string }) => setModelVersion(body.model_version))
      .catch(() => setModelVersion("API offline"));
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    setOverlayIndex(0);
    setAuditHash(null);
  }, [selected?.id]);

  async function submitDecision(decision: "approve" | "reject", comment: string) {
    if (!selected) return;
    const result = await decide(selected.id, {
      decision,
      comment,
      reviewer: "demo-radiologist",
    });
    setAuditHash(result.audit_hash);
    const fresh = await getStudy(selected.id);
    setSelected(fresh.study);
    await refresh();
  }

  const overlay =
    selected && selected.overlays.length > 0 && showOverlay
      ? overlayUrl(selected.overlays[Math.min(overlayIndex, selected.overlays.length - 1)])
      : null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">N</span>
          <div>
            <h1>Nexvia Imaging Review</h1>
            <p className="muted small">DICOM · AI findings · radiologist decision</p>
          </div>
        </div>
        <span className="muted small mono">model {modelVersion}</span>
      </header>

      <div className="banner">
        For education and research only. Not a medical device. Do not use for clinical decisions.
      </div>

      {error && <div className="error">{error}</div>}

      <main className="layout">
        <StudyList
          studies={studies}
          selectedId={selected?.id ?? null}
          status={status}
          onStatusChange={setStatus}
          onSelect={setSelected}
        />

        {selected ? (
          <div className="detail">
            <section className="panel viewer-panel">
              <div className="panel-head">
                <div>
                  <h2>{selected.description || "Synthetic study"}</h2>
                  <p className="muted small mono">{selected.id}</p>
                </div>
                <div className="viewer-controls">
                  {selected.overlays.length > 0 && (
                    <>
                      <button
                        type="button"
                        className={showOverlay ? "active" : ""}
                        onClick={() => setShowOverlay((value) => !value)}
                      >
                        Grad-CAM
                      </button>
                      {selected.overlays.length > 1 && showOverlay && (
                        <select
                          value={overlayIndex}
                          onChange={(event) => setOverlayIndex(Number(event.target.value))}
                        >
                          {selected.overlays.map((_, index) => (
                            <option key={index} value={index}>
                              Finding {index + 1}
                            </option>
                          ))}
                        </select>
                      )}
                    </>
                  )}
                </div>
              </div>

              <DicomViewer studyUid={selected.id} overlay={overlay} />
            </section>

            <div className="detail-grid">
              <section className="panel">
                <div className="panel-head">
                  <h2>AI findings</h2>
                  <span className={`pill pill-${selected.status}`}>{selected.status}</span>
                </div>
                <FindingsPanel findings={selected.findings} top={2} />
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2>Review</h2>
                  <span className="muted small mono">{selected.n_instances} instances</span>
                </div>
                <DecisionForm
                  study={selected}
                  onDecision={submitDecision}
                  auditHash={auditHash}
                />
              </section>
            </div>
          </div>
        ) : (
          <section className="panel empty">
            <h2>Select a study</h2>
            <p className="muted">
              Studies appear after Orthanc receives them and the worker finishes inference.
            </p>
          </section>
        )}
      </main>

      <footer className="muted small">
        Synthetic demo data. Decisions are written to a hash-chained audit log.
      </footer>
    </div>
  );
}
