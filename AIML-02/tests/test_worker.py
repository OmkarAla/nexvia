import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from nexvia_imaging.data.make_dicom import generate_cr_study
from nexvia_imaging.db.models import Base, Study
from nexvia_imaging.db.repo import get_cursor, list_studies
from nexvia_imaging.models.classifier import Finding
from nexvia_imaging.worker.main import run_once
from nexvia_imaging.worker.pipeline import process_study, to_display_image


class FakeClassifier:
    labels = ["Effusion", "Mass"]
    model_version = "fake-001"

    def predict(self, image):
        return [Finding("Effusion", 0.91), Finding("Mass", 0.42)]

    def gradcam(self, image, label_index, size=None):
        return np.ones((size[1], size[0]), dtype=np.float32) * 0.5

    def overlay(self, image, cam):
        return image


class FakeClient:
    def __init__(self, dataset, studies=("1.2.3",)):
        self.dataset = dataset
        self.studies = list(studies)

    def stable_studies(self, since):
        return self.studies, 7

    def study_series(self, study_uid):
        return [{"series_uid": "9.8.7", "modality": str(self.dataset.Modality)}]

    def series_instances(self, study_uid, series_uid):
        return ["5.5.5"]

    def download_instance(self, sop_uid):
        return self.dataset


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def session_factory(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)


def test_to_display_image_handles_ct_window():
    from nexvia_imaging.data.make_dicom import generate_ct_series

    dataset = generate_ct_series(0, slices=3)[1]
    image = to_display_image(dataset)
    assert image.size == (128, 128)
    array = np.asarray(image)
    assert array.min() >= 0 and array.max() <= 255
    assert array.max() > 0


def test_process_study_persists_and_writes_overlays(tmp_path, session_factory):
    dataset = generate_cr_study(0)[0]
    client = FakeClient(dataset)

    payload = process_study("1.2.3", client, session_factory, FakeClassifier(), tmp_path)

    assert payload["modality"] == "CR"
    assert payload["model_version"] == "fake-001"
    assert payload["findings"][0]["label"] == "Effusion"

    with session_factory() as session:
        study = session.get(Study, "1.2.3")
        assert study is not None
        assert study.status == "analyzed"
        assert len(study.findings) == 2
        assert len(study.overlays) == 2

    for relative in payload["overlays"]:
        assert (tmp_path / relative).exists()


def test_run_once_advances_cursor_and_is_idempotent(tmp_path, session_factory):
    client = FakeClient(generate_cr_study(1)[0])

    first = run_once(client, session_factory, FakeClassifier(), tmp_path)
    second = run_once(client, session_factory, FakeClassifier(), tmp_path)

    assert first["processed"] == 1
    assert second["processed"] == 1
    with session_factory() as session:
        assert len(list_studies(session)) == 1
        assert get_cursor(session) == 7


def test_missing_series_raises(tmp_path, session_factory):
    class EmptyClient(FakeClient):
        def study_series(self, study_uid):
            return []

    with pytest.raises(ValueError):
        process_study(
            "1.2.3",
            EmptyClient(generate_cr_study(0)[0]),
            session_factory,
            FakeClassifier(),
            tmp_path,
        )


class FakeSegmenter:
    run_id = "fake-unet"

    def segment(self, volume):
        return np.ones_like(volume, dtype=np.uint8)

    def overlay_slice(self, image, mask, alpha=0.45):
        return image


class FakeCTClient:
    def __init__(self, datasets):
        self.datasets = datasets
        self.by_uid = {str(item.SOPInstanceUID): item for item in datasets}

    def stable_studies(self, since):
        return [str(self.datasets[0].StudyInstanceUID)], 3

    def study_series(self, study_uid):
        return [{"series_uid": str(self.datasets[0].SeriesInstanceUID), "modality": "CT"}]

    def series_instances(self, study_uid, series_uid):
        return list(self.by_uid)

    def download_instance(self, sop_uid):
        return self.by_uid[sop_uid]


def test_ct_study_adds_segmentation(tmp_path, session_factory):
    from nexvia_imaging.data.make_dicom import generate_ct_series

    datasets = generate_ct_series(0, slices=3)
    client = FakeCTClient(datasets)
    study_uid = str(datasets[0].StudyInstanceUID)

    payload = process_study(
        study_uid, client, session_factory, FakeClassifier(), tmp_path, FakeSegmenter()
    )

    assert payload["segmentation"]
    assert (tmp_path / payload["segmentation"]).exists()
    with session_factory() as session:
        study = session.get(Study, study_uid)
        assert study.segmentation == payload["segmentation"]


class EmptySegmenter(FakeSegmenter):
    def segment(self, volume):
        return np.zeros_like(volume, dtype=np.uint8)


def test_ct_without_a_mask_has_no_segmentation(tmp_path, session_factory):
    from nexvia_imaging.data.make_dicom import generate_ct_series

    datasets = generate_ct_series(1, slices=3)
    client = FakeCTClient(datasets)
    study_uid = str(datasets[0].StudyInstanceUID)

    payload = process_study(
        study_uid, client, session_factory, FakeClassifier(), tmp_path, EmptySegmenter()
    )

    assert payload["segmentation"] is None
