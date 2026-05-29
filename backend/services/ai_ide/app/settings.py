import json
import os
import sys

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(find_dotenv())

PROJECT_ROOT = os.getenv("AI_IDE_PROJECT_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../..")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 获取可写数据目录
DATA_DIR = os.getenv("AI_IDE_DATA_DIR")
if not DATA_DIR:
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_config_api_key() -> str:
    """从可写配置中读取 API Key。"""
    config_path = os.path.join(DATA_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
                if config.get("qwen_api_key"):
                    return config["qwen_api_key"]
        except Exception:
            pass
    return ""


def get_effective_api_key() -> str:
    """按优先级获取 API Key：config.json > AI_IDE_API_KEY > OPENAI_API_KEY。"""
    return _load_config_api_key() or os.getenv("AI_IDE_API_KEY") or os.getenv("OPENAI_API_KEY", "")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "QuantMind-AI-IDE-Service"
    api_key: str = get_effective_api_key()
    # UI 当前主文案是 Qwen API Key，这里默认走 DashScope OpenAI 兼容地址
    # 可通过 AI_IDE_BASE_URL / AI_IDE_MODEL 覆盖。
    base_url: str = os.getenv("AI_IDE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = os.getenv("AI_IDE_MODEL") or "qwen-plus"


settings = Settings()


def refresh_runtime_settings() -> Settings:
    """
    运行时刷新可变配置，保证：
    - 前端刚保存 API Key 后，无需重启进程也可生效
    - 打包环境下重启后能从可写目录恢复配置
    """
    settings.api_key = get_effective_api_key()
    return settings
