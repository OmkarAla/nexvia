export function formatProbability(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function probabilityTone(value: number): "high" | "medium" | "low" {
  if (value >= 0.7) return "high";
  if (value >= 0.4) return "medium";
  return "low";
}
