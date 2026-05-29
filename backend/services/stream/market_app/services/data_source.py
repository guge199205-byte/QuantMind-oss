"""Data source adapter for fetching market data"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class DataSourceAdapter(ABC):
    """数据源适配器基类"""

    @abstractmethod
    async def fetch_quote(self, symbol: str) -> dict[str, Any] | None:
        """获取实时行情"""

    @abstractmethod
    async def fetch_kline(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取K线数据"""

    @abstractmethod
    async def fetch_symbols(self, market: str | None = None) -> list[dict[str, Any]]:
        """获取交易标的列表"""


class TencentDataSource(DataSourceAdapter):
    """腾讯财经数据源"""

    BASE_URL = "https://qt.gtimg.cn"

    async def fetch_quote(self, symbol: str) -> dict[str, Any] | None:
        """获取实时行情"""
        try:
            # 转换股票代码格式 (sh000001 -> sh000001)
            formatted_symbol = self._format_symbol(symbol)
            url = f"{self.BASE_URL}/q={formatted_symbol}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch quote from Tencent: {resp.status}")
                        return None

                    text = await resp.text()
                    return self._parse_quote(text, symbol)

        except Exception as e:
            logger.error(f"Error fetching quote from Tencent: {e}")
            return None

    async def fetch_kline(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取K线数据（腾讯公开接口）"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            token = self._map_tencent_interval(interval)
            if not token:
                logger.warning("Unsupported interval for Tencent kline: %s", interval)
                return []

            if token in {"day", "week", "month"}:
                # 复权日/周/月线
                url = (
                    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                    f"?param={formatted_symbol},{token},,,{limit},qfq"
                )
            else:
                # 分钟线
                url = "https://ifzq.gtimg.cn/appstock/app/kline/mkline" f"?param={formatted_symbol},{token},,{limit}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        logger.error("Failed to fetch kline from Tencent: %s", resp.status)
                        return []
                    payload = await resp.json(content_type=None)

            data = ((payload or {}).get("data") or {}).get(formatted_symbol) or {}
            rows = self._pick_tencent_kline_rows(data, token)
            if not rows:
                return []

            output: list[dict[str, Any]] = []
            prev_close: float | None = None
            for row in rows:
                item = self._parse_tencent_kline_row(
                    row=row,
                    symbol=symbol,
                    interval=interval,
                    prev_close=prev_close,
                )
                if not item:
                    continue
                ts = item["timestamp"]
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                output.append(item)
                prev_close = item["close_price"]

            # 保持按时间升序，返回最近 limit 条
            output.sort(key=lambda x: x["timestamp"])
            return output[-limit:]
        except Exception as e:
            logger.error(f"Error fetching kline from Tencent: {e}")
            return []

    async def fetch_symbols(self, market: str | None = None) -> list[dict[str, Any]]:
        """获取交易标的列表"""
        logger.warning("Tencent symbols API not fully implemented, returning empty list")
        return []

    def _format_symbol(self, symbol: str) -> str:
        """格式化股票代码"""
        if symbol.startswith("sh") or symbol.startswith("sz"):
            return symbol

        # 根据代码推断市场
        if symbol.startswith("6"):
            return f"sh{symbol}"
        elif symbol.startswith("0") or symbol.startswith("3"):
            return f"sz{symbol}"
        else:
            return symbol

    def _parse_quote(self, text: str, symbol: str) -> dict[str, Any] | None:
        """解析行情数据"""
        try:
            # v_sh000001="1~上证指数~000001~3241.83~3251.85~3241.83~..."
            if "~" not in text:
                return None

            parts = text.split("~")
            if len(parts) < 40:
                return None

            current_price = float(parts[3]) if parts[3] else 0.0
            pre_close = float(parts[4]) if parts[4] else 0.0
            open_price = float(parts[5]) if parts[5] else 0.0
            volume = int(parts[6]) if parts[6] else 0

            change = current_price - pre_close
            change_percent = (change / pre_close * 100) if pre_close > 0 else 0.0

            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "current_price": current_price,
                "open_price": open_price,
                "high_price": float(parts[33]) if parts[33] else 0.0,
                "low_price": float(parts[34]) if parts[34] else 0.0,
                "pre_close": pre_close,
                "volume": volume,
                "amount": float(parts[37]) if parts[37] else 0.0,
                "change": change,
                "change_percent": round(change_percent, 2),
                # Bid 1-5
                "bid1_price": float(parts[9]) if parts[9] else 0.0,
                "bid1_volume": int(parts[10]) if parts[10] else 0,
                "bid2_price": (float(parts[11]) if len(parts) > 11 and parts[11] else 0.0),
                "bid2_volume": int(parts[12]) if len(parts) > 12 and parts[12] else 0,
                "bid3_price": (float(parts[13]) if len(parts) > 13 and parts[13] else 0.0),
                "bid3_volume": int(parts[14]) if len(parts) > 14 and parts[14] else 0,
                "bid4_price": (float(parts[15]) if len(parts) > 15 and parts[15] else 0.0),
                "bid4_volume": int(parts[16]) if len(parts) > 16 and parts[16] else 0,
                "bid5_price": (float(parts[17]) if len(parts) > 17 and parts[17] else 0.0),
                "bid5_volume": int(parts[18]) if len(parts) > 18 and parts[18] else 0,
                # Ask 1-5
                "ask1_price": float(parts[19]) if parts[19] else 0.0,
                "ask1_volume": int(parts[20]) if parts[20] else 0,
                "ask2_price": (float(parts[21]) if len(parts) > 21 and parts[21] else 0.0),
                "ask2_volume": int(parts[22]) if len(parts) > 22 and parts[22] else 0,
                "ask3_price": (float(parts[23]) if len(parts) > 23 and parts[23] else 0.0),
                "ask3_volume": int(parts[24]) if len(parts) > 24 and parts[24] else 0,
                "ask4_price": (float(parts[25]) if len(parts) > 25 and parts[25] else 0.0),
                "ask4_volume": int(parts[26]) if len(parts) > 26 and parts[26] else 0,
                "ask5_price": (float(parts[27]) if len(parts) > 27 and parts[27] else 0.0),
                "ask5_volume": int(parts[28]) if len(parts) > 28 and parts[28] else 0,
                "data_source": "tencent",
            }
        except Exception as e:
            logger.error(f"Error parsing quote: {e}")
            return None

    def _map_tencent_interval(self, interval: str) -> str | None:
        raw = (interval or "").strip()
        # 兼容 1M(月线) 与 1m(分钟线)
        if raw == "1M":
            return "month"
        key = raw.lower()
        interval_map = {
            "1m": "m1",
            "5m": "m5",
            "15m": "m15",
            "30m": "m30",
            "1h": "m60",
            "1d": "day",
            "1w": "week",
            "1mo": "month",
            "1mon": "month",
        }
        return interval_map.get(key)

    def _pick_tencent_kline_rows(self, data: dict[str, Any], token: str) -> list[list[Any]]:
        # fqkline/get 常见字段：qfqday / day / week / month
        if token in {"day", "week", "month"}:
            for key in (f"qfq{token}", token, f"hfq{token}"):
                rows = data.get(key)
                if isinstance(rows, list):
                    return rows
            return []
        # mkline 常见字段：m1/m5/m15/m30/m60
        rows = data.get(token)
        return rows if isinstance(rows, list) else []

    def _parse_tencent_kline_row(
        self,
        row: list[Any],
        symbol: str,
        interval: str,
        prev_close: float | None,
    ) -> dict[str, Any] | None:
        try:
            if len(row) < 6:
                return None
            ts = self._parse_tencent_kline_time(str(row[0]))
            if ts is None:
                return None

            open_price = float(row[1] or 0)
            close_price = float(row[2] or 0)
            high_price = float(row[3] or 0)
            low_price = float(row[4] or 0)
            volume = int(float(row[5] or 0))
            amount = float(row[6]) if len(row) > 6 and row[6] not in (None, "") else None

            baseline = prev_close if prev_close and prev_close > 0 else None
            change = (close_price - baseline) if baseline else None
            change_percent = (change / baseline * 100) if baseline and change is not None else None

            return {
                "symbol": symbol,
                "interval": interval,
                "timestamp": ts,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": close_price,
                "volume": volume,
                "amount": amount,
                "change": change,
                "change_percent": round(change_percent, 4) if change_percent is not None else None,
                "turnover_rate": None,
                "data_source": "tencent",
            }
        except Exception:
            return None

    def _parse_tencent_kline_time(self, text: str) -> datetime | None:
        val = (text or "").strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d", "%Y%m%d%H%M"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None


class SinaDataSource(DataSourceAdapter):
    """新浪财经数据源"""

    BASE_URL = "https://hq.sinajs.cn"

    async def fetch_quote(self, symbol: str) -> dict[str, Any] | None:
        """获取实时行情"""
        try:
            # 转换股票代码格式 (000001 -> sh000001)
            formatted_symbol = self._format_symbol(symbol)
            url = f"{self.BASE_URL}/list={formatted_symbol}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch quote from Sina: {resp.status}")
                        return None

                    text = await resp.text()
                    return self._parse_quote(text, symbol)

        except Exception as e:
            logger.error(f"Error fetching quote from Sina: {e}")
            return None

    async def fetch_kline(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取K线数据（当前降级复用腾讯接口）"""
        logger.info("Sina kline endpoint unavailable, fallback to Tencent source")
        return await TencentDataSource().fetch_kline(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def fetch_symbols(self, market: str | None = None) -> list[dict[str, Any]]:
        """获取交易标的列表"""
        logger.warning("Sina symbols API not fully implemented, returning empty list")
        return []

    def _format_symbol(self, symbol: str) -> str:
        """格式化股票代码"""
        if symbol.startswith("sh") or symbol.startswith("sz"):
            return symbol

        if symbol.startswith("6"):
            return f"sh{symbol}"
        elif symbol.startswith("0") or symbol.startswith("3"):
            return f"sz{symbol}"
        else:
            return symbol

    def _parse_quote(self, text: str, symbol: str) -> dict[str, Any] | None:
        """解析行情数据"""
        try:
            # var hq_str_sh000001="上证指数,3241.83,3251.85,..."
            if "=" not in text:
                return None

            data_str = text.split('"')[1]
            parts = data_str.split(",")

            if len(parts) < 32:
                return None

            current_price = float(parts[3])
            pre_close = float(parts[2])
            open_price = float(parts[1])

            change = current_price - pre_close
            change_percent = (change / pre_close * 100) if pre_close > 0 else 0.0

            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "current_price": current_price,
                "open_price": open_price,
                "high_price": float(parts[4]),
                "low_price": float(parts[5]),
                "pre_close": pre_close,
                "volume": int(parts[8]),
                "amount": float(parts[9]),
                "change": change,
                "change_percent": round(change_percent, 2),
                # Bid 1-5 (Sina format: buy1_vol, buy1_price, buy2_vol, buy2_price...)
                "bid1_volume": int(parts[10]),
                "bid1_price": float(parts[11]),
                "bid2_volume": int(parts[12]),
                "bid2_price": float(parts[13]),
                "bid3_volume": int(parts[14]),
                "bid3_price": float(parts[15]),
                "bid4_volume": int(parts[16]),
                "bid4_price": float(parts[17]),
                "bid5_volume": int(parts[18]),
                "bid5_price": float(parts[19]),
                # Ask 1-5 (Sina format: sell1_vol, sell1_price...)
                "ask1_volume": int(parts[20]),
                "ask1_price": float(parts[21]),
                "ask2_volume": int(parts[22]),
                "ask2_price": float(parts[23]),
                "ask3_volume": int(parts[24]),
                "ask3_price": float(parts[25]),
                "ask4_volume": int(parts[26]),
                "ask4_price": float(parts[27]),
                "ask5_volume": int(parts[28]),
                "ask5_price": float(parts[29]),
                "data_source": "sina",
            }
        except Exception as e:
            logger.error(f"Error parsing Sina quote: {e}")
            return None


"""
注意：企业级金融业务禁止内置任何模拟/演示数据源。
如需测试，请在 tests 中使用 mock/stub，而不是在运行时代码中返回虚构行情。
"""
