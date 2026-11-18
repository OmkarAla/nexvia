"""Study processing: DICOM -> classifier -> Grad-CAM -> database."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image

from nexvia_imaging.db.repo import upsert_study


def to_display_image(dataset) -> Image.Image:
    pixels = dataset.pixel_array.astype(np.float64)
    slope = float(getattr(dataset, "RescaleSlope", 1) or 1)
    intercept = float(getattr(dataset, "RescaleIntercept", 0) or 0)
    values = pixels * slope + intercept

    modality = str(getattr(dataset, "Modality", ""))
    if modality == "CT":
        level, width = 40.0, 400.0
        low, high = level - width / 2, level + width / 2
    else:
        low, high = float(values.min()), float(values.max())
        if high <= low:
            high = low + 1.0

    scaled = np.clip((values - low) / (high - low), 0.0, 1.0)
    return Image.fromarray(np.uint8(scaled * 255), mode="L").convert("RGB")


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def process_study(
    study_uid: str,
    client,
    session_factory,
    classifier,
    overlay_dir: str | Path,
) -> dict:
    series = client.study_series(study_uid)
    if not series:
        raise ValueError(f"study {study_uid} has no series")

    series_uid = series[0]["series_uid"]
    instances = client.series_instances(study_uid, series_uid)
    if not instances:
        raise ValueError(f"series {series_uid} has no instances")

    dataset = client.download_instance(instances[len(instances) // 2])
    image = to_display_image(dataset)
    findings = classifier.predict(image)
    top_findings = findings[:2]

    overlay_root = Path(overlay_dir)
    overlay_paths: list[str] = []
    for finding in top_findings:
        label_index = classifier.labels.index(finding.label)
        cam = classifier.gradcam(image, label_index=label_index, size=image.size)
        overlay = classifier.overlay(image, cam)
        relative = Path(study_uid) / f"{_slug(finding.label)}.png"
        target = overlay_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        overlay.save(target)
        overlay_paths.append(str(relative).replace("\\", "/"))

    payload = {
        "study_uid": study_uid,
        "modality": str(getattr(dataset, "Modality", "")),
        "description": str(getattr(dataset, "StudyDescription", "")),
        "n_instances": len(instances),
        "status": "analyzed",
        "findings": [
            {"label": finding.label, "probability": finding.probability} for finding in findings
        ],
        "overlays": overlay_paths,
        "model_version": classifier.model_version,
    }

    with session_factory() as session:
        upsert_study(session, payload)
    return payload
