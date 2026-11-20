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


def _ct_volume(datasets: list) -> np.ndarray:
    ordered = sorted(datasets, key=lambda item: int(getattr(item, "InstanceNumber", 0)))
    slices = [
        dataset.pixel_array.astype(np.float32) * float(getattr(dataset, "RescaleSlope", 1) or 1)
        + float(getattr(dataset, "RescaleIntercept", 0) or 0)
        for dataset in ordered
    ]
    return np.stack(slices)


def process_study(
    study_uid: str,
    client,
    session_factory,
    classifier,
    overlay_dir: str | Path,
    segmenter=None,
) -> dict:
    series = client.study_series(study_uid)
    if not series:
        raise ValueError(f"study {study_uid} has no series")

    series_uid = series[0]["series_uid"]
    instances = client.series_instances(study_uid, series_uid)
    if not instances:
        raise ValueError(f"series {series_uid} has no instances")

    middle_dataset = client.download_instance(instances[len(instances) // 2])
    modality = str(getattr(middle_dataset, "Modality", ""))
    image = to_display_image(middle_dataset)
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

    segmentation_path: str | None = None
    if modality == "CT" and segmenter is not None:
        datasets = [client.download_instance(uid) for uid in instances]
        volume = _ct_volume(datasets)
        mask = segmenter.segment(volume)
        if int(mask.sum()) > 0:
            middle_index = min(len(mask) - 1, len(mask) // 2)
            ordered = sorted(
                datasets, key=lambda item: int(getattr(item, "InstanceNumber", 0))
            )
            display = to_display_image(ordered[middle_index])
            segmentation = segmenter.overlay_slice(display, mask[middle_index])
            relative = Path(study_uid) / "segmentation.png"
            target = overlay_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            segmentation.save(target)
            segmentation_path = str(relative).replace("\\", "/")

    payload = {
        "study_uid": study_uid,
        "modality": modality,
        "description": str(getattr(middle_dataset, "StudyDescription", "")),
        "n_instances": len(instances),
        "status": "analyzed",
        "findings": [
            {"label": finding.label, "probability": finding.probability} for finding in findings
        ],
        "overlays": overlay_paths,
        "segmentation": segmentation_path,
        "model_version": classifier.model_version,
    }

    with session_factory() as session:
        upsert_study(session, payload)
    return payload
