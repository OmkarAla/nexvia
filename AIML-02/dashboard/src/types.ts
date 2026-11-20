export interface Finding {
  label: string;
  probability: number;
}

export type StudyStatus = "pending" | "analyzed" | "reviewed";

export interface Study {
  id: string;
  modality: string;
  description: string;
  n_instances: number;
  status: StudyStatus;
  findings: Finding[];
  overlays: string[];
  segmentation: string | null;
  model_version: string;
  created_at: string;
  updated_at: string;
}

export interface DecisionResult {
  study: Study;
  decision: {
    id: string;
    study_id: string;
    decision: "approve" | "reject";
    comment: string;
    reviewer: string;
    created_at: string;
  };
  audit_hash: string;
}
