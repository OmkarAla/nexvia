# AIML-02 — Architecture

## Flow

```mermaid
flowchart LR
    DICOM[synthetic DICOM<br/>CR + CT] -->|upload| O[(Orthanc<br/>DICOMweb)]
    O -->|stable-studies| W[worker<br/>poll + idempotent]
    W --> M[DenseNet-121<br/>14 findings]
    M --> G[Grad-CAM<br/>top-2 overlays]
    W --> PG[(Postgres<br/>studies, decisions, audit)]
    W --> FS[(overlay PNGs)]
    API[FastAPI] --> PG
    FS --> API
    UI[React + Cornerstone3D] --> API
    UI -->|WADO /instances| O
```

The worker owns inference and writes results once per study. The API is read-only except for the decision endpoint; the viewer fetches pixels directly from Orthanc and results from the API.

## Study processing

```mermaid
sequenceDiagram
    participant O as Orthanc
    participant W as worker
    participant M as DenseNet
    participant C as Grad-CAM
    participant P as Postgres
    participant U as Viewer

    W->>O: /changes?type=stable-studies&since=N
    O-->>W: study UIDs + last cursor
    W->>O: QIDO series + instances
    W->>O: download middle instance (/instances/{uid}/file)
    W->>M: predict 14 findings
    M-->>W: probabilities
    W->>C: top-2 heatmaps
    C-->>W: overlays
    W->>P: upsert study (idempotent by StudyInstanceUID)
    U->>P: GET /studies
    U->>O: wadouri images
    U->>P: POST decision
```

## Idempotency

- The worker cursor (`worker_cursor`) stores the last Orthanc change sequence.
- `studies.id` is the `StudyInstanceUID`; `upsert_study` replaces findings and overlays rather than inserting duplicates.
- Decisions are a conditional update from `analyzed` to `reviewed`, so a second decision returns `409`.

## Audit chain

Each decision appends a row with `hash = SHA256(prev_hash || canonical(payload))` and updates a singleton head row under a row lock. Verification walks the chain and compares the tail to the head. Rewriting both tables is still possible; external anchoring is not implemented.

## Components

| Path | Role |
|---|---|
| `src/nexvia_imaging/data/make_dicom.py` | deterministic synthetic CR/CT studies |
| `src/nexvia_imaging/dicom/client.py` | Orthanc + DICOMweb transport |
| `src/nexvia_imaging/models/classifier.py` | DenseNet-121 inference + Grad-CAM |
| `src/nexvia_imaging/worker/` | polling, processing, cursor |
| `src/nexvia_imaging/api/` | studies, decisions, audit |
| `dashboard/src/components/DicomViewer.tsx` | Cornerstone3D stack viewport |
| `training/train_classifier.py` | NIH ChestX-ray14 training |
