from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from nexvia_imaging.models.segmenter import SpleenSegmenter

ARTIFACT_DIR = Path("artifacts/demo")


@pytest.fixture(scope="module")
def segmenter():
    if not (ARTIFACT_DIR / "unet_model.pt").exists():
        pytest.skip("segmentation checkpoint not present")
    return SpleenSegmenter(ARTIFACT_DIR)


def test_segments_demo_ct_volume(segmenter):
    from nexvia_imaging.data.make_dicom import generate_ct_series

    series = generate_ct_series(0, slices=20)
    volume = np.stack(
        [
            dataset.pixel_array.astype(np.float32) * float(dataset.RescaleSlope)
            + float(dataset.RescaleIntercept)
            for dataset in series
        ]
    )

    mask = segmenter.segment(volume)

    assert mask.shape == volume.shape
    assert set(np.unique(mask)).issubset({0, 1})
    assert segmenter.run_id == "colab-unet-003"


def test_overlay_preserves_size(segmenter):
    image = Image.fromarray(np.zeros((128, 128), dtype=np.uint8), mode="L").convert("RGB")
    mask = np.zeros((20, 128, 128), dtype=np.uint8)
    mask[8:12, 50:80, 50:80] = 1

    overlay = segmenter.overlay_slice(image, mask[10])

    assert overlay.size == (128, 128)
    assert overlay.mode == "RGB"
