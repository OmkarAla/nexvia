import { formatProbability, probabilityTone } from "../format";
import type { Finding } from "../types";

interface Props {
  findings: Finding[];
  top: number;
}

export function FindingsPanel({ findings, top }: Props) {
  return (
    <div className="findings">
      <p className="muted small">
        Ranked model outputs. Grad-CAM shows model attention, not clinical evidence.
      </p>
      <ul>
        {findings.map((finding, index) => (
          <li key={finding.label} className={index < top ? "top-finding" : ""}>
            <span className="finding-label">{finding.label.replaceAll("_", " ")}</span>
            <span className="finding-track">
              <span
                className={`finding-fill score-${probabilityTone(finding.probability)}`}
                style={{ width: `${Math.min(100, finding.probability * 100)}%` }}
              />
            </span>
            <span className={`finding-value score-${probabilityTone(finding.probability)}`}>
              {formatProbability(finding.probability)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
