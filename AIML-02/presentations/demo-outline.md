# 10-minute demo outline — AIML-02

## 0:00–0:40 — Frame

- What it is: DICOM study → AI findings + Grad-CAM → radiologist approve/reject → audit.
- What it is not: not a medical device, synthetic demo studies, public-data model.
- What to watch: the seams — DICOM correctness, idempotent worker, audit chain.

## 0:40–2:00 — Architecture

- Orthanc owns DICOM/DICOMweb; Postgres owns results and decisions.
- Worker polls stable studies, runs DenseNet-121 + Grad-CAM, upserts once per StudyInstanceUID.
- Viewer reads pixels from Orthanc and results from FastAPI.
- Synthetic studies are generated with deterministic UIDs and explicit `SYNTHETIC` tags.

## 2:00–4:30 — Live demo

1. Start Compose; the seed job uploads 6 CR studies and one 20-slice CT.
2. Study list: modality, status, top finding.
3. Open a CR study; toggle the Grad-CAM overlay; point out it is model attention, not evidence.
4. Inspect the 14 ranked findings and their probabilities.
5. Write a comment, approve; show the audit hash.
6. `GET /audit` returns `valid: true`.

## 4:30–6:00 — Model evidence

- NIH ChestX-ray14 official sample, 5,606 images, patient-level split.
- Mean AUROC 0.775 on 593 test rows; per-label table (Effusion 0.83, Edema 0.88, Pneumonia 0.61).
- Why AUROC: threshold-free and robust to label imbalance.
- Threshold caveat: sensitivity at 0.5 is near zero for rare findings; calibration is next.

## 6:00–7:00 — Correctness stories

- Deterministic UIDs: the same study twice is the same Orthanc object.
- Worker idempotency: reruns replace findings, not duplicate rows.
- Half-uploaded studies are excluded by `stable-studies`.
- Second decision returns 409.

## 7:00–8:00 — Engineering

- DVC stage regenerates the demo DICOM set; committed fixtures keep the offline demo working.
- Tests: DICOM tags, DICOMweb parsing, worker, API, audit, Grad-CAM, U-Net smoke.
- Compose: Orthanc, Postgres, API, worker, dashboard.

## 8:00–9:00 — Limits and next

- Single dataset, sample subset, label noise, no external validation, no bias analysis.
- 3D U-Net training code + Colab notebook; serving integration is pending a trained checkpoint.
- Cornerstone3D path with rendered-slice fallback for constrained environments.

## 9:00–10:00 — Questions

Keep `docs/api.md`, `docs/model-card.md`, and `docs/limitations.md` open.
