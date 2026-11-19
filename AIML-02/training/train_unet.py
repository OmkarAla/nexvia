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


def _resolve_data_dir(data_dir: str | Path) -> Path:
    """Accept either Task09_Spleen/ or a directory containing it."""
    path = Path(data_dir)
    if (path / "imagesTr").is_dir():
        return path
    for child in sorted(path.iterdir()):
        if child.is_dir() and (child / "imagesTr").is_dir():
            return child
    return path


def _cases(data_dir: Path) -> list[dict]:
    images = [
        path
        for path in sorted((data_dir / "imagesTr").glob("*.nii.gz"))
        if not path.name.startswith("._")
    ]
    cases = []
    for image in images:
        name = image.name
        if name.endswith("_0000.nii.gz"):
            stem = name[: -len("_0000.nii.gz")]
        elif name.endswith(".nii.gz"):
            stem = name[: -len(".nii.gz")]
        else:
            continue
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
    patch_size: tuple[int, int, int] = (96, 96, 64),
    batch_size: int = 1,
    limit: int | None = None,
    seed: int = 7,
    channels: tuple[int, ...] = (16, 32, 64, 128),
    num_res_units: int = 2,
    num_workers: int = 2,
    run_id: str = "unet-spleen",
    resume: bool = False,
) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"writing checkpoints to {out.resolve()}", flush=True)

    data_path = _resolve_data_dir(data_dir)
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
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    best_dice = -1.0
    history: list[dict] = []
    start_epoch = 0
    started = time.time()

    if resume and (out / "unet_last.pt").exists():
        state = torch.load(out / "unet_last.pt", map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        start_epoch = int(state["epoch"])
        best_dice = float(state["best_dice"])
        history = list(state["history"])
        print(f"resuming from epoch {start_epoch}", flush=True)

    for epoch in range(start_epoch, epochs):
        model.train()
        running = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            labels = batch["label"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                logits = model(images)
                loss = loss_function(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += float(loss.item())

        model.eval()
        case_dice: list[float] = []
        predicted_fractions: list[float] = []
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                labels = batch["label"].to(device)
                logits = sliding_window_inference(
                    images, patch_size, 1, model, overlap=0.5, mode="gaussian"
                )
                predictions = torch.argmax(logits, dim=1) == 1
                targets = labels[:, 0] == 1
                for index in range(predictions.shape[0]):
                    predicted = predictions[index]
                    target = targets[index]
                    intersection = torch.logical_and(predicted, target).sum().item()
                    denominator = predicted.sum().item() + target.sum().item()
                    case_dice.append(2 * intersection / denominator if denominator else 0.0)
                    predicted_fractions.append(predicted.float().mean().item())
        dice = float(np.mean(case_dice)) if case_dice else 0.0
        if not np.isfinite(dice):
            dice = 0.0
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": running / len(train_loader),
                "val_dice": dice,
                "val_pred_fraction": float(np.mean(predicted_fractions))
                if predicted_fractions
                else 0.0,
            }
        )
        print(json.dumps(history[-1]), flush=True)

        if dice > best_dice:
            best_dice = dice
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "arch": "unet3d",
                    "channels": list(channels),
                    "num_res_units": num_res_units,
                    "patch_size": list(patch_size),
                    "run_id": run_id,
                },
                out / "unet_model.pt",
            )

        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scaler": scaler.state_dict(),
                "epoch": epoch + 1,
                "best_dice": best_dice,
                "history": history,
            },
            out / "unet_last.pt",
        )
        (out / "unet_metrics.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "best_val_dice": best_dice,
                    "n_train": len(train_cases),
                    "n_val": len(val_cases),
                    "epochs": epochs,
                    "epochs_completed": epoch + 1,
                    "patch_size": list(patch_size),
                    "channels": list(channels),
                    "device": str(device),
                    "train_seconds": round(time.time() - started, 1),
                    "history": history,
                },
                indent=2,
            )
        )

    if not (out / "unet_model.pt").exists():
        torch.save(
            {
                "state_dict": model.state_dict(),
                "arch": "unet3d",
                "channels": list(channels),
                "num_res_units": num_res_units,
                "patch_size": list(patch_size),
                "run_id": run_id,
            },
            out / "unet_model.pt",
        )

    metrics = {
        "run_id": run_id,
        "best_val_dice": best_dice,
        "n_train": len(train_cases),
        "n_val": len(val_cases),
        "epochs": epochs,
        "epochs_completed": len(history),
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
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    metrics = train_unet(
        args.data,
        args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        limit=args.limit,
        seed=args.seed,
        run_id=args.run_id,
        resume=args.resume,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
