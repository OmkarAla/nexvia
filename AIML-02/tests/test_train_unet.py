from pathlib import Path

import nibabel as nib
import numpy as np
from train_unet import train_unet


def _write_case(directory: Path, index: int, size=(32, 32, 16)) -> None:
    images = directory / "imagesTr"
    labels = directory / "labelsTr"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(index)
    image = rng.normal(40, 20, size).astype(np.float32)
    label = np.zeros(size, dtype=np.uint8)

    if index % 2 == 0:
        z, y, x = np.ogrid[: size[0], : size[1], : size[2]]
        mask = (
            ((x - size[2] / 2) / (size[2] / 4)) ** 2
            + ((y - size[1] / 2) / (size[1] / 4)) ** 2
            + ((z - size[0] / 2) / (size[0] / 4)) ** 2
        ) < 1.0
        image[mask] = 120.0
        label[mask] = 1

    affine = np.eye(4)
    nib.save(nib.Nifti1Image(image, affine), images / f"case_{index:03d}_0000.nii.gz")
    nib.save(nib.Nifti1Image(label, affine), labels / f"case_{index:03d}.nii.gz")


def test_unet_training_smoke(tmp_path):
    data = tmp_path / "Task09_Spleen"
    for index in range(5):
        _write_case(data, index)
    metrics = train_unet(
        data,
        tmp_path / "artifacts",
        epochs=1,
        patch_size=(16, 16, 8),
        batch_size=1,
        limit=5,
        channels=(8, 16),
        num_res_units=1,
        num_workers=0,
        run_id="unet-smoke",
    )

    assert (tmp_path / "artifacts" / "unet_model.pt").exists()
    assert (tmp_path / "artifacts" / "unet_metrics.json").exists()
    assert metrics["run_id"] == "unet-smoke"
    assert metrics["n_train"] + metrics["n_val"] == 5
    assert 0.0 <= metrics["best_val_dice"] <= 1.0
    assert metrics["epochs"] == 1


def test_cases_accept_msd_task09_names(tmp_path):
    from train_unet import _cases, _resolve_data_dir

    inner = tmp_path / "Task09_Spleen"
    images = inner / "imagesTr"
    labels = inner / "labelsTr"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)

    import nibabel as nib
    import numpy as np

    array = np.zeros((8, 8, 4), dtype=np.float32)
    nib.save(nib.Nifti1Image(array, np.eye(4)), images / "spleen_1.nii.gz")
    nib.save(nib.Nifti1Image(array, np.eye(4)), labels / "spleen_1.nii.gz")
    (images / "._spleen_1.nii.gz").write_bytes(b"not a dicom")

    resolved = _resolve_data_dir(tmp_path)
    cases = _cases(resolved)

    assert resolved == inner
    assert len(cases) == 1
    assert cases[0]["image"].endswith("spleen_1.nii.gz")
