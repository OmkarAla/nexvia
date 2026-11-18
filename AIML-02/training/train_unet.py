"""MONAI 3D U-Net training for MSD Task 09 (spleen).

The same module runs on CPU for a smoke test and on a Colab T4 for real
training. Inference uses sliding-window evaluation over full volumes.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from monai.data import DataLoader, Dataset
from monai.inferers import sliding_window_inference
from monai.losses import DiceCELoss
from monai.metrics import DiceMetric
from monai.networks.nets import UNet
from monai.transforms import (
    Compose,
    CropForegroundd,
    EnsureChannelFirstd,
    EnsureTyped,
    LoadImaged,
    Orientationd,
    RandCropByPosNegLabeld,
    ScaleIntensityRanged,
    Spacingd,
)


def _cases(data_dir: Path) -> list[dict]:
    images = sorted((data_dir / "imagesTr").glob("*.nii.gz"))
    cases = []
    for image in images:
        stem = image.name.replace("_0000.nii.gz", "")
        label = data_dir / "labelsTr" / f"{stem}.nii.gz"
        if label.exists():
            cases.append({"image": str(image), "label": str(label)})
    if not cases:
        raise ValueError(f"no image/label pairs found under {data_dir}")
    return cases


def _transforms(patch_size: tuple[int, int, int], train: bool) -> Compose:
    base = [
        LoadImaged(keys=["image", "label"], image_only=True),
        EnsureChannelFirstd(keys=["image", "label"]),
        Spacingd(keys=["image", "label"], pixdim=(2.0, 2.0, 2.0), mode=("bilinear", "nearest")),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        ScaleIntensityRanged(keys="image", a_min=-57, a_max=164, b_min=0.0, b_max=1.0, clip=True),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        EnsureTyped(keys=["image", "label"]),
    ]
    if train:
        base.append(
            RandCropByPosNegLabeld(
                keys=["image", "label"],
                label_key="label",
                spatial_size=patch_size,
                pos=1,
                neg=1,
                num_samples=1,
            )
        )
    return Compose(base)


def train_unet(
    data_dir: str | Path,
    out_dir: str | Path,
    *,
    epochs: int = 20,
    patch_size: tuple[int, int, int] = (64, 64, 32),
    batch_size: int = 1,
    limit: int | None = None,
    seed: int = 7,
    channels: tuple[int, ...] = (16, 32, 64, 128),
    num_res_units: int = 2,
    num_workers: int = 2,
    run_id: str = "unet-spleen",
) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    data_path = Path(data_dir)
    cases = _cases(data_path)
    if limit is not None:
        cases = cases[:limit]
    split = max(1, int(len(cases) * 0.8))
    train_cases = cases[:split]
    val_cases = cases[split:] or cases[-1:]
    if not train_cases or not val_cases:
        raise ValueError("split produced an empty side")

    train_loader = DataLoader(
        Dataset(train_cases, transform=_transforms(patch_size, train=True)),
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        Dataset(val_cases, transform=_transforms(patch_size, train=False)),
        batch_size=1,
        shuffle=False,
        num_workers=num_workers,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UNet(
        spatial_dims=3,
        in_channels=1,
        out_channels=2,
        channels=channels,
        strides=(2,) * (len(channels) - 1),
        num_res_units=num_res_units,
    ).to(device)
    loss_function = DiceCELoss(softmax=True, to_onehot_y=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    dice_metric = DiceMetric(include_background=False, reduction="mean")

    best_dice = -1.0
    best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    history = []
    started = time.time()

    for epoch in range(epochs):
        model.train()
        running = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            labels = batch["label"].to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = loss_function(logits, labels)
            loss.backward()
            optimizer.step()
            running += float(loss.item())

        model.eval()
        dice_metric.reset()
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                labels = batch["label"].to(device)
                logits = sliding_window_inference(
                    images, patch_size, 1, model, overlap=0.5, mode="gaussian"
                )
                dice_metric(y_pred=logits, y=labels)
        dice = float(dice_metric.aggregate().item())
        if not np.isfinite(dice):
            dice = 0.0
        history.append(
            {"epoch": epoch + 1, "train_loss": running / len(train_loader), "val_dice": dice}
        )
        print(json.dumps(history[-1]), flush=True)
        if dice > best_dice:
            best_dice = dice
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "state_dict": best_state,
        "arch": "unet3d",
        "channels": list(channels),
        "num_res_units": num_res_units,
        "patch_size": list(patch_size),
        "run_id": run_id,
    }
    torch.save(checkpoint, out / "unet_model.pt")

    metrics = {
        "run_id": run_id,
        "best_val_dice": best_dice,
        "n_train": len(train_cases),
        "n_val": len(val_cases),
        "epochs": epochs,
        "patch_size": list(patch_size),
        "channels": list(channels),
        "device": str(device),
        "train_seconds": round(time.time() - started, 1),
        "history": history,
    }
    (out / "unet_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the MONAI spleen U-Net")
    parser.add_argument("--data", required=True, help="directory with imagesTr/ and labelsTr/")
    parser.add_argument("--out", default="artifacts/demo")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--run-id", default="unet-spleen")
    args = parser.parse_args()

    metrics = train_unet(
        args.data,
        args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        limit=args.limit,
        seed=args.seed,
        run_id=args.run_id,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
