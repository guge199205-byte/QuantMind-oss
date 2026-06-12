/**
 * Built-in starter snippets — drives the left-hand "示例" panel.
 *
 * Day-3 keeps this list short; Day-19 spec calls for 30 examples.
 */

export interface SnippetSpec {
  id: string;
  title: string;
  description: string;
  code: string;
}

export const STRATEGY_LAB_SNIPPETS: SnippetSpec[] = [
  {
    id: 'buy-and-hold',
    title: '买入持有 (Buy & Hold)',
    description: '最简单的回测——首日按等权买入两只股票后一直持有。',
    code: `# Strategy Lab: 买入持有
# 在 setup() 中声明 universe / 时间区间 / 资金；on_bar() 在每根 K 线被回放
# 时调用，可以发出 ctx.buy / ctx.sell 指令。

def setup(ctx):
    ctx.universe = ["sh600036", "sh000001"]   # 股票池
    ctx.start = "2024-01-02"                   # 回测开始
    ctx.end   = "2024-06-30"                   # 回测结束
    ctx.cash  = 1_000_000                      # 初始资金 (CNY)
    ctx.commission = 0.0003                    # 万三佣金
    ctx.slippage   = 0.0005                    # 5bp 滑点

def on_bar(ctx, bar):
    # 第一次见到该标的且没仓位 → 等权买入
    if ctx.position(bar.symbol).qty == 0:
        ctx.buy(bar.symbol, weight=0.4, reason="initial entry")
`,
  },
  {
    id: 'momentum',
    title: '动量轮动 (Momentum)',
    description: '每月初按过去 20 日收益率取前 N，等权重仓。',
    code: `# Strategy Lab: 动量轮动
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2024-01-02"
    ctx.end      = "2024-06-30"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    # 每个交易日都会调用,这里仅在月初再平衡
    if pd.Timestamp(date).day > 5:
        return
    # 取过去 20 个交易日的累计收益,排序选 5 只
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    top  = rets.dropna().sort_values(ascending=False).head(ctx.max_positions).index.tolist()
    ctx.set_target_holdings(top, reason=f"top-{ctx.max_positions} momentum")
`,
  },
  {
    id: 'price-break',
    title: '突破 20 日新高',
    description: '收盘价突破 20 日最高点买入,跌破 10 日最低卖出。',
    code: `# Strategy Lab: 价格突破
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start    = "2024-01-02"
    ctx.end      = "2024-06-30"
    ctx.cash     = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    if len(closes) < 20:
        return
    high20 = float(closes.max())
    low10  = float(closes.tail(10).min())
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close >= high20:
        ctx.buy(bar.symbol, weight=0.5, reason=f"break20={high20:.2f}")
    elif pos.qty > 0 and bar.close <= low10:
        ctx.sell(bar.symbol, all=True, reason=f"break10-low={low10:.2f}")
`,
  },
  {
    id: 'fib-v3',
    title: 'A/B 斐波那契 v3',
    description: '22日高低点 → 0.618(S1)/1.236(R1) → 触发 S1 入场，止损-10%/止盈+15%。',
    code: `# Strategy Lab: A/B 斐波那契 v3
# 思路：用 22 日 (≈一个月交易日) 的最高/最低构造支撑(S)与压力(R)
# - S1 = high22 * 0.786  (回撤至 0.214 处)
# - R1 = high22 * 1.236  (向上 0.236 突破)
# 触发条件：当日收盘距 S1 < 3% 时买入 5%，并设置 ±10/+15% 风控
# 注意：该例使用 set_stop_loss / set_take_profit，broker 会在
#       每日开盘前自动检查并强制平仓。

def setup(ctx):
    ctx.universe = ["sh600519"]              # 贵州茅台单股测试
    ctx.start    = "2024-01-02"
    ctx.end      = "2024-06-30"
    ctx.cash     = 1_000_000
    ctx.benchmark = "SH000300"

def on_bar(ctx, bar):
    sym = bar.symbol
    closes = ctx.history(symbol=sym, n=22, field="close")
    if len(closes) < 22:
        return
    lows = ctx.history(symbol=sym, n=22, field="low")
    high22 = float(closes.max())
    low22  = float(lows.min()) if len(lows) else high22 * 0.5
    s1 = high22 * 0.786
    r1 = high22 * 1.236

    pos = ctx.position(sym)
    near_s1 = abs(bar.close - s1) / s1 < 0.03
    if pos.qty == 0 and near_s1:
        ctx.buy(
            sym, weight=0.50,
            reason="fib_v3:S1_hit",
            detail={"close": bar.close, "s1": s1, "r1": r1, "low22": low22},
        )
        ctx.set_stop_loss(sym, -0.10)
        ctx.set_take_profit(sym, 0.15)
`,
  },
];
