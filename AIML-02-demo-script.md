# AIML-02 — Imaging demo recording script

**URL:** http://localhost:5174
**API:** http://localhost:8001 (for the `/audit` tab)
**Target length:** 5–6 minutes
**Format:** 1080p, 30 fps, narrated. Do not show terminals or tokens.

The stack is already running: 7 studies (6 CR + 1 CT), all analyzed.

---

## Pre-flight (before you hit record)

1. Open two browser tabs:
   - `http://localhost:5174`
   - `http://localhost:8001/audit`
2. Refresh the dashboard. Confirm the study list shows **7 studies**.
3. Hide bookmarks, 100% zoom, close other apps.
4. Test audio, then start the take.

---

## 0:00–0:35 — Opening

**On screen:** header, education banner, study list.

**Say:**

> "This is AIML-02, Nexvia Imaging. A synthetic DICOM study is uploaded to Orthanc; a worker fetches it over DICOMweb, runs a DenseNet-121 classifier for 14 NIH findings, produces Grad-CAM overlays, and stores the result. A radiologist reviews it here and approves or rejects it. Every decision is audited."

> "This is education and research only — synthetic studies and a public research dataset, not a medical device. The banner stays visible on every page."

---

## 0:35–1:05 — Study list

**Do:** point at the list.

**Say:**

> "Seven studies: six chest X-rays and one CT abdomen series with 20 slices. Each shows modality, top finding, and status. Studies are processed once per StudyInstanceUID; the worker uses Orthanc's stable-study feed so it never analyzes a half-uploaded series."

---

## 1:05–2:15 — Open a CR study and inspect findings

**Do:** open **SYNTHETIC CHEST - EDUCATION ONLY - 05** (a CR study).

**Say:**

> "The viewer loads the DICOM pixels from Orthanc, and the AI panel returns 14 ranked findings. The top two here are Effusion at about 12% and Infiltration at about 10%."

> "The model is DenseNet-121 fine-tuned on the official NIH ChestX-ray14 sample — 5,606 images with a patient-level split, mean AUROC 0.775 on the held-out patients."

> "The 0.5 threshold is not calibrated; that's why the panel ranks all findings and highlights the top two rather than declaring a diagnosis."

---

## 2:15–2:45 — Grad-CAM

**Do:** click **Grad-CAM**.

**Say:**

> "This heatmap is Grad-CAM on the final convolutional feature map for the top finding. It shows where the model looked — model attention, not clinical evidence. The limitations page says exactly that."

**Do:** click **Grad-CAM** again to turn it off (optional).

---

## 2:45–3:30 — Decision

**Do:** type a comment, then **Approve**.

Comment to type:

> `no acute cardiopulmonary finding — synthetic demo review`

**Say:**

> "I'll approve with a comment. The status changes to reviewed and an audit hash appears. A second decision on the same study returns 409 — the transition is a conditional update, not a silent overwrite."

---

## 3:30–3:55 — Audit

**Do:** switch to the `/audit` tab.

**Say:**

> "The audit endpoint returns the chain and `valid: true`. Each row hashes the previous hash plus the canonical payload, and a singleton head row stores the tail. Deleting a row breaks verification unless both tables are rewritten."

---

## 3:55–4:40 — CT study and the segmentation caveat

**Do:** open the **CT SYNTHETIC ABDOMEN** study.

**Say:**

> "This is the 20-slice CT series. The viewer shows the middle slice and the classifier still ranks the 14 chest findings — the CT is a pipeline demonstration, not a chest diagnosis."

> "The 3D U-Net spleen segmenter is trained and validated on MSD Task 09 with a Dice of 0.922. On this synthetic phantom, which is out of distribution, it correctly returns no mask, so the viewer hides the segmentation toggle rather than showing a fabricated result. That is deliberate and documented."

---

## 4:40–5:35 — Engineering and evidence

**Say:**

> "The mandated pieces are all present: MONAI 3D U-Net, PyTorch, Orthanc with DICOMweb, Grad-CAM, DVC for the generated data pipeline, Docker Compose, React, and an approve/reject flow with a hash-chained audit log."

> "Tests cover DICOM tags and deterministic UIDs, DICOMweb parsing, worker idempotency, the API and audit chain, the classifier and Grad-CAM shape checks, the segmentation smoke test, and a U-Net resume test — 38 backend tests."

---

## 5:35–6:05 — Close and limits

**Say:**

> "Limits are on the limitations page: one dataset, noisy NLP-mined labels, sample subset, no external validation, no demographic bias analysis, and the synthetic demo CT is out of distribution. The next steps are per-label threshold calibration and an external validation set."

> "That's the pipeline: DICOM in, findings and explanations out, a human decision, and an auditable record."

---

## Click checklist

1. Study list (default)
2. CR study "SYNTHETIC CHEST - EDUCATION ONLY - 05"
3. Grad-CAM on → off
4. Comment → Approve
5. `/audit` tab
6. CT study
7. End

## If something goes wrong

- **List is empty:** refresh; if still empty, tell me — do not re-seed mid-recording.
- **Viewer shows "No DICOM instances":** refresh once. The offline demo path should serve the rendered slice; if it persists, tell me.
- **CT has no "Spleen mask" button:** expected. Do not hunt for it; use the caveat lines above.
- **A page is stale:** `Ctrl+R`.
- **You flub a section:** stop, delete the take, restart from the nearest section. If the CR is already approved, pick another CR study.
