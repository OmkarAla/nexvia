import { formatProbability, formatTime, probabilityTone } from "../format";
import type { Study } from "../types";

interface Props {
  studies: Study[];
  selectedId: string | null;
  status: string;
  onStatusChange: (status: string) => void;
  onSelect: (study: Study) => void;
}

export function StudyList({ studies, selectedId, status, onStatusChange, onSelect }: Props) {
  return (
    <section className="panel list-panel">
      <div className="panel-head">
        <h2>Studies</h2>
        <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
          <option value="">All</option>
          <option value="analyzed">Analyzed</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </div>

      <ul className="study-list">
        {studies.map((study) => (
          <li key={study.id}>
            <button
              type="button"
              className={`study-row ${selectedId === study.id ? "selected" : ""}`}
              onClick={() => onSelect(study)}
            >
              <span className={`modality modality-${study.modality.toLowerCase()}`}>
                {study.modality}
              </span>
              <span className="study-main">
                <span>{study.description || "Synthetic study"}</span>
                <span className="muted small">{formatTime(study.updated_at)}</span>
              </span>
              <span className="study-side">
                {study.findings[0] && (
                  <span className={`score-${probabilityTone(study.findings[0].probability)}`}>
                    {formatProbability(study.findings[0].probability)}
                  </span>
                )}
                <span className={`pill pill-${study.status}`}>{study.status}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {studies.length === 0 && <p className="muted pad">No studies yet. Uploading…</p>}
    </section>
  );
}
