"""Minimal DICOMweb + Orthanc client used by the worker and the seeder."""

from __future__ import annotations

from io import BytesIO

import httpx
import pydicom
from pydicom.dataset import Dataset


class OrthancClient:
    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._auth = (user, password)

    def _get(self, path: str, **kwargs) -> httpx.Response:
        response = self._client.get(f"{self.base_url}{path}", auth=self._auth, **kwargs)
        response.raise_for_status()
        return response

    def stable_studies(self, since: int) -> tuple[list[str], int]:
        response = self._get("/changes", params={"type": "stable-studies", "since": str(since)})
        payload = response.json()
        studies = [
            change["ID"]
            for change in payload.get("Changes", [])
            if change.get("ChangeType") == "StableStudy" or "ID" in change
        ]
        return sorted(set(studies)), int(payload.get("Last", since))

    def study_series(self, study_uid: str) -> list[dict]:
        response = self._get(f"/dicom-web/studies/{study_uid}/series")
        series = []
        for item in response.json():
            series.append(
                {
                    "series_uid": item.get("0020000E", {}).get("Value", [""])[0],
                    "modality": item.get("00080060", {}).get("Value", [""])[0],
                }
            )
        return series

    def series_instances(self, study_uid: str, series_uid: str) -> list[str]:
        response = self._get(f"/dicom-web/studies/{study_uid}/series/{series_uid}/instances")
        return [item.get("00080018", {}).get("Value", [""])[0] for item in response.json()]

    def download_instance(self, sop_instance_uid: str) -> Dataset:
        response = self._get(f"/instances/{sop_instance_uid}/file")
        return pydicom.dcmread(BytesIO(response.content))

    def upload_instance(self, payload: bytes) -> bool:
        response = self._client.post(
            f"{self.base_url}/instances",
            content=payload,
            headers={"Content-Type": "application/dicom"},
            auth=self._auth,
        )
        if response.status_code in (200, 201):
            return True
        if response.status_code == 409:
            return False
        response.raise_for_status()
        return False

    def find_studies(self, limit: int = 100) -> list[str]:
        response = self._get("/dicom-web/studies", params={"limit": limit})
        return [item.get("0020000D", {}).get("Value", [""])[0] for item in response.json()]

    def close(self) -> None:
        self._client.close()
