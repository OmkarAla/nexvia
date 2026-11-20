# Reflection - AIML-02 (Nexvia Imaging)

## Name and role

- Name: Omkar Ala (sole intern)
- Role: AI / Machine Learning
- Owned area(s): synthetic DICOM generation, the Orthanc/DICOMweb client, the worker pipeline, DenseNet-121 training, Grad-CAM, the 3D U-Net, the API/audit layer, the Cornerstone viewer, DVC, tests, and docs.

## What I built

- `data/make_dicom.py` - deterministic synthetic CR and CT studies with valid tags and UIDs.
- `dicom/client.py` - DICOMweb QIDO/WADO plus native instance retrieval.
- `models/classifier.py` - DenseNet-121 inference and Grad-CAM.
- `training/train_classifier.py` and `notebooks/train_classifier_colab.ipynb` - NIH ChestX-ray14 training.
- `training/train_unet.py` and `models/segmenter.py` - MONAI 3D U-Net and CT segmentation.
- `worker/` - stable-study polling, idempotent processing, overlays.
- `api/`, `db/`, `audit/` - studies, decisions, and the hash-chained audit log.
- `dashboard/` - React viewer with findings, Grad-CAM, approve/reject.

The decision I would defend: **suppressing the segmentation toggle when the model returns an empty mask** instead of showing a fabricated overlay. The MSD model is out of distribution on the synthetic phantom; hiding a meaningless result is more honest than decorating it.

## What broke

- **DICOM rescale bug.** The generator stored voxels already in HU while also declaring `RescaleIntercept = -1024`, so every CT slice displayed black and the model saw nonsense. Fixed the stored values and regenerated the series.
- **MSD filenames.** Task 09 uses `spleen_*.nii.gz`, not `*_0000.nii.gz`; the loader found zero cases. It now supports both.
- **AppleDouble files.** The MSD tar contained `._spleen_*.nii.gz` metadata files that MONAI tried to read as images. They are filtered and deleted.
- **Dice metric.** The first U-Net run computed Dice on raw logits, so it was frozen at 0.016 and saved epoch-1 weights. Discrete `argmax` + one-hot fixed it.
- **Segmentation collapse.** With small patches the model produced a constant mask. Larger patches (96x96x64) and per-volume Dice diagnostics produced a real 0.922.
- **Cornerstone3D codec runtime failure.** The viewer falls back to a server-rendered slice; the failure is documented rather than hidden.

## What I learned

- I can explain the DICOM hierarchy, DICOMweb, window/level, and why pixel rescale is not optional.
- I can explain Grad-CAM and why it is model attention, not clinical evidence.
- I am still less confident on **domain shift**: I can detect it, but a real external-validation plan is next.

## What I would do differently

- I would build and validate the DICOM → Orthanc round trip before any model work, which is also what the design recommended.
- I would add per-label threshold calibration to the first training run instead of deferring it.

## Evidence

- Commit range: `d2affe0` through the final submission commit.
- Run IDs: `colab-nih-sample-001` (mean AUROC 0.775), `colab-unet-003` (best Dice 0.922).
- Tests: 38 backend tests, including DICOM, worker, API, audit, classifier, Grad-CAM, segmentation, and U-Net resume.
- Demo timestamp: the imaging recording linked from the README.
