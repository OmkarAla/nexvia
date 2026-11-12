export function formatScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

export function formatMoney(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
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

export function scoreTone(score: number): "high" | "medium" | "low" {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

export function driftTone(share: number): "stable" | "watch" | "drifted" {
  if (share < 0.1) return "stable";
  if (share < 0.3) return "watch";
  return "drifted";
}
