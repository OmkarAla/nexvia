"""DenseNet-121 multi-label training for NIH ChestX-ray14.

Runs on CPU for smoke tests and on a Colab T4 for real training. The same
module is imported by the notebook, so there is no notebook-only logic.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import DenseNet121_Weights, densenet121

FINDINGS = [
    "Atelectasis",
    "Cardiomegaly",
    "Effusion",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pneumonia",
    "Pneumothorax",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Fibrosis",
    "Pleural_Thickening",
    "Hernia",
]
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def parse_labels(frame: pd.DataFrame) -> np.ndarray:
    labels = np.zeros((len(frame), len(FINDINGS)), dtype=np.float32)
    for row_index, value in enumerate(frame["Finding Labels"].astype(str)):
        for finding in value.split("|"):
            if finding in FINDINGS:
                labels[row_index, FINDINGS.index(finding)] = 1.0
    return labels


def patient_split(
    frame: pd.DataFrame, seed: int = 7, val_fraction: float = 0.1, test_fraction: float = 0.1
) -> np.ndarray:
    patients = frame["Patient ID"].astype(str).unique()
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(patients)
    n_test = max(1, int(len(patients) * test_fraction))
    n_val = max(1, int(len(patients) * val_fraction))

    assignment = {}
    for patient in shuffled[:n_test]:
        assignment[patient] = "test"
    for patient in shuffled[n_test : n_test + n_val]:
        assignment[patient] = "val"
    for patient in shuffled[n_test + n_val :]:
        assignment[patient] = "train"
    return frame["Patient ID"].astype(str).map(assignment).to_numpy()


def build_transforms(image_size: int) -> tuple:
    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Resize(int(image_size * 1.14)),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    return train_transform, eval_transform


class ChestXrayDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, images_dir: str | Path, transform) -> None:
        self.frame = frame.reset_index(drop=True)
        self.images_dir = Path(images_dir)
        self.transform = transform
        self.labels = parse_labels(self.frame)

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        name = self.frame.iloc[index]["Image Index"]
        image = Image.open(self.images_dir / name).convert("RGB")
        return self.transform(image), torch.tensor(self.labels[index])


def build_model(num_labels: int, pretrained: bool = True) -> torch.nn.Module:
    weights = DenseNet121_Weights.DEFAULT if pretrained else None
    model = densenet121(weights=weights)
    model.classifier = torch.nn.Linear(model.classifier.in_features, num_labels)
    return model


def _per_label_auroc(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float | None]:
    scores: dict[str, float | None] = {}
    for index, finding in enumerate(FINDINGS):
        column = y_true[:, index]
        if len(np.unique(column)) < 2:
            scores[finding] = None
        else:
            scores[finding] = float(roc_auc_score(column, y_score[:, index]))
    return scores


def _mean(values) -> float:
    valid = [value for value in values if value is not None]
    return float(np.mean(valid)) if valid else 0.0


@torch.no_grad()
def evaluate(model, loader, device) -> tuple[dict, np.ndarray, np.ndarray]:
    model.eval()
    probabilities, targets = [], []
    for images, labels in loader:
        images = images.to(device)
        logits = model(images)
        probabilities.append(torch.sigmoid(logits).cpu().numpy())
        targets.append(labels.numpy())

    y_score = np.concatenate(probabilities)
    y_true = np.concatenate(targets)
    per_label = _per_label_auroc(y_true, y_score)
    metrics = {
        "per_label_auroc": per_label,
        "mean_auroc": _mean(per_label.values()),
        "n": int(len(y_true)),
        "prevalence": {
            finding: float(y_true[:, index].mean()) for index, finding in enumerate(FINDINGS)
        },
    }
    return metrics, y_true, y_score


def train(
    csv_path: str | Path,
    images_dir: str | Path,
    out_dir: str | Path,
    *,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 1e-4,
    image_size: int = IMAGE_SIZE,
    limit: int | None = None,
    seed: int = 7,
    pretrained: bool = True,
    num_workers: int = 2,
    run_id: str = "imaging-classifier",
) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    frame = pd.read_csv(csv_path)
    if limit is not None:
        frame = frame.head(limit).copy()
    frame["split"] = patient_split(frame, seed=seed)

    train_transform, eval_transform = build_transforms(image_size)
    splits = {
        name: frame[frame["split"] == name].reset_index(drop=True)
        for name in ("train", "val", "test")
    }
    for name, subset in splits.items():
        if subset.empty:
            raise ValueError(f"{name} split is empty")

    train_loader = DataLoader(
        ChestXrayDataset(splits["train"], images_dir, train_transform),
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        ChestXrayDataset(splits["val"], images_dir, eval_transform),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )
    test_loader = DataLoader(
        ChestXrayDataset(splits["test"], images_dir, eval_transform),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(len(FINDINGS), pretrained=pretrained).to(device)
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, epochs))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    best_auc = -1.0
    best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    history = []
    started = time.time()

    for epoch in range(epochs):
        model.train()
        running = 0.0
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += float(loss.item()) * len(images)

        scheduler.step()
        val_metrics, _, _ = evaluate(model, val_loader, device)
        epoch_metrics = {
            "epoch": epoch + 1,
            "train_loss": running / len(splits["train"]),
            "val_mean_auroc": val_metrics["mean_auroc"],
        }
        history.append(epoch_metrics)
        print(json.dumps(epoch_metrics), flush=True)

        if val_metrics["mean_auroc"] > best_auc:
            best_auc = val_metrics["mean_auroc"]
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }

    model.load_state_dict(best_state)
    test_metrics, y_true, y_score = evaluate(model, test_loader, device)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "state_dict": best_state,
        "arch": "densenet121",
        "labels": FINDINGS,
        "image_size": image_size,
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "run_id": run_id,
        "mean_auroc": test_metrics["mean_auroc"],
    }
    torch.save(checkpoint, out / "model.pt")

    threshold = 0.5
    predictions = (y_score >= threshold).astype(int)
    sensitivity = {}
    specificity = {}
    for index, finding in enumerate(FINDINGS):
        positive = y_true[:, index] == 1
        negative = ~positive
        sensitivity[finding] = (
            float(predictions[positive, index].mean()) if positive.any() else None
        )
        specificity[finding] = (
            float(1.0 - predictions[negative, index].mean()) if negative.any() else None
        )

    metrics = {
        "run_id": run_id,
        **test_metrics,
        "sensitivity_at_0.5": sensitivity,
        "specificity_at_0.5": specificity,
        "n_train": int(len(splits["train"])),
        "n_val": int(len(splits["val"])),
        "n_test": int(len(splits["test"])),
        "epochs": epochs,
        "batch_size": batch_size,
        "image_size": image_size,
        "val_best_mean_auroc": best_auc,
        "history": history,
        "train_seconds": round(time.time() - started, 1),
        "device": str(device),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the NIH ChestX-ray14 classifier")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--out", default="artifacts/demo")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--run-id", default="imaging-classifier")
    args = parser.parse_args()

    metrics = train(
        args.csv,
        args.images,
        args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        image_size=args.image_size,
        limit=args.limit,
        seed=args.seed,
        pretrained=not args.no_pretrained,
        num_workers=args.num_workers,
        run_id=args.run_id,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
