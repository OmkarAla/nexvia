export type AlertStatus = "open" | "approved" | "rejected";

export interface Alert {
  id: string;
  transaction_id: string;
  score: number;
  status: AlertStatus;
  reason: string | null;
  assignee: string | null;
  created_at: string;
}

export interface Transaction {
  transaction_id: string;
  card_id: string;
  event_time: string;
  amount: number;
  score: number;
  mode: string;
  model_version: string;
  features: Record<string, number>;
}

export interface FeatureContribution {
  feature: string;
  value: number;
  contribution: number;
}

export interface AlertDetail {
  alert: Alert;
  transaction: Transaction;
  top_features: FeatureContribution[];
  prior_cases: number;
}

export interface DecisionResult {
  alert: Alert;
  decision_id: string;
  audit_hash: string;
}

export interface Health {
  status: string;
  model_version: string;
}

export interface DriftColumn {
  column: string;
  score: number;
  method: string;
  drifted: boolean;
}

export interface DriftReport {
  id: string;
  created_at: string;
  drift_share: number;
  dataset_drift: boolean;
  n_reference: number;
  n_current: number;
  method: string;
  columns: DriftColumn[];
}

export type RetrainingStatus = "open" | "approved" | "rejected";

export interface RetrainingRequest {
  id: string;
  drift_report_id: string;
  reason: string;
  status: RetrainingStatus;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
}
