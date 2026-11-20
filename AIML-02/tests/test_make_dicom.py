import pytest

from nexvia_imaging.data.make_dicom import (
    CR_IMAGE_STORAGE,
    CT_IMAGE_STORAGE,
    generate_cr_study,
    generate_ct_series,
    write_demo_studies,
)


def test_cr_study_is_synthetic_and_deterministic():
    first = generate_cr_study(0, seed=7)
    second = generate_cr_study(0, seed=7)

    assert len(first) == 1
    dataset = first[0]
    assert dataset.Modality == "CR"
    assert dataset.SOPClassUID == CR_IMAGE_STORAGE
    assert "SYNTHETIC" in str(dataset.PatientName)
    assert "EDUCATION" in str(dataset.StudyDescription)
    assert dataset.Rows == 512
    assert dataset.Columns == 512
    assert dataset.pixel_array.shape == (512, 512)
    assert dataset.SOPInstanceUID == second[0].SOPInstanceUID
    assert dataset.StudyInstanceUID == second[0].StudyInstanceUID


def test_ct_series_shares_study_and_has_rescale():
    series = generate_ct_series(1, seed=7, slices=4)

    assert len(series) == 4
    assert len({dataset.StudyInstanceUID for dataset in series}) == 1
    assert len({dataset.SOPInstanceUID for dataset in series}) == 4
    assert all(dataset.SOPClassUID == CT_IMAGE_STORAGE for dataset in series)
    assert series[0].RescaleIntercept == -1024
    assert series[0].RescaleSlope == 1
    assert series[0].pixel_array.dtype.name == "int16"
    assert [int(dataset.InstanceNumber) for dataset in series] == [1, 2, 3, 4]
    hu = series[0].pixel_array.astype(float) * series[0].RescaleSlope + series[0].RescaleIntercept
    assert hu.max() > -500


def test_write_demo_studies_creates_manifest(tmp_path):
    manifest = write_demo_studies(tmp_path)

    assert len(manifest["studies"]) >= 2
    modalities = {study["modality"] for study in manifest["studies"]}
    assert modalities == {"CR", "CT"}
    assert (tmp_path / "manifest.json").exists()
    assert list(tmp_path.rglob("*.dcm"))


def test_cr_index_changes_uid_but_not_for_same_index():
    a = generate_cr_study(2, seed=1)[0]
    b = generate_cr_study(3, seed=1)[0]
    c = generate_cr_study(2, seed=1)[0]
    assert a.StudyInstanceUID != b.StudyInstanceUID
    assert a.StudyInstanceUID == c.StudyInstanceUID


def test_invalid_modality_rejected():
    with pytest.raises(ValueError):
        generate_cr_study(-1, seed=1)
