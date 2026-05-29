import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class FundamentalAligner:
    """
    统一基本面对齐器 (Unified Fundamental Aligner)

    从统一的 Parquet 文件读取预计算基本面特征，确保回测与实盘执行口径一致。
    """

    DEFAULT_PATH = "db/custom/fundamental_aligned.parquet"

    def __init__(self, parquet_path: str | None = None):
        self.parquet_path = parquet_path or os.getenv(
            "FUNDAMENTAL_ALIGN_PATH", self.DEFAULT_PATH
        )
        self._data: pd.DataFrame | None = None
        self._project_root = self._find_project_root()

        if os.path.isabs(self.parquet_path):
            self.full_path = Path(self.parquet_path)
        else:
            self.full_path = self._project_root / self.parquet_path

    def _find_project_root(self) -> Path:
        curr = Path(__file__).resolve().parent
        for _ in range(10):
            if (curr / "requirements.txt").exists() or (curr / "AGENTS.md").exists():
                return curr
            if curr.parent == curr:
                break
            curr = curr.parent
        return Path(os.getcwd())

    def _load_data(self) -> pd.DataFrame:
        if self._data is not None:
            return self._data

        if not self.full_path.exists():
            logger.warning("FundamentalAligner: 找不到对齐文件 %s", self.full_path)
            self._data = pd.DataFrame()
            return self._data

        try:
            df = pd.read_parquet(self.full_path)
            if df.empty:
                self._data = pd.DataFrame()
                return self._data

            df["trade_date"] = pd.to_datetime(df["trade_date"])

            if os.getenv("MODE") == "production":
                last_date = df["trade_date"].max()
                days_diff = (pd.Timestamp.now().normalize() - last_date.normalize()).days
                if days_diff > 2:
                    logger.error(
                        "CRITICAL: 基本面对齐数据已过期，最后日期=%s，滞后=%s天",
                        last_date.date(),
                        days_diff,
                    )

            self._data = df.set_index(["trade_date", "symbol"]).sort_index()
            logger.info("FundamentalAligner: 成功加载数据，字段数=%s", len(df.columns))
        except Exception as exc:
            logger.error("FundamentalAligner: 加载失败: %s", exc)
            self._data = pd.DataFrame()
        return self._data

    def filter_instruments(
        self,
        current_date: Any,
        instruments: list[str],
        constraints: dict[str, Any] | None = None,
    ) -> list[str]:
        data = self._load_data()
        if data.empty:
            return instruments

        dt = pd.to_datetime(current_date).normalize()
        try:
            snapshot = data.loc[dt]
        except KeyError:
            return instruments

        if not constraints:
            return instruments

        mask = pd.Series(True, index=snapshot.index)
        for key, target_val in constraints.items():
            if target_val is None:
                continue

            col = key
            op = "eq"
            if key.endswith("_max"):
                col, op = key[:-4], "le"
            elif key.endswith("_min"):
                col, op = key[:-4], "ge"
            elif key.endswith("_in"):
                col, op = key[:-3], "in"
            elif key.endswith("_not"):
                col, op = key[:-4], "ne"

            if col not in snapshot.columns:
                logger.debug("FundamentalAligner: 字段 %s 不存在，跳过", col)
                continue

            col_data = snapshot[col]
            if op == "le":
                mask &= col_data <= float(target_val)
            elif op == "ge":
                mask &= col_data >= float(target_val)
            elif op == "ne":
                mask &= col_data != target_val
            elif op == "in":
                if isinstance(target_val, (list, set, tuple)):
                    mask &= col_data.isin(target_val)
                else:
                    mask &= col_data == target_val
            else:
                mask &= col_data == target_val

        valid_symbols = set(snapshot[mask].index)
        return [symbol for symbol in instruments if symbol in valid_symbols]


fundamental_aligner = FundamentalAligner()

