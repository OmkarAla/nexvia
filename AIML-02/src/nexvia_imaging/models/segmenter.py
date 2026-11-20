"""3D U-Net spleen segmentation for CT series."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from monai.inferers import sliding_window_inference
from monai.networks.nets import UNet
from PIL import Image

HU_MIN = -160.0
HU_MAX = 240.0


class SpleenSegmenter:
    def __init__(self, model_dir: str | Path, device: str = "cpu") -> None:
        model_dir = Path(model_dir)
        checkpoint_path = model_dir / "unet_model.pt"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"missing checkpoint: {checkpoint_path}")

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        self.channels = tuple(checkpoint.get("channels", (16, 32, 64, 128)))
        self.num_res_units = int(checkpoint.get("num_res_units", 2))
        self.patch_size = tuple(checkpoint.get("patch_size", (96, 96, 64)))
        self.run_id = str(checkpoint.get("run_id", "unknown"))

        self.device = torch.device(device)
        model = UNet(
            spatial_dims=3,
            in_channels=1,
            out_channels=2,
            channels=self.channels,
            strides=(2,) * (len(self.channels) - 1),
            num_res_units=self.num_res_units,
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.to(self.device)
        model.eval()
        self.model = model

    @staticmethod
    def _normalize(volume_hu: np.ndarray) -> np.ndarray:
        clipped = np.clip(volume_hu.astype(np.float32), HU_MIN, HU_MAX)
        return (clipped - HU_MIN) / (HU_MAX - HU_MIN)

    @staticmethod
    def _pad_depth(volume: np.ndarray, multiple: int = 16) -> np.ndarray:
        depth = volume.shape[0]
        target = max(multiple, ((depth + multiple - 1) // multiple) * multiple)
        if target == depth:
            return volume
        pad = target - depth
        return np.pad(volume, ((0, pad), (0, 0), (0, 0)), mode="constant", constant_values=HU_MIN)

    def segment(self, volume_hu: np.ndarray) -> np.ndarray:
        """Return a binary spleen mask with shape (D, H, W)."""
        volume = self._pad_depth(volume_hu)
        tensor = torch.from_numpy(self._normalize(volume))[None, None].to(self.device)
        patch = tuple(
            min(size, dimension)
            for size, dimension in zip(self.patch_size, volume.shape, strict=False)
        )
        with torch.no_grad():
            logits = sliding_window_inference(
                tensor, patch, 1, self.model, overlap=0.5, mode="gaussian"
            )
        mask = torch.argmax(logits, dim=1)[0].cpu().numpy().astype(np.uint8)
        return mask[: volume_hu.shape[0]]

    @staticmethod
    def overlay_slice(image: Image.Image, mask: np.ndarray, alpha: float = 0.45) -> Image.Image:
        base = np.asarray(image.convert("RGB"), dtype=np.float32).copy()
        color = np.zeros_like(base)
        color[..., 0] = 255.0
        mask_3d = mask.astype(bool)
        base[mask_3d] = (1.0 - alpha) * base[mask_3d] + alpha * color[mask_3d]
        return Image.fromarray(np.uint8(np.clip(base, 0, 255)), mode="RGB")
