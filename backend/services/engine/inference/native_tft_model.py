"""
Native TFT model wrapper for production inference.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class _TorchRequiredError(RuntimeError):
    pass


def _import_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except Exception as exc:  # pragma: no cover - import guard
        raise _TorchRequiredError("PyTorch is required for NativeTFT inference. Install torch first.") from exc
    return torch, nn, F


class GatedResidualNetwork:  # thin wrapper to delay torch import at module load
    @staticmethod
    def build(input_size: int, hidden_size: int, output_size: int, dropout: float):
        _, nn, F = _import_torch()

        class _GRN(nn.Module):
            def __init__(self):
                super().__init__()
                self.lin1 = nn.Linear(input_size, hidden_size)
                self.lin2 = nn.Linear(hidden_size, hidden_size)
                self.gate = nn.Linear(hidden_size, output_size)
                self.dropout = nn.Dropout(dropout)
                self.norm = nn.LayerNorm(output_size)
                self.skip = nn.Linear(input_size, output_size) if input_size != output_size else nn.Identity()

            def forward(self, x):
                h = F.elu(self.lin1(x))
                h = self.lin2(h)
                h = self.dropout(h)
                g = self.gate(h).sigmoid()
                return self.norm(self.skip(x) + g * h)

        return _GRN()


def _build_native_tft(
    *,
    input_dim: int = 54,
    hidden_dim: int = 64,
    num_heads: int = 4,
    dropout: float = 0.1,
):
    _, nn, _ = _import_torch()

    class _NativeTFT(nn.Module):
        def __init__(self):
            super().__init__()
            self.input_proj = nn.Linear(input_dim, hidden_dim)
            self.gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True)
            self.attn = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=num_heads, batch_first=True)
            self.grn = GatedResidualNetwork.build(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                output_size=hidden_dim,
                dropout=dropout,
            )
            self.output_layer = nn.Linear(hidden_dim, 1)

        def forward(self, x):
            h = self.input_proj(x)
            h_gru, _ = self.gru(h)
            attn_out, _ = self.attn(h_gru, h_gru, h_gru)
            h = h_gru + attn_out
            h = self.grn(h[:, -1, :])
            return self.output_layer(h).squeeze(-1)

    return _NativeTFT()


class NativeTFTPredictor:
    def __init__(self, model: Any, device: str = "cpu"):
        torch, _, _ = _import_torch()
        self._torch = torch
        self.model = model.to(device)
        self.device = device
        self.model.eval()

    def predict(self, data, **kwargs):
        import numpy as np

        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[None, :, :]
        if arr.ndim != 3:
            raise ValueError(f"NativeTFT expects 3D input, got shape={arr.shape}")
        with self._torch.no_grad():
            x = self._torch.tensor(arr, dtype=self._torch.float32, device=self.device)
            out = self.model(x)
        return out.detach().cpu().numpy().reshape(-1)


def load_native_tft_state_dict(model_file: str, metadata: dict[str, Any] | None = None):
    torch, _, _ = _import_torch()
    meta = metadata or {}
    input_spec = meta.get("input_spec", {}) if isinstance(meta, dict) else {}
    feature_columns = input_spec.get("feature_columns", [])

    arch = meta.get("model_arch", {}) if isinstance(meta.get("model_arch"), dict) else {}
    input_dim = int(arch.get("input_dim") or len(feature_columns) or 54)
    hidden_dim = int(arch.get("hidden_dim") or 64)
    num_heads = int(arch.get("num_heads") or 4)
    dropout = float(arch.get("dropout") or 0.1)

    model = _build_native_tft(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        num_heads=num_heads,
        dropout=dropout,
    )
    obj = torch.load(model_file, map_location="cpu")
    if isinstance(obj, dict) and "state_dict" in obj and isinstance(obj["state_dict"], dict):
        state_dict = obj["state_dict"]
    else:
        state_dict = obj
    strict = bool(meta.get("strict_load", True))
    model.load_state_dict(state_dict, strict=strict)
    return NativeTFTPredictor(model=model, device="cpu")
