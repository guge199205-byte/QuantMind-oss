"""
风控闸门模块 (RiskGate)

从 runner/main.py 剥离，集中存放所有风控逻辑：
  - 价格偏离校验
  - 账户回撤全局止损
  - 单笔金额 / 单票持仓上限
  - 换手率拦截
  - 信号指纹 + 幂等锁
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

import redis

logger = logging.getLogger(__name__)


# ─── 内部辅助 ────────────────────────────────────────────────────────────────

def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _extract_live_price(snapshot: dict[str, Any]) -> float | None:
    for key in ("Now", "last_price", "current_price", "price", "close"):
        parsed = _to_float(snapshot.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _extract_market_pct_change(snapshot: dict[str, Any]) -> float | None:
    for key in ("pct_chg", "pct_change", "change_percent", "change_pct", "pct", "ChgRatio"):
        parsed = _to_float(snapshot.get(key))
        if parsed is None:
            continue
        return parsed / 100.0 if abs(parsed) > 1 else parsed

    live_price = _extract_live_price(snapshot)
    prev_close = _to_float(snapshot.get("prev_close"))
    if live_price is not None and prev_close and prev_close > 0:
        return (live_price - prev_close) / prev_close
    return None


# ─── 公开接口 ─────────────────────────────────────────────────────────────────

class RiskGate:
    """
    无状态风控闸门，所有方法均为类方法，便于直接调用。

    调用示例（runner/main.py）::

        from backend.services.trade.runner.risk_gate import RiskGate

        signals = RiskGate.apply(signals, account, exec_config, market, live_trade_config)
        fingerprint = RiskGate.fingerprint(signals)
        if RiskGate.acquire_lock(redis_client, tenant_id, user_id, strategy, fingerprint):
            ...
    """

    @staticmethod
    def apply(
        signals: list[dict[str, Any]],
        account: dict[str, Any],
        exec_config: dict[str, Any],
        market_snapshot: dict[str, Any],
        live_trade_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        核心风控闸门 (RC2 增强版)。
        对输入信号列表做多层过滤/缩减，返回合规后的信号列表。
        """
        live_trade_config = live_trade_config or {}

        # 1. 配置加载
        max_turnover = float(exec_config.get("max_turnover_ratio_per_cycle", 0.20))
        stop_loss_threshold = float(
            exec_config.get("stop_loss", exec_config.get("global_stop_loss_drawdown", -0.08))
        )
        max_buy_drop = float(exec_config.get("max_buy_drop", -0.03))
        max_single_stock_ratio = float(exec_config.get("max_single_stock_ratio", 0.15))
        max_order_value = float(exec_config.get("max_order_value_absolute", 500000))
        max_price_dev = float(
            live_trade_config.get("max_price_deviation", exec_config.get("max_price_deviation", 0.02))
        )

        total_value = float(account.get("total_value") or 0)
        current_drawdown = float(account.get("drawdown") or 0)
        existing_positions = account.get("positions") or {}

        # 2. 全局止损：只保留平仓信号
        if current_drawdown <= stop_loss_threshold and total_value > 0:
            logger.warning(
                "[Risk] 账户回撤 (%.2f) 触发全局止损 (%.2f)，拦截所有开仓信号",
                current_drawdown,
                stop_loss_threshold,
            )
            signals = [s for s in signals if s.get("trade_action") in {"SELL_TO_CLOSE", "BUY_TO_CLOSE"}]

        # 3. 逐单合规性检查
        passed_signals = []
        for s in signals:
            symbol = s["symbol"]
            price = float(s["price"])
            volume = float(s["volume"])
            notional = price * volume

            # A. 价格离散度校验
            if market_snapshot and symbol in market_snapshot:
                snapshot = market_snapshot[symbol]
                live_price = _extract_live_price(snapshot)
                if live_price is not None and live_price > 0:
                    dev = abs(price - live_price) / live_price
                    if dev > max_price_dev:
                        logger.warning(
                            "[Risk] %s 信号价(%.2f) 与市价(%.2f) 偏离 %.2f%%，拦截",
                            symbol, price, live_price, dev * 100,
                        )
                        continue

            trade_action = str(s.get("trade_action") or "").upper()
            if market_snapshot and symbol in market_snapshot:
                pct_change = _extract_market_pct_change(market_snapshot[symbol])
                if pct_change is not None:
                    # B. 多头大跌拦截
                    if trade_action == "BUY_TO_OPEN" and pct_change <= max_buy_drop:
                        logger.warning(
                            "[Risk] %s 涨跌幅 %.2f%% 触发多头大跌拦截，动作=%s",
                            symbol, pct_change * 100, trade_action,
                        )
                        continue
                    # C. 空头大涨拦截
                    elif trade_action == "SELL_TO_OPEN" and pct_change >= abs(max_buy_drop):
                        logger.warning(
                            "[Risk] %s 涨跌幅 %.2f%% 触发空头大涨拦截，动作=%s",
                            symbol, pct_change * 100, trade_action,
                        )
                        continue

            # D. 单笔金额上限
            if notional > max_order_value:
                logger.warning(
                    "[Risk] %s 订单金额 %.2f 超过限制 %.2f，自动缩减数量",
                    symbol, notional, max_order_value,
                )
                volume = (max_order_value / price) // 100 * 100
                s["volume"] = int(volume)
                notional = price * volume

            # E. 单票持仓上限
            current_pos_value = float(existing_positions.get(symbol, {}).get("market_value") or 0)
            if total_value > 0 and (current_pos_value + notional) / total_value > max_single_stock_ratio:
                logger.warning(
                    "[Risk] %s 预期持仓比 %.2f%% 超过上限 %.2f%%，缩减",
                    symbol,
                    (current_pos_value + notional) / total_value * 100,
                    max_single_stock_ratio * 100,
                )
                allowed_notional = (total_value * max_single_stock_ratio) - current_pos_value
                if allowed_notional <= 0:
                    continue
                s["volume"] = int((allowed_notional / price) // 100 * 100)

            if float(s["volume"]) > 0:
                passed_signals.append(s)

        # 4. 换手率拦截（等比例缩减）
        final_signals = passed_signals
        estimated_turnover = sum(float(s["volume"]) * float(s["price"]) for s in final_signals)
        if total_value > 0 and (estimated_turnover / total_value) > max_turnover:
            logger.warning(
                "[Risk] 本轮换手率 (%.2f) 超过限制 (%.2f)，等比例缩减",
                estimated_turnover / total_value,
                max_turnover,
            )
            ratio = (total_value * max_turnover) / estimated_turnover
            for s in final_signals:
                s["volume"] = int(float(s["volume"]) * ratio // 100 * 100)

        final_signals = [s for s in final_signals if float(s["volume"]) > 0]
        logger.info(
            "[Risk] 原始=%d -> 合规后=%d -> 换手率缩减后=%d | Drawdown: %.4f",
            len(signals),
            len(passed_signals),
            len(final_signals),
            current_drawdown,
        )
        return final_signals

    @staticmethod
    def fingerprint(signals: list[dict[str, Any]]) -> str:
        """计算信号批次指纹，用于幂等锁键。"""
        sorted_sigs = sorted(signals, key=lambda x: x["symbol"] + x["action"])
        raw = "|".join([f"{s['symbol']}:{s['action']}:{s['volume']}" for s in sorted_sigs])
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def acquire_lock(
        redis_client: redis.Redis,
        tenant_id: str,
        user_id: str,
        strategy: str,
        fingerprint: str,
        ttl_seconds: int = 86400,
    ) -> bool:
        """
        获取幂等锁（NX SET）。
        返回 True 表示首次出现（应下单）；False 表示重复（应跳过）。
        """
        lock_key = f"qm:lock:signal:{tenant_id}:{user_id}:{strategy}:{fingerprint}"
        return bool(redis_client.set(lock_key, "1", ex=ttl_seconds, nx=True))
