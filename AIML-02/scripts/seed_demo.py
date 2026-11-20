"""Process the committed demo studies without Orthanc.

This is the offline path used for screenshots and recorded demos when Docker
is unavailable. The same pipeline and model run; only the transport changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pydicom

from nexvia_imaging.config import get_settings
from nexvia_imaging.db.engine import make_engine, make_session_factory
from nexvia_imaging.db.repo import init_db, list_studies
from nexvia_imaging.models.classifier import DenseNetClassifier
from nexvia_imaging.models.segmenter import SpleenSegmenter
from nexvia_imaging.worker.pipeline import process_study


class LocalStudyClient:
    def __init__(self, datasets: list) -> None:
        self.datasets = datasets
        self.by_uid = {str(dataset.SOPInstanceUID): dataset for dataset in datasets}
        first = datasets[0]
        self.study_uid = str(first.StudyInstanceUID)
        self.series_uid = str(first.SeriesInstanceUID)
        self.modality = str(first.Modality)

    def study_series(self, study_uid: str) -> list[dict]:
        return [{"series_uid": self.series_uid, "modality": self.modality}]

    def series_instances(self, study_uid: str, series_uid: str) -> list[str]:
        return list(self.by_uid)

    def download_instance(self, sop_uid: str):
        return self.by_uid[sop_uid]


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Analyze committed DICOM files offline")
    parser.add_argument("--data", default=settings.demo_data_dir)
    parser.add_argument("--overlays", default="data/overlays")
    args = parser.parse_args()

    manifest = json.loads((Path(args.data) / "manifest.json").read_text())
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    classifier = DenseNetClassifier(settings.model_dir)
    segmenter = SpleenSegmenter(settings.model_dir)

    for entry in manifest["studies"]:
        directory = Path(args.data) / entry["path"]
        datasets = [pydicom.dcmread(path) for path in sorted(directory.glob("*.dcm"))]
        client = LocalStudyClient(datasets)
        process_study(
            client.study_uid, client, session_factory, classifier, args.overlays, segmenter
        )
        print(f"analyzed {client.study_uid} ({entry['modality']}, {len(datasets)} instances)")

    with session_factory() as session:
        print(f"studies in database: {len(list_studies(session))}")


if __name__ == "__main__":
    main()
