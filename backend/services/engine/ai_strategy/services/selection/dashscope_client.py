import os
from typing import Any, Dict, Optional

from openai import OpenAI

try:
    from ...ai_strategy_config import get_config as _get_config
except ImportError:
    from backend.services.engine.ai_strategy.ai_strategy_config import get_config as _get_config

ai_strategy_config = _get_config()


class DashScopeClient:
    """Minimal wrapper around DashScope (OpenAI-compatible) APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured")
        self.base_url = base_url or os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_embedding(
        self,
        text: str,
        model: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        model = model or ai_strategy_config.DASHSCOPE_EMBEDDING_MODEL
        resp = self.client.embeddings.create(
            model=model,
            input=text,
            timeout=timeout or ai_strategy_config.DASHSCOPE_EMBEDDING_TIMEOUT,
        )
        return {
            "model": resp.model,
            "vector": resp.data[0].embedding,
            "metadata": resp.to_dict(),
        }

    def health(self) -> str:
        """Lightweight check that the configured endpoint responds."""
        try:
            resp = self.client.embeddings.create(
                model=ai_strategy_config.DASHSCOPE_EMBEDDING_MODEL,
                input="health check",
                timeout=ai_strategy_config.DASHSCOPE_EMBEDDING_TIMEOUT,
            )
            return resp.model
        except Exception as exc:
            raise RuntimeError("DashScope health check failed") from exc


__all__ = ["DashScopeClient"]
