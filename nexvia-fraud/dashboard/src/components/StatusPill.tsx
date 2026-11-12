import type { AlertStatus } from "../types";

export function StatusPill({ status }: { status: AlertStatus | "open" }) {
  return <span className={`pill pill-${status}`}>{status}</span>;
}
