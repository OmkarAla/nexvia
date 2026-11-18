# AIML-02 — Limitations

- **Education only.** No clinical use, no regulatory clearance, no PHI.
- **Single dataset.** NIH ChestX-ray14 sample (5,606 images); labels were NLP-mined from reports and carry noise. No external validation.
- **Sample subset.** The full archive is ~42 GB; the demo trains on the official sample. Metrics are not comparable to full-dataset papers.
- **No calibration.** Sensitivities at a fixed 0.5 threshold are near zero because of imbalance. Per-label thresholds must be fit on validation before any deployment-shaped claim.
- **No bias analysis.** NIH metadata is incomplete; subgroup performance by age, sex, or scanner is not measured.
- **Grad-CAM is attention, not evidence.** It is computed at the final feature map for the top two findings and can be degenerate on out-of-distribution images.
- **Synthetic demo studies.** The committed CR/CT series are procedurally generated, not real acquisitions. DICOM tags are structurally correct but the pixels are not representative of scanner variation.
- **No 3D U-Net yet.** The mandated spleen segmentation and MONAI pipeline are the depth phase.
- **No DVC yet.** Dataset pointers and a reproducible fetch are the depth phase.
- **Single-node demo.** Orthanc, Postgres, the worker, and the API are single replicas. No TLS, no auth, no retention policy.
- **Audit chain caveat.** Tampering that rewrites both `audit_log` and `audit_head` is not detectable without external anchoring.
