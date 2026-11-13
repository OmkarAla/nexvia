import httpx
import pytest

from nexvia_imaging.dicom.client import OrthancClient


def _client(handler) -> OrthancClient:
    transport = httpx.MockTransport(handler)
    return OrthancClient(
        "http://orthanc:8042",
        "orthanc",
        "orthanc",
        client=httpx.Client(transport=transport),
    )


def test_stable_studies_parses_changes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/changes"
        assert request.url.params["type"] == "stable-studies"
        return httpx.Response(
            200,
            json={
                "Changes": [
                    {"ID": "1.2.3", "Seq": 4, "ChangeType": "StableStudy"},
                    {"ID": "1.2.4", "Seq": 5, "ChangeType": "StableStudy"},
                ],
                "Last": 5,
            },
        )

    studies, last = _client(handler).stable_studies(since=0)
    assert studies == ["1.2.3", "1.2.4"]
    assert last == 5


def test_study_metadata_returns_series():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dicom-web/studies/1.2.3/series"
        return httpx.Response(
            200,
            json=[{"0020000E": {"Value": ["9.8.7"]}, "00080060": {"Value": ["CT"]}}],
        )

    series = _client(handler).study_series("1.2.3")
    assert series == [{"series_uid": "9.8.7", "modality": "CT"}]


def test_series_instances_parses_sop_uids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dicom-web/studies/1.2.3/series/9.8.7/instances"
        return httpx.Response(
            200,
            json=[{"00080018": {"Value": ["5.5.5"]}}],
        )

    assert _client(handler).series_instances("1.2.3", "9.8.7") == ["5.5.5"]


def test_download_instance_reads_dicom_bytes():
    from io import BytesIO

    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.MediaStorageSOPInstanceUID = "5.5.5"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    dataset.SOPInstanceUID = "5.5.5"
    dataset.PatientName = "SYNTHETIC^DEMO"

    buffer = BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)
    payload = buffer.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/instances/5.5.5/file"
        return httpx.Response(200, content=payload)

    loaded = _client(handler).download_instance("5.5.5")
    assert loaded.SOPInstanceUID == "5.5.5"
    assert str(loaded.PatientName) == "SYNTHETIC^DEMO"


def test_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(httpx.HTTPStatusError):
        _client(handler).stable_studies(since=0)
