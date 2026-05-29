"""
Configuration for AI Inference Service
"""

import os
from pathlib import Path

# Model Registry Paths
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODELS_DIR = PROJECT_ROOT / "models"
PRODUCTION_MODELS_DIR = MODELS_DIR / "production"
CANDIDATE_MODELS_DIR = MODELS_DIR / "candidates"
ARCHIVE_MODELS_DIR = MODELS_DIR / "archive"

# Service Configuration
INFERENCE_SERVICE_HOST = os.getenv("INFERENCE_SERVICE_HOST", "0.0.0.0")
INFERENCE_SERVICE_PORT = int(os.getenv("INFERENCE_SERVICE_PORT", "8007"))

# Model Loading Configuration
MAX_MODELS_IN_MEMORY = int(os.getenv("MAX_MODELS_IN_MEMORY", "5"))
MODEL_TIMEOUT_SECONDS = int(os.getenv("MODEL_TIMEOUT_SECONDS", "30"))

# History Buffer Configuration
HISTORY_WINDOW_SIZE = int(os.getenv("HISTORY_WINDOW_SIZE", "30"))

# Qlib Configuration
QLIB_PROVIDER_URI = os.getenv("QLIB_PROVIDER_URI", str(PROJECT_ROOT / "db" / "qlib_data"))
QLIB_REGION = os.getenv("QLIB_REGION", "cn")
