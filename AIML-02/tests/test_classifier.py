from pathlib import Path

import numpy as np
import pydicom
import pytest
from PIL import Image

from nexvia_imaging.models.classifier import DenseNetClassifier

ARTIFACT_DIR = Path("artifacts/demo")
DEMO_IMAGE = Path("data/demo/cr/study-00/000.dcm")


@pytest.fixture(scope="module")
def classifier():
    if not (ARTIFACT_DIR / "model.pt").exists():
        pytest.skip("trained checkpoint not present")
    return DenseNetClassifier(ARTIFACT_DIR)


def _image(size: int = 512) -> Image.Image:
    rng = np.random.default_rng(0)
    array = rng.integers(0, 255, (size, size), dtype=np.uint8)
    return Image.fromarray(array).convert("RGB")


def _demo_image() -> Image.Image:
    dataset = pydicom.dcmread(DEMO_IMAGE)
    return Image.fromarray(dataset.pixel_array).convert("RGB")


def test_loads_checkpoint_and_ranks_findings(classifier):
    findings = classifier.predict(_image())

    assert len(findings) == 14
    assert classifier.model_version == "colab-nih-sample-001"
    probabilities = [finding.probability for finding in findings]
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(0.0 <= value <= 1.0 for value in probabilities)


def test_gradcam_has_signal_and_shape(classifier):
    image = _demo_image()
    top = classifier.predict(image)[0]
    label_index = classifier.labels.index(top.label)

    cam = classifier.gradcam(image, label_index=label_index, size=(224, 224))

    assert cam.shape == (224, 224)
    assert np.isfinite(cam).all()
    assert cam.min() >= 0.0 and cam.max() <= 1.0
    assert cam.std() > 0.0


def test_overlay_keeps_size(classifier):
    image = _demo_image().resize((256, 256))
    cam = classifier.gradcam(image, label_index=0, size=(256, 256))
    overlay = classifier.overlay(image, cam)
    assert overlay.size == (256, 256)
    assert overlay.mode == "RGB"
