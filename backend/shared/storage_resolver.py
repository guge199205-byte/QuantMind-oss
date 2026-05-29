"""
Storage Resolver Utility
用于解析由于云端化导致的存储差异。
将 COS Key 或 Database Strategy ID 解析为本地可执行/可读取的文件路径。
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from sqlalchemy import text

try:
    from backend.shared.database_pool import get_db, init_default_databases
except ImportError:
    try:
        from shared.database_pool import get_db, init_default_databases
    except ImportError:
        get_db = None
        init_default_databases = None

try:
    from backend.shared.cos_service import get_cos_service
except ImportError:
    try:
        from shared.cos_service import get_cos_service
    except ImportError:
        get_cos_service = None

logger = logging.getLogger(__name__)


class StorageResolver:
    """
    负责将抽象资源 Key 解析为具体的本地文件路径。
    """

    def __init__(self, cache_dir: str | None = None):
        # 默认缓存目录，可由环境变量覆盖
        default_cache = os.getenv("STORAGE_RESOLVER_CACHE", "/tmp/quantmind_cache")
        self.cache_dir = Path(cache_dir or default_cache)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cos_service = None
        if get_cos_service:
            try:
                self.cos_service = get_cos_service()
            except Exception as e:
                logger.warning(f"StorageResolver: COS service initialization failed: {e}")

    async def resolve_to_local_path(self, key: str) -> Path:
        """
        主解析方法。

        解析规则：
        1. 本身是存在的绝对路径 -> 返回 Path 对象
        2. 纯数字字符串 -> 视为数据库 Strategy ID
        3. 包含特定前缀/结构的字符串 -> 视为 COS Key
        4. 回退 -> 视为项目相对路径或原样返回
        """
        if not key:
            raise ValueError("Empty key provided to StorageResolver")
        normalized_key = self._normalize_cloud_key(key)

        # 1. 绝对路径检查
        if os.path.isabs(key) and os.path.exists(key):
            return Path(key)

        # 2. 数据库 ID 检查
        if normalized_key.isdigit():
            return await self._resolve_db_strategy(int(normalized_key))

        # 3. COS Key 检查
        # 规则：包含 user_strategies/ 或 stock_pool 等关键词，或者 explicit prefix
        is_cos = (
            "user_strategies/" in normalized_key
            or "stock_pool" in normalized_key
            or "user_pools/" in normalized_key
            or "strategies/" in normalized_key
            or key.startswith("cos://")
            or key.startswith("http://")
            or key.startswith("https://")
        )
        if is_cos:
            return await self._resolve_cos_key(normalized_key)

        # 4. 回退逻辑：检查常见的本地存储位置
        storage_root = os.getenv("STORAGE_ROOT")
        if storage_root:
            potential = Path(storage_root) / normalized_key
            if potential.exists():
                return potential

        # 最后回退原样返回，交由调用方处理（可能在当前目录）
        return Path(normalized_key)

    def _normalize_cloud_key(self, key: str) -> str:
        """
        归一化云端资源标识：
        - cos://bucket/path/file.txt -> bucket/path/file.txt
        - https://domain/path/file.txt?sig=... -> path/file.txt
        - 其他字符串保持原样
        """
        raw = str(key or "").strip()
        if not raw:
            return raw
        if raw.startswith("cos://"):
            return raw.replace("cos://", "", 1).lstrip("/")
        if raw.startswith(("http://", "https://")):
            parsed = urlparse(raw)
            path = unquote(parsed.path or "").lstrip("/")
            return path
        return raw

    async def _resolve_db_strategy(self, strategy_id: int) -> Path:
        """
        从数据库 strategies 表读取 strategy_code (存储在 config.code 中)
        并导出为临时文件，以便回测引擎加载。
        """
        if not get_db:
            raise RuntimeError("Database connections not available in shared layer")

        # 确保初始化
        if init_default_databases:
            try:
                init_default_databases()
            except Exception as e:
                logger.warning(f"Database init failed: {e}")

        try:
            with get_db() as session:
                row = session.execute(
                    text("SELECT config, name FROM strategies WHERE id = :id"),
                    {"id": strategy_id},
                ).fetchone()

                if not row:
                    raise ValueError(f"Strategy ID {strategy_id} not found in database")

                config_data = row[0]
                if isinstance(config_data, str):
                    try:
                        config_data = json.loads(config_data)
                    except:
                        config_data = {}

                code = config_data.get("code")
                if not code:
                    raise ValueError(f"Strategy {strategy_id} has no code in 'config.code' field")

                # 构造文件名
                safe_name = "".join([c if c.isalnum() else "_" for c in str(row[1] or "unnamed")])
                filename = f"db_strategy_{strategy_id}_{safe_name}.py"
                local_path = self.cache_dir / filename

                # 写入文件
                local_path.write_text(code, encoding="utf-8")
                logger.info(f"Resolved strategy {strategy_id} to local file: {local_path}")
                return local_path

        except Exception as e:
            logger.error(f"Failed to resolve strategy from DB: {e}")
            raise

    async def _resolve_cos_key(self, key: str) -> Path:
        """
        将 COS 上的对象下载到本地缓存目录。
        """
        # 映射 Key 到扁平文件名
        safe_filename = key.replace("/", "_").replace("\\", "_")
        local_path = self.cache_dir / safe_filename

        # 简单的缓存检查 (生产环境可增加 TTL 或 Hash 校验)
        if local_path.exists():
            return local_path

        # 如果没有配置 COS，或者强制本地模式，尝试直接从本地文件系统读取
        storage_mode = os.getenv("STORAGE_MODE", "cos").lower()
        if storage_mode == "local" or not self.cos_service or not self.cos_service.client:
            storage_root = os.getenv("STORAGE_ROOT", "/tmp/quantmind_strategies")
            potential = Path(storage_root) / key
            if potential.exists():
                return potential
            raise RuntimeError(f"Storage mode is LOCAL but file not found: {potential}")

        # 执行 COS 下载
        try:
            logger.info(f"Downloading {key} from COS...")
            response = self.cos_service.client.get_object(Bucket=self.cos_service.bucket_name, Key=key)
            content = response["Body"].get_raw_stream().read()

            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(content)
            logger.info(f"Downloaded {key} to {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {key} from COS: {e}")
            raise


# Singleton instance access
_resolver = None


def get_storage_resolver() -> StorageResolver:
    global _resolver
    if _resolver is None:
        _resolver = StorageResolver()
    return _resolver
