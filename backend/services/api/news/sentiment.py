"""FinBERT-zh 中文金融情感小模型（懒加载，CPU 推理）。

依赖：transformers + torch + 已离线下载好的中文 FinBERT 权重。
默认模型：valhalla/distilbart...  不，我们要中文金融。

实际选用：bardsai/finance-sentiment-zh-base  (≈100MB, RoBERTa-zh)
回退：直接 NotAvailable，调用方使用字典法 sentiment_score。

行为：
- 第一次调用时下载/加载（耗时几秒~几十秒）
- 之后每次 score(text) 返回 (label, confidence)
- label ∈ {"bullish", "bearish", "neutral"}
- 全局单例，线程安全
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Tuple

logger = logging.getLogger("news.sentiment")

# 优先离线，不下载就跳过
DEFAULT_MODEL = os.getenv(
    "FINBERT_ZH_MODEL",
    "bardsai/finance-sentiment-zh-base",
)
USE_FINBERT = os.getenv("NEWS_USE_FINBERT", "true").lower() == "true"

_model_lock = threading.Lock()
_model_ready = False
_model_failed = False
_pipeline = None  # transformers Pipeline 实例

# label 映射（不同模型 label 命名不一样）
_LABEL_MAP = {
    "positive": "bullish",
    "bullish": "bullish",
    "neutral": "neutral",
    "negative": "bearish",
    "bearish": "bearish",
    "POSITIVE": "bullish",
    "NEUTRAL": "neutral",
    "NEGATIVE": "bearish",
    "LABEL_0": "bearish",   # 大多数 transformer 默认 0=neg
    "LABEL_1": "neutral",
    "LABEL_2": "bullish",
}


def _try_load() -> None:
    global _pipeline, _model_ready, _model_failed
    if not USE_FINBERT:
        _model_failed = True
        return
    try:
        from transformers import pipeline  # type: ignore
        logger.info("加载 FinBERT 模型: %s ...", DEFAULT_MODEL)
        _pipeline = pipeline(
            "sentiment-analysis",
            model=DEFAULT_MODEL,
            tokenizer=DEFAULT_MODEL,
            device=-1,  # CPU
            truncation=True,
            max_length=256,
        )
        _model_ready = True
        logger.info("FinBERT 加载完成")
    except Exception as e:
        logger.warning("FinBERT 加载失败（将仅使用字典法情感）：%s", e)
        _model_failed = True


def score(text: str) -> Tuple[str | None, float | None]:
    """返回 (label, confidence)。失败/未启用返回 (None, None)。"""
    global _model_ready, _model_failed
    if _model_failed:
        return None, None
    if not _model_ready:
        with _model_lock:
            if not _model_ready and not _model_failed:
                _try_load()
        if _model_failed or not _model_ready:
            return None, None
    if not text or not text.strip():
        return None, None
    try:
        # 截断到 256 token 已在 pipeline 处设置
        res = _pipeline(text[:1000])
        if not res:
            return None, None
        item = res[0]
        raw_label = str(item.get("label") or "").strip()
        conf = float(item.get("score") or 0.0)
        label = _LABEL_MAP.get(raw_label, "neutral")
        return label, conf
    except Exception as e:
        logger.warning("FinBERT 推理失败: %s", str(e)[:120])
        return None, None


def is_available() -> bool:
    return _model_ready and not _model_failed
