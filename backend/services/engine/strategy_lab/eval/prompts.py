"""The 30-prompt AI evaluation dataset for Strategy Lab.

Each prompt covers a distinct strategy category (trend, mean-reversion, breakout,
factor, cross-section, risk control). The expected output is valid Strategy Lab
SDK code with `setup` + at least one of `on_bar`/`on_universe`, that passes the
AST safety check and contains the required ctx config fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalPrompt:
    id: str
    category: str  # "trend" | "mean_reversion" | "breakout" | "factor" | "risk" | "cross_section" | "event"
    user_prompt: str
    must_contain: tuple[str, ...] = ()
    """Substrings that MUST appear in the generated code (semantic markers)."""


PROMPT_DATASET: tuple[EvalPrompt, ...] = (
    # --- Trend (5) ---
    EvalPrompt("p01", "trend", "写一个 20/60 双均线策略：MA20 上穿 MA60 买入，下穿全部卖出，标的茅台。",
               must_contain=("MA", "buy", "sell")),
    EvalPrompt("p02", "trend", "MACD 金叉买入死叉卖出，沪深300 池子。",
               must_contain=("MACD", "buy")),
    EvalPrompt("p03", "trend", "20 日动量为正且高于 60 日均线时入场。",
               must_contain=("buy",)),
    EvalPrompt("p04", "trend", "EMA20 上穿 EMA50 全仓买入；下穿全部清仓。",
               must_contain=("EMA", "buy", "sell")),
    EvalPrompt("p05", "trend", "趋势跟踪：Donchian 20 日通道，突破上轨买入，跌破下轨卖出。",
               must_contain=("buy", "sell")),

    # --- Mean reversion (5) ---
    EvalPrompt("p06", "mean_reversion", "RSI(14) < 30 买入，> 70 卖出，单股招商银行。",
               must_contain=("RSI", "buy", "sell")),
    EvalPrompt("p07", "mean_reversion", "布林带 BBands(20, 2) 触及下轨买入，触及上轨卖出。",
               must_contain=("buy", "sell")),
    EvalPrompt("p08", "mean_reversion", "近 5 日跌幅超 8% 的个股反弹买入，持有 5 个交易日。",
               must_contain=("buy",)),
    EvalPrompt("p09", "mean_reversion", "KDJ 金叉买入死叉卖出。",
               must_contain=("buy", "sell")),
    EvalPrompt("p10", "mean_reversion", "Z-score 方法：标的偏离 20 日均值 2 倍标准差时反向买入。",
               must_contain=("buy",)),

    # --- Breakout / Fibonacci (4) ---
    EvalPrompt("p11", "breakout", "海龟交易：20 日最高突破入场，10 日最低出场。",
               must_contain=("buy", "sell")),
    EvalPrompt("p12", "breakout", "斐波那契回撤：22 日高点 0.618 处买入，止损 -10%，止盈 15%。",
               must_contain=("buy", "set_stop_loss")),
    EvalPrompt("p13", "breakout", "ATR 突破：当日收盘 > 20 日均线 + 2*ATR(14) 时买入。",
               must_contain=("buy",)),
    EvalPrompt("p14", "breakout", "缩量突破：放量突破 20 日新高后买入。",
               must_contain=("buy",)),

    # --- Factor / cross-section (8) ---
    EvalPrompt("p15", "cross_section", "csi300 中按 20 日动量排序，前 5 名等权持有，每月初再平衡。",
               must_contain=("csi300", "set_target_holdings")),
    EvalPrompt("p16", "cross_section", "PE < 15 且 ROE > 15% 的股票按动量取前 10 名。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p17", "cross_section", "小市值反转：选市值最小的 30 支，每月再平衡。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p18", "cross_section", "PEG < 1 且 ROE > 10% 的股票按市值倒序取前 5 支。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p19", "cross_section", "PB < 1 且 ROE 转正的股票，每月初等权买入前 8 支。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p20", "factor", "三因子打分：价值 + 质量 + 动量等权合成，取前 30 支。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p21", "factor", "行业轮动：取过去 20 日动量最强的 3 个一级行业各前 5 支。",
               must_contain=("set_target_holdings",)),
    EvalPrompt("p22", "cross_section", "北上资金跟随：北向持股增量前 20 等权买入。",
               must_contain=("set_target_holdings",)),

    # --- Risk control (4) ---
    EvalPrompt("p23", "risk", "单股止损 -8% 止盈 +15%，标的贵州茅台。",
               must_contain=("set_stop_loss", "set_take_profit")),
    EvalPrompt("p24", "risk", "账户级止损 -20%，触发后清仓。",
               must_contain=("set_account_stop_loss",)),
    EvalPrompt("p25", "risk", "最长持有 30 天，超期强制卖出。",
               must_contain=("set_max_holding_days",)),
    EvalPrompt("p26", "risk", "动态止损：跌破入场价 -10% 或盈利回撤超过最高点 5% 时卖出。",
               must_contain=("set_stop_loss",)),

    # --- Event / advanced (4) ---
    EvalPrompt("p27", "event", "财报发布前 5 个交易日埋伏，发布后第二日卖出。",
               must_contain=("buy", "sell")),
    EvalPrompt("p28", "event", "连续 2 个涨停后第 3 日打板买入。",
               must_contain=("buy",)),
    EvalPrompt("p29", "event", "龙虎榜跟随：上榜后次日开盘买入，持有 5 天。",
               must_contain=("buy",)),
    EvalPrompt("p30", "event", "网格交易：3% 分档，跌一档买，涨一档卖。",
               must_contain=("buy", "sell")),
)

assert len(PROMPT_DATASET) == 30, "evaluation gate requires exactly 30 prompts"
