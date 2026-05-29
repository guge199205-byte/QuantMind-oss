import logging
from datetime import date as date_cls
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 系统保留列，不作为特征列返回
_SYSTEM_COLUMNS = {"trade_date", "date", "symbol", "stock_name", "industry", "province", "updated_at", "features"}


class ETLWorker:
    def __init__(self, db_session: Session):
        self.db = db_session

    @staticmethod
    def _parse_trade_date(date_value: Any) -> date_cls:
        if isinstance(date_value, date_cls):
            return date_value
        if isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        raise ValueError(f"Unsupported date format: {date_value!r}")

    def _get_feature_columns(self) -> list[str]:
        """
        动态从 market_data_daily 表获取所有非系统列名，作为特征列。
        若无法内省则返回已知的 10 个基础列名。
        """
        try:
            inspector = inspect(self.db.bind)
            all_cols = [c["name"] for c in inspector.get_columns("stock_daily_latest")]
            return [c for c in all_cols if c not in _SYSTEM_COLUMNS]
        except Exception:
            # 内省失败时退回到已知基础列
            return [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "vwap",
                "returns_1d",
                "turnover_rate",
                "adj_factor",
            ]

    def load_features_from_db(self, date: str) -> pd.DataFrame:
        """
        从数据库加载指定日期的特征数据，返回 DataFrame。
        Index: symbol
        Columns: 所有非系统列（动态获取，不硬编码维度）
        """
        logger.info(f"Loading features for date: {date}")
        trade_date = self._parse_trade_date(date)

        feature_cols = self._get_feature_columns()
        rows: list[dict[str, Any]] = []

        if feature_cols:
            try:
                cols_sql = ", ".join(f'"{c}"' for c in feature_cols)
                stmt = text(f"""
                    SELECT symbol, {cols_sql}
                    FROM stock_daily_latest
                    WHERE trade_date = :trade_date
                    """)
                rows = self.db.execute(stmt, {"trade_date": trade_date}).mappings().all()
            except Exception as e:
                # 兼容旧表结构（仅 features JSONB）
                logger.warning(f"Fallback to legacy market_data_daily schema: {e}")
                feature_cols = []

            # 如果 stock_daily_latest 为空，不再回退到 MarketDataDaily，因为表结构完全不同
            logger.warning(f"No data found in stock_daily_latest for {trade_date}")
            return pd.DataFrame()

        if not rows:
            logger.warning(f"No data found for date {trade_date}")
            return pd.DataFrame()

        data_list = []
        for row in rows:
            symbol = row.get("symbol")
            record: dict[str, Any] = {"symbol": symbol}

            # 优先读取具名列
            named_values = {c: row.get(c) for c in feature_cols if row.get(c) is not None}
            if named_values:
                record.update(named_values)
            else:
                # fallback：从 JSONB features 展开为 feature_0, feature_1, ...
                features = row.get("features")
                if isinstance(features, list) and features:
                    try:
                        record.update({f"feature_{i}": float(v) for i, v in enumerate(features)})
                    except Exception:
                        logger.error(f"Invalid feature format for {symbol}: cannot parse JSONB features")
                        continue
                else:
                    logger.warning(f"No usable features for {symbol}, skipping")
                    continue

            data_list.append(record)

        df = pd.DataFrame(data_list)
        if df.empty:
            return df

        df.set_index("symbol", inplace=True)
        return df
