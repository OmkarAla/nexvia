"""DenseNet-121 inference and Grad-CAM for chest X-rays."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torchvision import transforms
from torchvision.models import densenet121

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


@dataclass
class Finding:
    label: str
    probability: float


class DenseNetClassifier:
    def __init__(self, model_dir: str | Path, device: str = "cpu") -> None:
        model_dir = Path(model_dir)
        checkpoint_path = model_dir / "model.pt"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"missing checkpoint: {checkpoint_path}")

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        self.labels: list[str] = list(checkpoint.get("labels", FINDINGS))
        self.image_size = int(checkpoint.get("image_size", 224))
        normalization = checkpoint.get(
            "normalization",
            {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        )
        self.model_version = str(checkpoint.get("run_id", "unknown"))

        self.device = torch.device(device)
        model = densenet121(weights=None)
        model.classifier = torch.nn.Linear(model.classifier.in_features, len(self.labels))
        model.load_state_dict(checkpoint["state_dict"])
        model.to(self.device)
        model.eval()
        self.model = model

        self.transform = transforms.Compose(
            [
                transforms.Resize(int(self.image_size * 1.14)),
                transforms.CenterCrop(self.image_size),
                transforms.ToTensor(),
                transforms.Normalize(normalization["mean"], normalization["std"]),
            ]
        )

    def _forward(self, tensor: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Run the backbone without torchvision's in-place ReLU.

        DenseNet's stock forward modifies the feature map in place, which
        breaks Grad-CAM autograd. Keeping the feature tensor intact lets us
        differentiate the class score with respect to it directly.
        """
        features = self.model.features(tensor)
        pooled = torch.nn.functional.adaptive_avg_pool2d(torch.relu(features), (1, 1))
        logits = self.model.classifier(torch.flatten(pooled, 1))
        return logits, features

    def _tensor(self, image: Image.Image) -> torch.Tensor:
        return self.transform(image.convert("RGB")).unsqueeze(0).to(self.device)

    @torch.no_grad()
    def predict(self, image: Image.Image) -> list[Finding]:
        logits, _ = self._forward(self._tensor(image))
        probabilities = torch.sigmoid(logits)[0].cpu().numpy()
        findings = [
            Finding(label=label, probability=float(probabilities[index]))
            for index, label in enumerate(self.labels)
        ]
        return sorted(findings, key=lambda finding: finding.probability, reverse=True)

    def gradcam(
        self, image: Image.Image, label_index: int, size: tuple[int, int] | None = None
    ) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            logits, features = self._forward(self._tensor(image))
            score = logits[0, label_index]
            gradients = torch.autograd.grad(score, features)[0]

        activations_tensor = features.detach()[0]
        gradients_tensor = gradients.detach()[0]
        weights = gradients_tensor.mean(dim=(1, 2), keepdim=True)
        cam = torch.relu((weights * activations_tensor).sum(dim=0))
        cam = cam / (cam.max() + 1e-8)
        cam_array = cam.cpu().numpy()

        target_size = size or image.size
        resized = Image.fromarray(np.uint8(cam_array * 255)).resize(target_size, Image.BILINEAR)
        return np.asarray(resized, dtype=np.float32) / 255.0

    def overlay(self, image: Image.Image, cam: np.ndarray, alpha: float = 0.45) -> Image.Image:
        base = image.convert("RGB")
        heat = Image.fromarray(np.uint8(cam * 255), mode="L")
        colored = ImageOps.colorize(heat, black="#0000ff", mid="#ffff00", white="#ff0000")
        return Image.blend(base, colored.convert("RGB"), alpha)


def finding_thresholds(metrics: dict, default: float = 0.5) -> dict[str, float]:
    """Use the metrics file to pick a display threshold per finding.

    The checkpoint ships sensitivity/specificity at 0.5; until per-label
    threshold calibration is run on validation, this keeps the default and
    lets the UI rank by probability.
    """
    return {label: default for label in metrics.get("per_label_auroc", {})}
