"""数据源适配器注册中心。

外部调用：
    from backend.services.engine.data_platform.adapters import register_all
    register_all()

D3 第一批：baostock / efinance / qstock / investment_data / eltdx
D4 第二批：tdx_api / injoyai_tdx / simonlin_a_stock / mootdx / akshare
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# (name, registrar_callable)
_REGISTRARS: list[tuple[str, Callable[[], bool]]] = []


def _collect() -> None:
    """惰性收集所有 register() 函数，import 失败的适配器静默跳过。"""
    global _REGISTRARS
    if _REGISTRARS:
        return
    out: list[tuple[str, Callable[[], bool]]] = []

    for mod_name in (
        # D3 第一批
        "backend.services.engine.data_platform.adapters.baostock_adapter",
        "backend.services.engine.data_platform.adapters.efinance_adapter",
        "backend.services.engine.data_platform.adapters.qstock_adapter",
        "backend.services.engine.data_platform.adapters.investment_data_adapter",
        "backend.services.engine.data_platform.adapters.eltdx_adapter",
        # D4 第二批
        "backend.services.engine.data_platform.adapters.akshare_adapter",
        "backend.services.engine.data_platform.adapters.mootdx_adapter",
        "backend.services.engine.data_platform.adapters.tdx_api_adapter",
        "backend.services.engine.data_platform.adapters.injoyai_tdx_adapter",
        "backend.services.engine.data_platform.adapters.simonlin_a_stock_adapter",
        # 第三批：Yahoo Finance + simonlin_global
        "backend.services.engine.data_platform.adapters.yahoo_finance_adapter",
        "backend.services.engine.data_platform.adapters.simonlin_global_adapter",
        # 第四批：OpenBB-CN + easyquotation
        "backend.services.engine.data_platform.adapters.openbb_adapter",
        "backend.services.engine.data_platform.adapters.easyquotation_adapter",
    ):
        try:
            import importlib
            m = importlib.import_module(mod_name)
            if hasattr(m, "register"):
                out.append((mod_name.rsplit(".", 1)[-1], m.register))
        except Exception as exc:  # noqa: BLE001
            logger.warning("import adapter module %s failed: %s", mod_name, exc)

    _REGISTRARS = out


def register_all() -> dict[str, bool]:
    """注册全部可用适配器；返回 {name: success}。"""
    _collect()
    results: dict[str, bool] = {}
    for name, fn in _REGISTRARS:
        try:
            results[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001
            logger.error("adapter %s register() raised: %s", name, exc)
            results[name] = False
    logger.info("Data-source adapters registered: %s", results)
    return results


def list_known() -> list[str]:
    _collect()
    return [n for n, _ in _REGISTRARS]
