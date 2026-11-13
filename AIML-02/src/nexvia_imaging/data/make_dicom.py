"""Generate small, clearly synthetic DICOM studies for the demo.

No patient data is used. Every object carries SYNTHETIC / EDUCATION ONLY tags.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

CR_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.1"
CT_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.2"
_NAMESPACE = uuid.UUID("6f1e6a5a-6c1f-4b6e-9f0e-2f7c1a9d4b21")
_IMPLEMENTATION_UID = "2.25.329800735698586629295641978511506172918"
_STUDY_DATE = "20260101"
_STUDY_TIME = "120000"


def _uid(key: str) -> str:
    return f"2.25.{uuid.uuid5(_NAMESPACE, key).int}"


def _base_dataset(
    *,
    study_key: str,
    series_key: str,
    instance_key: str,
    sop_class: str,
    modality: str,
    description: str,
    series_number: int,
    instance_number: int,
) -> FileDataset:
    sop_instance = _uid(instance_key)
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class
    file_meta.MediaStorageSOPInstanceUID = sop_instance
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = _IMPLEMENTATION_UID

    dataset = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = sop_class
    dataset.SOPInstanceUID = sop_instance

    dataset.PatientName = "SYNTHETIC^DEMO"
    dataset.PatientID = "SYN-DEMO"
    dataset.PatientBirthDate = ""
    dataset.PatientSex = "O"
    dataset.StudyInstanceUID = _uid(study_key)
    dataset.SeriesInstanceUID = _uid(series_key)
    dataset.StudyDate = _STUDY_DATE
    dataset.StudyTime = _STUDY_TIME
    dataset.SeriesDate = _STUDY_DATE
    dataset.SeriesTime = _STUDY_TIME
    dataset.AccessionNumber = "SYNTHETIC"
    dataset.StudyID = "SYN-DEMO"
    dataset.StudyDescription = description
    dataset.SeriesDescription = description
    dataset.Modality = modality
    dataset.SeriesNumber = series_number
    dataset.InstanceNumber = instance_number
    dataset.Manufacturer = "SYNTHETIC"
    dataset.InstitutionName = "EDUCATION ONLY"
    dataset.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    return dataset


def _cr_pixels(index: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed * 1000 + index)
    size = 512
    y, x = np.mgrid[0:size, 0:size]
    image = 30.0 + 60.0 * (y / size)

    # Two darker lung fields.
    for cx in (170, 342):
        mask = ((x - cx) / 120.0) ** 2 + ((y - 280) / 190.0) ** 2 < 1.0
        image[mask] -= 35.0

    # Rib-like arcs.
    for offset in range(6):
        arc = np.abs(np.sqrt((x - 256) ** 2 + (y - 300) ** 2) - (120 + offset * 22))
        image[arc < 2.0] += 45.0

    # A bright synthetic nodule in half the studies; index parity keeps it deterministic.
    if index % 2 == 0:
        nodule = ((x - 300) / 22.0) ** 2 + ((y - 240) / 18.0) ** 2 < 1.0
        image[nodule] += 90.0

    image += rng.normal(0, 4, image.shape)
    return np.clip(image, 0, 255).astype(np.uint8)


def _ct_pixels(slice_index: int, slices: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed * 100 + slice_index)
    size = 128
    y, x = np.mgrid[0:size, 0:size]
    image = np.full((size, size), -1000.0)

    body = ((x - 64) / 52.0) ** 2 + ((y - 64) / 44.0) ** 2 < 1.0
    image[body] = 40.0

    # Spleen appears in the middle third of the series.
    start = slices // 3
    if start <= slice_index < start + max(2, slices // 3):
        spleen = ((x - 78) / 20.0) ** 2 + ((y - 70) / 14.0) ** 2 < 1.0
        image[spleen] = 110.0

    image += rng.normal(0, 8, image.shape)
    return np.clip(image, -1000, 1500).astype(np.int16)


def generate_cr_study(index: int, seed: int = 7) -> list[FileDataset]:
    if index < 0:
        raise ValueError("index must be non-negative")

    dataset = _base_dataset(
        study_key=f"cr-study-{index}",
        series_key=f"cr-series-{index}",
        instance_key=f"cr-instance-{index}",
        sop_class=CR_IMAGE_STORAGE,
        modality="CR",
        description=f"SYNTHETIC CHEST - EDUCATION ONLY - {index:02d}",
        series_number=1,
        instance_number=1,
    )
    dataset.Rows = 512
    dataset.Columns = 512
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelSpacing = [0.14, 0.14]
    dataset.PixelData = _cr_pixels(index, seed).tobytes()
    file_meta = dataset.file_meta
    file_meta.MediaStorageSOPClassUID = CR_IMAGE_STORAGE
    file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    return [dataset]


def generate_ct_series(index: int, seed: int = 7, slices: int = 20) -> list[FileDataset]:
    if index < 0:
        raise ValueError("index must be non-negative")
    if slices < 1:
        raise ValueError("slices must be positive")

    series: list[FileDataset] = []
    for slice_index in range(slices):
        dataset = _base_dataset(
            study_key=f"ct-study-{index}",
            series_key=f"ct-series-{index}",
            instance_key=f"ct-instance-{index}-{slice_index}",
            sop_class=CT_IMAGE_STORAGE,
            modality="CT",
            description=f"SYNTHETIC ABDOMEN - EDUCATION ONLY - {index:02d}",
            series_number=2,
            instance_number=slice_index + 1,
        )
        dataset.Rows = 128
        dataset.Columns = 128
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = 16
        dataset.BitsStored = 16
        dataset.HighBit = 15
        dataset.PixelRepresentation = 1
        dataset.PixelSpacing = [1.5, 1.5]
        dataset.SliceThickness = 5.0
        dataset.ImagePositionPatient = [0.0, 0.0, float(slice_index * 5)]
        dataset.RescaleSlope = 1
        dataset.RescaleIntercept = -1024
        dataset.PixelData = _ct_pixels(slice_index, slices, seed).tobytes()
        dataset.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
        series.append(dataset)
    return series


def write_demo_studies(out_dir: str | Path, seed: int = 7) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    studies = []

    for index in range(6):
        series = generate_cr_study(index, seed=seed)
        relative = Path("cr") / f"study-{index:02d}"
        _write_series(out / relative, series)
        studies.append(
            {
                "study_uid": series[0].StudyInstanceUID,
                "modality": "CR",
                "description": str(series[0].StudyDescription),
                "n_instances": len(series),
                "path": str(relative).replace("\\", "/"),
            }
        )

    series = generate_ct_series(0, seed=seed)
    relative = Path("ct") / "study-00"
    _write_series(out / relative, series)
    studies.append(
        {
            "study_uid": series[0].StudyInstanceUID,
            "modality": "CT",
            "description": str(series[0].StudyDescription),
            "n_instances": len(series),
            "path": str(relative).replace("\\", "/"),
        }
    )

    manifest = {"synthetic": True, "seed": seed, "studies": studies}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _write_series(directory: Path, series: list[FileDataset]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, dataset in enumerate(series):
        dataset.save_as(directory / f"{index:03d}.dcm", enforce_file_format=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic DICOM demo studies")
    parser.add_argument("--out", default="data/demo")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    manifest = write_demo_studies(args.out, args.seed)
    print(f"wrote {len(manifest['studies'])} studies to {args.out}")


if __name__ == "__main__":
    main()
