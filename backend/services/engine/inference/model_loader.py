"""
Model Loader - 支持多框架模型加载 (LightGBM, PyTorch/TFT, ONNX)
"""

import hashlib
import json
import logging
import pickle
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认最大缓存模型数
DEFAULT_MAX_MODELS = 5


class EnsembleBooster:
    """多个 LightGBM Boosters 的集成包装器"""

    def __init__(self, boosters: list):
        self.boosters = boosters

    def predict(self, data, **kwargs):
        import numpy as np

        preds = [b.predict(data, **kwargs) for b in self.boosters]
        return np.mean(preds, axis=0)

    def feature_name(self):
        return self.boosters[0].feature_name()


class ModelLoader:
    """多框架模型管理器"""

    def __init__(self, production_dir: Path, max_models: int = DEFAULT_MAX_MODELS):
        self.production_dir = production_dir
        self.max_models = max_models
        self._loaded_models: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _build_cache_key(model_id: str, cache_key: str | None) -> str:
        return str(cache_key or model_id)

    def load_model(self, model_id: str, *, model_dir: Path | None = None, cache_key: str | None = None) -> Any:
        """加载模型，自动识别框架"""
        cache_id = self._build_cache_key(model_id, cache_key)
        with self._lock:
            if cache_id in self._loaded_models:
                self._loaded_models.move_to_end(cache_id)
                return self._loaded_models[cache_id]

        resolved_model_dir = model_dir or self._resolve_model_dir(model_id)
        if not resolved_model_dir.exists():
            raise FileNotFoundError(f"Model directory {model_id} not found at {self.production_dir}")

        # 读取元数据以确定框架
        metadata = self._get_metadata(resolved_model_dir)
        framework = metadata.get("framework", "lightgbm").lower()

        try:
            if framework == "lightgbm":
                model = self._load_lightgbm(resolved_model_dir, metadata)
            elif framework == "pytorch" or framework == "tft":
                model = self._load_pytorch(resolved_model_dir, metadata)
            elif framework == "onnx":
                model = self._load_onnx(resolved_model_dir, metadata)
            else:
                raise ValueError(f"Unsupported framework: {framework}")

            with self._lock:
                self._evict_lru()
                self._loaded_models[cache_id] = model

            logger.info(f"✅ Successfully loaded {framework} model: {model_id}")
            return model
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_id} ({framework}): {e}")
            raise

    def _load_lightgbm(self, model_dir: Path, metadata: dict[str, Any]) -> Any:
        """加载 LightGBM 模型 (支持单模型和集成)"""
        import lightgbm as lgb

        is_ensemble = metadata.get("is_ensemble", False) or any(model_dir.glob("seed_*.txt"))

        if is_ensemble:
            seed_files = sorted(list(model_dir.glob("seed_*.txt")))
            if not seed_files:
                # 兼容性检查：如果 metadata 说集成但没 seed 文件，看有没有 model.txt
                main_file = model_dir / "model.txt"
                if main_file.exists():
                    seed_files = [main_file]

            if not seed_files:
                raise FileNotFoundError("Ensemble seed files missing")
            boosters = [lgb.Booster(model_file=str(f)) for f in seed_files]
            return EnsembleBooster(boosters)
        else:
            model_file = model_dir / metadata.get("model_file", "model.lgb")
            if not model_file.exists():
                # 优先找 .lgb（训练流水线产物），再 .txt，最后 .pkl
                candidates = (
                    list(model_dir.glob("*.lgb"))
                    + list(model_dir.glob("*.txt"))
                    + list(model_dir.glob("*.pkl"))
                )
                if not candidates:
                    raise FileNotFoundError(f"No LightGBM model file found in {model_dir}")
                model_file = candidates[0]

            if model_file.suffix == ".pkl":
                with open(model_file, "rb") as f:
                    return pickle.load(f)
            return lgb.Booster(model_file=str(model_file))

    def _load_pytorch(self, model_dir: Path, metadata: dict[str, Any]) -> Any:
        """加载 PyTorch / TFT 模型"""
        try:
            import torch
        except ImportError:
            logger.error("torch is required for pytorch models. Please install it.")
            raise

        model_file = model_dir / metadata.get("model_file", "model.pth")
        if not model_file.exists():
            candidates = list(model_dir.glob("*.pth")) + list(model_dir.glob("*.pt"))
            if not candidates:
                raise FileNotFoundError(f"No PyTorch model file found in {model_dir}")
            model_file = candidates[0]

        # 针对 TFT (Temporal Fusion Transformer) 的特殊处理
        model_type = str(metadata.get("model_type", ""))
        if model_type == "TFT":
            try:
                from pytorch_forecasting import TemporalFusionTransformer

                # 注意：TFT 通常使用 load_from_checkpoint
                return TemporalFusionTransformer.load_from_checkpoint(str(model_file))
            except ImportError:
                logger.warning("pytorch_forecasting not installed, loading as raw torch model")

        if "nativetft" in model_type.lower():
            from .native_tft_model import load_native_tft_state_dict

            return load_native_tft_state_dict(str(model_file), metadata)

        return torch.load(str(model_file), map_location="cpu")

    def _load_onnx(self, model_dir: Path, metadata: dict[str, Any]) -> Any:
        """加载 ONNX 模型 (预留)"""
        import onnxruntime as ort

        model_file = model_dir / metadata.get("model_file", "model.onnx")
        return ort.InferenceSession(str(model_file))

    def _get_metadata(self, model_dir: Path) -> dict[str, Any]:
        """获取元数据，不存在则返回空字典"""
        merged: dict[str, Any] = {}
        meta_path = model_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                merged.update(json.load(f))

        # Optional runtime metadata (non-breaking extension).
        inf_meta_path = model_dir / "inference_metadata.json"
        if inf_meta_path.exists():
            with open(inf_meta_path) as f:
                inf_meta = json.load(f)
            for k, v in inf_meta.items():
                if k not in merged:
                    merged[k] = v

        return merged

    def _resolve_model_dir(self, model_id: str) -> Path:
        """支持版本解析 (e.g. model_v2)"""
        exact = self.production_dir / model_id
        if exact.exists():
            return exact
        candidates = sorted(self.production_dir.glob(f"{model_id}_v*"), key=lambda p: p.name, reverse=True)
        return candidates[0] if candidates else exact

    def _evict_lru(self):
        """LRU 淘汰"""
        while len(self._loaded_models) >= self.max_models:
            self._loaded_models.popitem(last=False)

    def get_model(self, model_id: str, *, cache_key: str | None = None) -> Any | None:
        cache_id = self._build_cache_key(model_id, cache_key)
        with self._lock:
            if cache_id in self._loaded_models:
                self._loaded_models.move_to_end(cache_id)
                return self._loaded_models[cache_id]
        return None

    def get_model_metadata(self, model_id: str, *, model_dir: Path | None = None) -> dict[str, Any] | None:
        resolved_model_dir = model_dir or self._resolve_model_dir(model_id)
        return self._get_metadata(resolved_model_dir) or None

    @property
    def loaded_models(self) -> list[str]:
        return list(self._loaded_models.keys())
