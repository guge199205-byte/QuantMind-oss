"""
轻量 Qlib 回测适配器

作用：
- 统一对 Qlib 初始化与配置的入口
- 提供 run_backtest 方法，接受 Qlib 的 strategy/executor 配置字典或实例
- 若 Qlib 未安装或未准备数据时，给出可读错误，便于上层降级
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 计算项目根目录
try:
    _current_dir = Path(__file__).resolve().parent
    # integration -> backtest_engine -> shared -> backend -> quantmind
    PROJECT_ROOT = _current_dir.parents[4]
except Exception:
    PROJECT_ROOT = Path(os.getcwd())

_default_rel_path = os.path.join("db", "qlib_data")
# 如果环境变量未设置，尝试基于项目根目录解析默认路径
if "QLIB_PROVIDER_URI" not in os.environ and (PROJECT_ROOT / _default_rel_path).exists():
    DEFAULT_PROVIDER_URI = str(PROJECT_ROOT / _default_rel_path)
else:
    DEFAULT_PROVIDER_URI = os.getenv("QLIB_PROVIDER_URI", str(_default_rel_path))


class QlibNotAvailable(Exception):
    """Qlib 未安装或未初始化时抛出的异常"""


class QlibBacktestAdapter:
    """封装 Qlib 初始化与回测调用"""

    def __init__(
        self,
        provider_uri: str = DEFAULT_PROVIDER_URI,
        region: str = "cn",
        auto_init: bool = True,
    ) -> None:
        self.provider_uri = provider_uri
        self.region = region
        self.auto_init = auto_init
        self.logger = logging.getLogger(__name__)

    def ensure_qlib(self) -> None:
        """检查并初始化 Qlib"""
        try:
            import qlib
        except ImportError as e:  # noqa: BLE001
            raise QlibNotAvailable("pyqlib 未安装，请先 pip install pyqlib") from e

        if not qlib.is_initialized():
            if not self.auto_init:
                raise QlibNotAvailable("Qlib 未初始化，且 auto_init=False")
            self.logger.info("初始化 Qlib provider_uri=%s region=%s", self.provider_uri, self.region)
            qlib.init(provider_uri=self.provider_uri, region=self.region)

    def run_backtest(
        self,
        start_time: str,
        end_time: str,
        strategy: Any,
        executor: Any,
        benchmark: str = "SH000300",
        account: float = 1e9,
        exchange_kwargs: dict[str, Any] | None = None,
        pos_type: str = "Position",
        codes: list | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        调用 Qlib backtest，返回 (portfolio_dict, indicator_dict)

        Args:
            start_time: 回测开始时间（闭区间）
            end_time: 回测结束时间（闭区间）
            strategy: Qlib strategy 实例或配置
            executor: Qlib executor 实例或配置
            benchmark: 基准代码
            account: 初始资金
            exchange_kwargs: 透传给 Exchange 的参数（如限价、交易单元等）
            pos_type: 持仓类型
            codes: 明确的标的列表，绕过 D.instruments('all') 空列表问题
        """
        self.ensure_qlib()

        import qlib  # type: ignore  # noqa: F401
        from qlib.backtest import backtest as qlib_backtest

        exchange_kwargs = exchange_kwargs or {}
        if codes:
            exchange_kwargs.setdefault("codes", codes)
        self.logger.info(
            "调用 Qlib 回测 start=%s end=%s benchmark=%s",
            start_time,
            end_time,
            benchmark,
        )
        portfolio_dict, indicator_dict = qlib_backtest(
            start_time=start_time,
            end_time=end_time,
            strategy=strategy,
            executor=executor,
            benchmark=benchmark,
            account=account,
            exchange_kwargs=exchange_kwargs,
            pos_type=pos_type,
        )

        # 将返回值转为 Python 原生结构，便于 FastAPI/JSON 序列化
        def _df_to_dict(df_or_tuple: Any) -> Any:
            if hasattr(df_or_tuple, "to_dict"):
                return df_or_tuple.to_dict()
            return df_or_tuple

        portfolio_serializable = {freq: (_df_to_dict(df), metadata) for freq, (df, metadata) in portfolio_dict.items()}
        indicator_serializable = {
            freq: (_df_to_dict(df), indicator) for freq, (df, indicator) in indicator_dict.items()
        }
        return portfolio_serializable, indicator_serializable


__all__ = ["QlibBacktestAdapter", "QlibNotAvailable", "DEFAULT_PROVIDER_URI"]
