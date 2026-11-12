import type {
  Alert,
  AlertDetail,
  DecisionResult,
  DriftReport,
  Health,
  RetrainingRequest,
  Transaction,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${body}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function getAlerts(params: {
  status?: string;
  minScore?: number;
  limit?: number;
} = {}): Promise<{ alerts: Alert[] }> {
  return request<{ alerts: Alert[] }>(`/alerts${buildAlertQuery(params)}`);
}

export function getAlert(id: string): Promise<AlertDetail> {
  return request<AlertDetail>(`/alerts/${id}`);
}

export function getTransactions(limit = 100): Promise<{ transactions: Transaction[] }> {
  return request<{ transactions: Transaction[] }>(`/transactions?limit=${limit}`);
}

export function getDriftLatest(): Promise<{ report: DriftReport | null }> {
  return request<{ report: DriftReport | null }>("/drift/latest");
}

export function getRetrainingRequests(): Promise<{ requests: RetrainingRequest[] }> {
  return request<{ requests: RetrainingRequest[] }>("/retraining-requests");
}

export function resolveRetrainingRequest(
  id: string,
  body: { status: "approved" | "rejected"; resolved_by: string },
): Promise<{ request: RetrainingRequest }> {
  return request<{ request: RetrainingRequest }>(`/retraining-requests/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function decide(
  id: string,
  body: { decision: "approve" | "reject"; reason: string; analyst: string },
): Promise<DecisionResult> {
  return request<DecisionResult>(`/alerts/${id}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function buildAlertQuery(params: {
  status?: string;
  minScore?: number;
  limit?: number;
}): string {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.minScore !== undefined) search.set("min_score", String(params.minScore));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  const query = search.toString();
  return query ? `?${query}` : "";
}
