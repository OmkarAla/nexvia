# AIML-02 — Nexvia Imaging

AI-assisted medical imaging review. Submission folder: `AIML-02` (imaging brief, course project 1).

> **Education and research only. Not a medical device. Do not use for clinical decisions.**

## Status

| Piece | State |
|---|---|
| Synthetic DICOM generator (CR + CT) | done — `src/nexvia_imaging/data/make_dicom.py` |
| Orthanc + DICOMweb client | done — `src/nexvia_imaging/dicom/client.py` |
| Orthanc/Postgres Compose | done |
| DenseNet-121 training (NIH sample, Colab) | done — `training/train_classifier.py` + `notebooks/train_classifier_colab.ipynb` |
| Classifier + Grad-CAM serving | next |
| Worker, API, audit | next |
| Cornerstone3D viewer | next |
| 3D U-Net (MSD spleen) | depth phase |
| DVC | depth phase |

## Quickstart (data + Orthanc)

```bash
docker compose up -d orthanc postgres
python scripts/upload_dicoms.py        # pushes the committed synthetic studies
```

Orthanc API: <http://localhost:8042>. The committed demo set is 6 CR studies + one 20-slice CT series, all tagged `SYNTHETIC` / `EDUCATION ONLY`.

## Training on Colab

The trainer lives in `training/train_classifier.py`; the notebook is a thin driver. It uses the **official NIH ChestX-ray14 sample** (5,606 images, 14 findings) with a patient-level split.

1. Open `notebooks/train_classifier_colab.ipynb` in Colab.
2. Add `KAGGLE_API_TOKEN` to Colab Secrets (never paste it into a cell).
3. Run all cells. On a free T4: ~10–20 minutes for 5 epochs.
4. Download `model.pt` and `metrics.json`, then place them in `artifacts/demo/`.

Local smoke run (no GPU, tiny synthetic set) is covered by `tests/test_train_classifier.py`.

## Data

See the repository-level [`docs/data-setup.md`](../docs/data-setup.md). The full NIH archive is ~42 GB; the sample is the default for the demo. The synthetic studies are committed; no dataset is redistributed.

## Design

Scope and build order: [`docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md`](../docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md) §6. Plan: [`docs/superpowers/plans/2026-11-13-imaging-vertical-slice.md`](../docs/superpowers/plans/2026-11-13-imaging-vertical-slice.md).
