import numpy as np
import pandas as pd
import pytest
from PIL import Image
from train_classifier import FINDINGS, parse_labels, patient_split, train


def _frame(n: int = 24) -> pd.DataFrame:
    rows = []
    for index in range(n):
        patient = index // 4 + 1
        finding = "Effusion" if index % 3 == 0 else ("Nodule" if index % 5 == 0 else "No Finding")
        rows.append(
            {
                "Image Index": f"{patient:08d}_{index % 4:03d}.png",
                "Finding Labels": finding,
                "Patient ID": patient,
            }
        )
    return pd.DataFrame(rows)


def _write_dataset(tmp_path, frame, size=64):
    images = tmp_path / "images"
    images.mkdir()
    rng = np.random.default_rng(0)
    for name in frame["Image Index"]:
        array = rng.integers(0, 255, (size, size, 3), dtype=np.uint8)
        Image.fromarray(array).save(images / name)
    csv = tmp_path / "labels.csv"
    frame.to_csv(csv, index=False)
    return csv, images


def test_parse_labels_produces_binary_matrix():
    frame = pd.DataFrame({"Finding Labels": ["Effusion|Nodule", "No Finding", "Hernia"]})
    labels = parse_labels(frame)
    assert labels.shape == (3, len(FINDINGS))
    assert labels[0, FINDINGS.index("Effusion")] == 1
    assert labels[0, FINDINGS.index("Nodule")] == 1
    assert labels[1].sum() == 0
    assert labels[2, FINDINGS.index("Hernia")] == 1


def test_patient_split_has_no_overlap():
    frame = _frame(40)
    frame["split"] = patient_split(frame, seed=3)
    patients = {
        name: set(frame.loc[frame["split"] == name, "Patient ID"])
        for name in ("train", "val", "test")
    }
    assert patients["train"] & patients["val"] == set()
    assert patients["train"] & patients["test"] == set()
    assert patients["val"] & patients["test"] == set()


def test_training_smoke_writes_checkpoint_and_metrics(tmp_path):
    frame = _frame()
    csv, images = _write_dataset(tmp_path, frame)

    metrics = train(
        csv,
        images,
        tmp_path / "artifacts",
        epochs=1,
        batch_size=8,
        learning_rate=1e-3,
        image_size=64,
        pretrained=False,
        num_workers=0,
        run_id="smoke",
    )

    assert (tmp_path / "artifacts" / "model.pt").exists()
    assert (tmp_path / "artifacts" / "metrics.json").exists()
    assert metrics["run_id"] == "smoke"
    assert set(metrics["per_label_auroc"]) == set(FINDINGS)
    assert metrics["n_train"] + metrics["n_val"] + metrics["n_test"] == len(frame)
    assert 0.0 <= metrics["mean_auroc"] <= 1.0


def test_empty_split_is_rejected(tmp_path):
    frame = _frame(8)
    frame["Patient ID"] = 1
    csv, images = _write_dataset(tmp_path, frame)

    with pytest.raises(ValueError):
        train(
            csv, images, tmp_path / "artifacts", epochs=1, limit=8, pretrained=False, num_workers=0
        )
