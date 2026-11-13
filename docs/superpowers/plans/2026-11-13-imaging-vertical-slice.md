# Imaging Vertical Slice Implementation Plan (AIML-02 / course project 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One end-to-end imaging path: synthetic DICOM → Orthanc → worker (classifier + Grad-CAM) → Postgres → API → Cornerstone3D viewer → approve/reject with audit.

**Architecture:** A Python package (`nexvia_imaging`) with a DICOM generator, a DICOMweb client, a polling worker, a model wrapper, and an API. Orthanc owns DICOM storage and DICOMweb; Postgres owns results, decisions, and the audit chain. The viewer talks to Orthanc DICOMweb for pixels and to the API for AI results.

**Tech Stack:** Python 3.11, pydicom, httpx, FastAPI, SQLAlchemy, (later) torch/torchvision/MONAI, Orthanc 24.x, React + Cornerstone3D, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md` §6, §12 item 4.

## Global Constraints

- Education only; every study is synthetic and labeled as such.
- No PHI. PatientName/PatientID are explicitly synthetic.
- Idempotency key: `StudyInstanceUID + SOPInstanceUID`.
- Worker polls only `stable-studies`; never processes a half-uploaded series.
- Grad-CAM is described as model attention, not clinical evidence.
- CPU-only inference; seconds per study is acceptable for the demo.
- Committed demo studies must keep the repo small (< 5 MB total).

## Review Focus

- **Half-uploaded study:** stable-only polling prevents analysis of incomplete series.
- **Re-processing:** the same study twice must not duplicate result rows.
- **Missing pixels:** a study with no instances returns a clear error.
- **DICOM correctness:** transfer syntax, pixel representation, and rescale values round-trip.
- **Audit:** a decision writes one chained entry; the chain verifies.

---

### Task 1: Scaffold and config

**Files:** `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `src/nexvia_imaging/{__init__,config}.py`, `tests/test_config.py`.

- `Settings`: `database_url`, `orthanc_url`, `orthanc_user`, `orthanc_password`, `demo_data_dir`, `model_dir`, `poll_interval`.
- TDD: defaults + env override; commit.

### Task 2: Synthetic DICOM generator

**Files:** `src/nexvia_imaging/data/make_dicom.py`, `tests/test_make_dicom.py`, `data/demo/`.

- `generate_cr_study(index, seed) -> list[Dataset]` (one 512×512 CR instance).
- `generate_ct_series(index, seed, slices=20) -> list[Dataset]` (128×128 CT slices with a synthetic spleen).
- Deterministic UIDs via `uuid5`; all tags include `SYNTHETIC` and `EDUCATION ONLY`.
- Manifest: `study_uid, modality, description, n_instances`.
- TDD: SOP class, tags, determinism, CT rescale, pixel shapes; generate and commit demo files.

### Task 3: DICOMweb client and Orthanc

**Files:** `src/nexvia_imaging/dicom/client.py`, `docker-compose.yml`, `orthanc.json`, `tests/test_dicom_client.py`.

- `OrthancClient.find_stable_studies()`, `.study_metadata(study_uid)`, `.download_instance(study_uid, series_uid, sop_uid) -> Dataset` using QIDO/WADO.
- `stable-studies` change feed + idempotency helper.
- Tests with `httpx.MockTransport` (no real Orthanc).
- Compose: `orthanc` with DICOMweb, `postgres`, `api`, `worker`, `dashboard` placeholders.

### Task 4: Worker and model

**Files:** `src/nexvia_imaging/worker/{main,pipeline}.py`, `src/nexvia_imaging/models/classifier.py`, `tests/test_worker.py`.

- `classify(study, model) -> list[Finding]`; 14-label output.
- Grad-CAM overlay PNG per top-2 findings.
- Idempotent upsert by study UID.
- Tests with a fake model (no torch) for the pipeline; a smoke test for the real model behind a marker.

### Task 5: API, DB, audit

**Files:** `src/nexvia_imaging/{db,api}/**`, `tests/test_api.py`.

- `GET /studies`, `GET /studies/{uid}`, `POST /studies/{uid}/decision`, `GET /audit`.
- Hash-chained audit reused from the fraud pattern.
- Decision requires a comment; second decision 409.

### Task 6: Viewer

**Files:** `dashboard/**`.

- Cornerstone3D DICOMweb loader against Orthanc.
- Study list, viewer, AI panel (ranked findings, Grad-CAM toggle), approve/reject.

### Task 7: Docs and demo

- README, model card, limitations, architecture diagram, demo outline, screenshots.
- Compose up on synthetic studies; record the flow.

## Self-Review Notes

- Spec coverage: DICOM/Orthanc, classifier, Grad-CAM, audit, viewer. 3D U-Net and DVC are the depth phase.
- Review Focus is covered by Tasks 2–5.
- The first shippable milestone is Tasks 1–3 (data + Orthanc round trip) before any model work, matching the spec's risk mitigation.
