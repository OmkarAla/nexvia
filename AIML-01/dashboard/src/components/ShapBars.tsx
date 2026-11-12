import type { FeatureContribution } from "../types";

interface Props {
  features: FeatureContribution[];
}

export function ShapBars({ features }: Props) {
  if (features.length === 0) {
    return <p className="muted">No explanation stored for this transaction.</p>;
  }

  const max = Math.max(...features.map((item) => Math.abs(item.contribution)), 1e-9);

  return (
    <ul className="shap" aria-label="Top feature contributions">
      {features.map((item) => {
        const width = (Math.abs(item.contribution) / max) * 100;
        const tone = item.contribution >= 0 ? "positive" : "negative";
        return (
          <li key={item.feature} className="shap-row">
            <span className="shap-feature">{item.feature.replaceAll("_", " ")}</span>
            <span className="shap-bar-track">
              <span className={`shap-bar ${tone}`} style={{ width: `${width}%` }} />
            </span>
            <span className={`shap-value ${tone}`}>
              {item.contribution >= 0 ? "+" : ""}
              {item.contribution.toFixed(3)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
