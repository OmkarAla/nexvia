"""Upload the committed synthetic studies into Orthanc (idempotent)."""

from __future__ import annotations

import argparse
from pathlib import Path

from nexvia_imaging.config import get_settings
from nexvia_imaging.dicom.client import OrthancClient


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Upload synthetic DICOM studies")
    parser.add_argument("--data", default=settings.demo_data_dir)
    parser.add_argument("--url", default=settings.orthanc_url)
    args = parser.parse_args()

    client = OrthancClient(args.url, settings.orthanc_user, settings.orthanc_password)
    files = sorted(Path(args.data).rglob("*.dcm"))
    uploaded = 0
    duplicates = 0

    for path in files:
        if client.upload_instance(path.read_bytes()):
            uploaded += 1
        else:
            duplicates += 1

    print(f"uploaded {uploaded}, already present {duplicates}, total {len(files)}")


if __name__ == "__main__":
    main()
