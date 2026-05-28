"""
数据源注册中心。

适配器在自身模块里通过 @register_source 装饰器或 register_source() 函数挂载，
聚合层根据字段路由表（field_routing.yaml）按名字调用。
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Type

from backend.services.engine.data_platform.base import OfflineDataSourceAdapter

logger = logging.getLogger(__name__)


class SourceRegistry:
    """线程安全的数据源注册表。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._classes: dict[str, Type[OfflineDataSourceAdapter]] = {}
        self._instances: dict[str, OfflineDataSourceAdapter] = {}

    def register(
        self,
        adapter_cls: Type[OfflineDataSourceAdapter],
        *,
        name: Optional[str] = None,
    ) -> Type[OfflineDataSourceAdapter]:
        with self._lock:
            n = (name or adapter_cls.name or "").strip()
            if not n:
                raise ValueError(f"adapter {adapter_cls.__name__} 缺少 name")
            if n in self._classes:
                logger.warning("Data source %s already registered, overriding", n)
            self._classes[n] = adapter_cls
            # 清掉旧实例，下次 get 时重建
            self._instances.pop(n, None)
            logger.info("Registered data source: %s -> %s", n, adapter_cls.__name__)
            return adapter_cls

    def get(self, name: str) -> OfflineDataSourceAdapter:
        with self._lock:
            if name not in self._classes:
                raise KeyError(f"数据源 {name} 未注册")
            if name not in self._instances:
                self._instances[name] = self._classes[name]()
            return self._instances[name]

    def list_sources(self) -> list[str]:
        with self._lock:
            return sorted(self._classes.keys())

    def sources_for(self, field: str, market: str) -> list[str]:
        """返回该市场+字段下所有支持的源名（顺序无保证，由路由表决定优先级）。"""
        result: list[str] = []
        for name in self.list_sources():
            try:
                adapter = self.get(name)
            except Exception:  # noqa: BLE001
                continue
            if adapter.supports(field, market):
                result.append(name)
        return result

    def clear(self) -> None:
        """仅用于测试。"""
        with self._lock:
            self._classes.clear()
            self._instances.clear()


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------
_registry: Optional[SourceRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> SourceRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = SourceRegistry()
    return _registry


def register_source(name: Optional[str] = None):
    """类装饰器：@register_source("baostock")"""

    def _wrap(cls: Type[OfflineDataSourceAdapter]) -> Type[OfflineDataSourceAdapter]:
        get_registry().register(cls, name=name)
        return cls

    return _wrap
