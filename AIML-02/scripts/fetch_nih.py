"""Fetch the official NIH ChestX-ray14 sample through the Kaggle CLI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the NIH sample")
    parser.add_argument("--out", default="data/nih")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "nih-sample.zip"

    subprocess.run(
        [
            "kaggle",
            "datasets",
            "download",
            "-d",
            "nih-chest-xrays/sample",
            "-p",
            str(out),
            "--unzip",
        ],
        check=True,
    )

    if not any(out.rglob("*.png")):
        candidates = list(out.glob("*.zip"))
        if candidates:
            with zipfile.ZipFile(candidates[0]) as bundle:
                bundle.extractall(out)
            candidates[0].unlink()

    if archive.exists():
        archive.unlink()

    nested = out / "sample"
    if nested.exists():
        for item in nested.iterdir():
            shutil.move(str(item), out / item.name)
        nested.rmdir()

    print(f"NIH sample ready under {out}")


if __name__ == "__main__":
    main()
