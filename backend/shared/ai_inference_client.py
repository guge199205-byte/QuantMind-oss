"""
AI Inference Client
Client library for communicating with AI Inference Service
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class AIInferenceClient:
    """Client for AI Inference Service API."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def health_check(self) -> bool:
        """Check if inference service is healthy."""
        try:
            response = self.session.get(f"{self.base_url}/")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def list_models(self) -> list[dict[str, Any]]:
        """
        List all available models.

        Returns:
            List of model metadata dictionaries
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/inference/models")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_model_info(self, model_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific model.

        Args:
            model_id: Model identifier

        Returns:
            Model metadata or None if not found
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/inference/models/{model_id}")
            response.raise_for_status()
            data = response.json()
            return data.get("model")
        except Exception as e:
            logger.error(f"Failed to get model info for {model_id}: {e}")
            return None

    def load_model(self, model_id: str) -> bool:
        """
        Load a model into memory.

        Args:
            model_id: Model identifier

        Returns:
            True if successful
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/inference/models/load",
                json={"model_id": model_id},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            return False

    def unload_model(self, model_id: str) -> bool:
        """
        Unload a model from memory.

        Args:
            model_id: Model identifier

        Returns:
            True if successful
        """
        try:
            response = self.session.delete(f"{self.base_url}/api/v1/inference/models/{model_id}")
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to unload model {model_id}: {e}")
            return False

    def predict(self, model_id: str, data: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Generate prediction using a model.

        Args:
            model_id: Model identifier
            data: Market data (single dict or list of dicts)

        Returns:
            Prediction results or None if failed
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/inference/predict",
                json={"model_id": model_id, "data": data},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Prediction failed for model {model_id}: {e}")
            return None

    def batch_predict(
        self, model_id: str, symbols: list[str], market_data: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """
        Generate predictions for multiple symbols.

        Args:
            model_id: Model identifier
            symbols: List of symbol codes
            market_data: Dictionary mapping symbol to market data

        Returns:
            Dictionary mapping symbol to prediction score
        """
        predictions = {}

        # Prepare batch data
        batch_data = []
        for symbol in symbols:
            if symbol in market_data:
                batch_data.append(market_data[symbol])

        if not batch_data:
            return predictions

        # Get predictions
        result = self.predict(model_id, batch_data)
        if result and result.get("status") == "success":
            pred_values = result.get("predictions", [])
            result_symbols = result.get("symbols", [])

            for symbol, score in zip(result_symbols, pred_values):
                predictions[symbol] = score

        return predictions


# Singleton instance
_client_instance = None


def get_inference_client(base_url: str = "http://localhost:8001") -> AIInferenceClient:
    """Get or create singleton inference client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = AIInferenceClient(base_url)
    return _client_instance
