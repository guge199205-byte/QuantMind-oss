"""
Inference Service - Core service for model predictions
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from .config import MAX_MODELS_IN_MEMORY, PRODUCTION_MODELS_DIR
from .data_adapter import DataAdapter
from .history_buffer import HistoryBuffer
from .model_loader import ModelLoader
from .neutralizer import Neutralizer
from backend.shared.stock_utils import StockCodeUtil

logger = logging.getLogger(__name__)


class InferenceService:
    """Main service for handling model inference requests."""

    def __init__(self, production_dir: Path | None = None):
        self.production_dir = production_dir or PRODUCTION_MODELS_DIR
        self.history_buffer = HistoryBuffer()
        self.model_loader = ModelLoader(self.production_dir, max_models=MAX_MODELS_IN_MEMORY)
        self.data_adapter = DataAdapter(history_buffer=self.history_buffer)
        self.neutralizer = Neutralizer()
        logger.info(f"Initialized InferenceService with production dir: {self.production_dir}")

    def predict(
        self,
        model_id: str,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        model_dir: Path | None = None,
        cache_namespace: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate prediction using a loaded model with neutralization.
        """
        try:
            cache_key = f"{cache_namespace}:{model_id}" if cache_namespace else model_id
            model = self.model_loader.get_model(model_id, cache_key=cache_key)
            if model is None:
                self.model_loader.load_model(model_id, model_dir=model_dir, cache_key=cache_key)
                model = self.model_loader.get_model(model_id, cache_key=cache_key)

            metadata = self.model_loader.get_model_metadata(model_id, model_dir=model_dir)
            if self._is_sequence_model(metadata):
                return self._predict_sequence_model(
                    model_id=model_id,
                    model=model,
                    metadata=metadata or {},
                    data=data,
                )

            df = self.data_adapter.convert_realtime_data(data)
            feature_columns = self._resolve_feature_columns(model, metadata)
            features = self.data_adapter.prepare_features(df, feature_columns)

            # --- ARCHITECTURE UPGRADE: Apply Neutralization ---
            is_neutralized = metadata.get("is_neutralized", False)
            if is_neutralized:
                last_date = (
                    df["date"].max().strftime("%Y-%m-%d")
                    if "date" in df.columns
                    else datetime.now().strftime("%Y-%m-%d")
                )
                self.neutralizer.refresh_metadata(last_date)
                features.index = df.get("instrument", df.get("symbol", []))
                features = self.neutralizer.neutralize(features, feature_columns)
            # --------------------------------------------------

            prediction = self._predict_with_model(model, features)

            # Format response
            if isinstance(prediction, pd.Series):
                prediction = prediction.tolist()
            elif hasattr(prediction, "tolist"):
                prediction = prediction.tolist()

            return {
                "status": "success",
                "model_id": model_id,
                "predictions": prediction,
                "input_shape": features.shape,
                "symbols": (
                    df.get("instrument", df.get("symbol", [])).tolist()
                    if "instrument" in df.columns or "symbol" in df.columns
                    else []
                ),
            }

        except Exception as e:
            logger.error(f"Prediction failed for model {model_id}: {e}")
            return {"status": "error", "model_id": model_id, "error": str(e)}

    def predict_batch(
        self,
        model_id: str,
        features_df: pd.DataFrame,
        *,
        model_dir: Path | None = None,
        cache_namespace: str | None = None,
    ) -> dict[str, Any]:
        """
        批量预测，直接使用预计算好的特征。
        跳过 DataAdapter 的特征生成步骤，直接调用模型进行推理。

        Args:
            model_id: 模型ID
            features_df: 包含特征的 DataFrame (index=instrument, columns=features)

        Returns:
            Dict containing:
                - status: success/error
                - predictions: list of scores
                - symbols: list of symbols (from index)
                - model_id: used model
        """
        try:
            cache_key = f"{cache_namespace}:{model_id}" if cache_namespace else model_id
            # 1. 获取模型
            model = self.model_loader.get_model(model_id, cache_key=cache_key)
            if model is None:
                self.model_loader.load_model(model_id, model_dir=model_dir, cache_key=cache_key)
                model = self.model_loader.get_model(model_id, cache_key=cache_key)

            if model is None:
                raise ValueError(f"Model {model_id} could not be loaded")

            # 2. 校验特征列 (Optional but recommended)
            # metadata = self.model_loader.get_model_metadata(model_id)
            # feature_columns = self._resolve_feature_columns(model, metadata)
            # missing = set(feature_columns) - set(features_df.columns)
            # if missing:
            #     logger.warning(f"Batch prediction input missing columns: {missing}")

            # 3. 直接推理 (高效批量)
            # Ensure input is compatible with model expectations (e.g. float32)
            prediction = self._predict_with_model(model, features_df)

            # 4. 格式化输出
            if isinstance(prediction, pd.Series):
                prediction = prediction.tolist()
            elif hasattr(prediction, "tolist"):
                prediction = prediction.tolist()

            return {
                "status": "success",
                "model_id": model_id,
                "predictions": prediction,
                "symbols": features_df.index.tolist(),
                "count": len(prediction),
            }

        except Exception as e:
            logger.error(f"Batch prediction failed for model {model_id}: {e}")
            return {"status": "error", "model_id": model_id, "error": str(e)}

    def _resolve_feature_columns(self, model: Any, metadata: dict[str, Any] | None) -> list[str]:
        """从 metadata 或模型对象推断特征列。"""
        if metadata:
            feature_columns = metadata.get("feature_columns", [])
            if feature_columns:
                return feature_columns
            input_spec = metadata.get("input_spec", {})
            if isinstance(input_spec, dict):
                seq_cols = input_spec.get("feature_columns", [])
                if seq_cols:
                    return [str(c) for c in seq_cols]

        # LightGBM Booster
        if hasattr(model, "feature_name"):
            try:
                feature_columns = model.feature_name()
                if feature_columns:
                    return [str(c) for c in feature_columns]
            except Exception:
                pass

        # Qlib LGBModel wrapper
        if hasattr(model, "model") and hasattr(model.model, "feature_name"):
            try:
                feature_columns = model.model.feature_name()
                if feature_columns:
                    return [str(c) for c in feature_columns]
            except Exception:
                pass

        # Fallback
        return ["open", "high", "low", "close", "volume"]

    @staticmethod
    def _is_sequence_model(metadata: dict[str, Any] | None) -> bool:
        if not metadata:
            return False
        input_spec = metadata.get("input_spec", {})
        if not isinstance(input_spec, dict):
            return False
        tensor_shape = input_spec.get("tensor_shape")
        return isinstance(tensor_shape, list) and len(tensor_shape) == 3

    def _predict_sequence_model(
        self,
        *,
        model_id: str,
        model: Any,
        metadata: dict[str, Any],
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> dict[str, Any]:
        feature_columns = self._resolve_feature_columns(model, metadata)
        lookback = int(
            (metadata.get("preprocess", {}) or {}).get("lookback_window")
            or (metadata.get("input_spec", {}) or {}).get("tensor_shape", [None, 30, None])[1]
            or 30
        )
        clip_range = (metadata.get("preprocess", {}) or {}).get("clip_range")

        seq_arr: np.ndarray
        symbols: list[str]

        if isinstance(data, dict) and "sequences" in data:
            seq_arr = np.asarray(data.get("sequences"), dtype=np.float32)
            if seq_arr.ndim != 3:
                raise ValueError(f"sequences must be 3D array, got shape={seq_arr.shape}")
            if seq_arr.shape[2] != len(feature_columns):
                raise ValueError(f"feature dim mismatch: got {seq_arr.shape[2]}, expect {len(feature_columns)}")
            raw_symbols = data.get("symbols") or []
            if isinstance(raw_symbols, list) and len(raw_symbols) == seq_arr.shape[0]:
                symbols = [StockCodeUtil.to_prefix(str(s)) for s in raw_symbols]
            else:
                symbols = [f"SEQ_{i}" for i in range(seq_arr.shape[0])]
        else:
            df = self.data_adapter.convert_realtime_data(data)
            if "instrument" not in df.columns and "symbol" in df.columns:
                df["instrument"] = df["symbol"]
            if "instrument" not in df.columns:
                raise ValueError("sequence inference data must include instrument/symbol")
            if "date" in df.columns and "datetime" not in df.columns:
                df["datetime"] = pd.to_datetime(df["date"], errors="coerce")
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

            seq_list: list[np.ndarray] = []
            symbols = []
            grouped = df.groupby("instrument", sort=False)
            for inst, g in grouped:
                g2 = g.sort_values("datetime") if "datetime" in g.columns else g
                g2 = g2.reindex(columns=feature_columns, fill_value=0.0)
                g2 = g2.ffill().bfill().fillna(0.0)
                if len(g2) < lookback:
                    continue
                seq = g2.tail(lookback).to_numpy(dtype=np.float32)
                seq_list.append(seq)
                symbols.append(str(inst))
            if not seq_list:
                raise ValueError(f"no valid sequence found, need >= {lookback} rows per instrument")
            seq_arr = np.stack(seq_list, axis=0).astype(np.float32, copy=False)

        if isinstance(clip_range, list) and len(clip_range) == 2:
            lo, hi = float(clip_range[0]), float(clip_range[1])
            seq_arr = np.clip(seq_arr, lo, hi)

        seq_arr = np.nan_to_num(seq_arr, nan=0.0, posinf=0.0, neginf=0.0)

        prediction = self._predict_with_model(model, seq_arr)
        if isinstance(prediction, pd.Series):
            prediction = prediction.tolist()
        elif hasattr(prediction, "tolist"):
            prediction = prediction.tolist()

        return {
            "status": "success",
            "model_id": model_id,
            "predictions": prediction,
            "input_shape": tuple(seq_arr.shape),
            "symbols": symbols,
        }

    @staticmethod
    def _is_generated_column_feature_set(feature_columns: list[str]) -> bool:
        """判断是否为 Column_0...Column_N 这类自动列名。"""
        if not feature_columns:
            return False
        return all(re.fullmatch(r"Column_\d+", str(col)) for col in feature_columns)

    @staticmethod
    def _predict_with_model(model: Any, features: pd.DataFrame):
        """
        兼容多种模型对象:
          - sklearn/lightgbm booster: model.predict(features)
          - qlib LGBModel wrapper: model.model.predict(features)
        """
        # 常规路径
        if hasattr(model, "predict"):
            try:
                return model.predict(features)
            except Exception as e:
                # qlib LGBModel 常见错误: DataFrame 无 prepare()
                if "prepare" not in str(e):
                    raise

        # qlib LGBModel 包装器
        inner_model = getattr(model, "model", None)
        if inner_model is not None and hasattr(inner_model, "predict"):
            return inner_model.predict(features)

        raise TypeError(f"Unsupported model type for prediction: {type(model)}")

    def get_model_info(self, model_id: str, *, model_dir: Path | None = None) -> dict[str, Any] | None:
        """
        Get detailed information about a model.

        Args:
            model_id: Unique identifier for the model

        Returns:
            Dictionary with model information or None
        """
        metadata = self.model_loader.get_model_metadata(model_id, model_dir=model_dir)
        if metadata:
            metadata["loaded"] = model_id in self.model_loader.loaded_models
            return metadata
        return None

    def get_buffer_stats(self) -> dict[str, Any]:
        """获取历史数据缓冲区统计"""
        return self.history_buffer.stats()
