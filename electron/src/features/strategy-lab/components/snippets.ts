/**
 * Built-in starter snippets — drives the left-hand "示例" panel.
 *
 * Day-18: extended to 30 entries grouped by 7 categories. Each is a
 * runnable, self-contained example that compiles under the SDK sandbox.
 *
 * Categories:
 *   - basic    基础 (entry-level, single-symbol)
 *   - trend    趋势 (moving averages, breakouts, channels)
 *   - reversal 反转 (mean-reversion, RSI, Bollinger)
 *   - timing   择时 (calendar / event triggers)
 *   - volume   量价 (volume-confirmation, OBV)
 *   - cross    横截面 (rank/score across universe)
 *   - factor   多因子 (composite signals)
 */

export type SnippetCategory =
  | 'basic'
  | 'trend'
  | 'reversal'
  | 'timing'
  | 'volume'
  | 'cross'
  | 'factor';

export interface SnippetSpec {
  id: string;
  title: string;
  description: string;
  category: SnippetCategory;
  code: string;
}

export const CATEGORY_LABELS: Record<SnippetCategory, string> = {
  basic: '基础',
  trend: '趋势',
  reversal: '反转',
  timing: '择时',
  volume: '量价',
  cross: '横截面',
  factor: '多因子',
};

export const STRATEGY_LAB_SNIPPETS: SnippetSpec[] = [
  // --------------------------------------------------------------------
  // 基础 (4)
  // --------------------------------------------------------------------
  {
    id: 'buy-and-hold',
    title: '买入持有 (Buy & Hold)',
    description: '最简单的回测——首日按等权买入两只股票后一直持有。',
    category: 'basic',
    code: `# Strategy Lab: 买入持有
def setup(ctx):
    ctx.universe = ["sh600036", "sh000001"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000
    ctx.commission = 0.0003
    ctx.slippage   = 0.0005

def on_bar(ctx, bar):
    if ctx.position(bar.symbol).qty == 0:
        ctx.buy(bar.symbol, weight=0.4, reason="initial entry")
`,
  },
  {
    id: 'fixed-rebalance',
    title: '月初等权再平衡',
    description: '每月初按等权重调整至全 universe，其他时间不交易。',
    category: 'basic',
    code: `# Strategy Lab: 月初等权再平衡
import pandas as pd

def setup(ctx):
    ctx.universe = ["sh600036", "sh600519", "sh601318"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    ctx.set_target_holdings(ctx.universe, reason="month-start equal-weight")
`,
  },
  {
    id: 'cash-cap',
    title: '只用 50% 资金的保守版',
    description: '将买入权重限制在 0.5，剩下一半留作现金缓冲。',
    category: 'basic',
    code: `# Strategy Lab: 保守入场
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000
    ctx.max_position_per_stock = 0.5

def on_bar(ctx, bar):
    if ctx.position(bar.symbol).qty == 0:
        ctx.buy(bar.symbol, weight=0.5, reason="conservative entry")
`,
  },
  {
    id: 'param-window',
    title: '可调参数（参敏检测会用）',
    description: '用 ctx.param() 声明 window 后被 4 关卡参敏检测自动扫描。',
    category: 'basic',
    code: `# Strategy Lab: 用 ctx.param 暴露可调参数
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    n = ctx.param("window", choices=[10, 15, 20, 25, 30], default=20)
    closes = ctx.history(symbol=bar.symbol, n=n, field="close")
    if len(closes) < n:
        return
    if bar.close > float(closes.mean()) and ctx.position(bar.symbol).qty == 0:
        ctx.buy(bar.symbol, weight=0.5, reason=f"close>MA{n}")
`,
  },

  // --------------------------------------------------------------------
  // 趋势 (5)
  // --------------------------------------------------------------------
  {
    id: 'sma-cross',
    title: '双均线金叉死叉',
    description: '5 日 MA 上穿 20 日 MA 买入，下穿卖出。',
    category: 'trend',
    code: `# Strategy Lab: 双均线
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    if len(closes) < 20:
        return
    sma5  = float(closes.tail(5).mean())
    sma20 = float(closes.mean())
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and sma5 > sma20:
        ctx.buy(bar.symbol, weight=0.6, reason=f"SMA5>{sma20:.2f}")
    elif pos.qty > 0 and sma5 < sma20:
        ctx.sell(bar.symbol, all=True, reason="SMA5<SMA20 死叉")
`,
  },
  {
    id: 'price-break',
    title: '突破 20 日新高',
    description: '收盘价突破 20 日最高点买入，跌破 10 日最低卖出。',
    category: 'trend',
    code: `# Strategy Lab: 价格突破
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

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
    id: 'donchian-channel',
    title: 'Donchian 通道（海龟）',
    description: '20 日通道上轨突破做多，10 日通道下轨止损。经典海龟法则简化版。',
    category: 'trend',
    code: `# Strategy Lab: Donchian 通道
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    highs = ctx.history(symbol=bar.symbol, n=20, field="high")
    lows  = ctx.history(symbol=bar.symbol, n=10, field="low")
    if len(highs) < 20 or len(lows) < 10:
        return
    upper = float(highs.iloc[:-1].max())
    lower = float(lows.iloc[:-1].min())
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close > upper:
        ctx.buy(bar.symbol, weight=0.5, reason=f"donchian-up={upper:.2f}")
    elif pos.qty > 0 and bar.close < lower:
        ctx.sell(bar.symbol, all=True, reason=f"donchian-low={lower:.2f}")
`,
  },
  {
    id: 'macd',
    title: 'MACD 柱翻红',
    description: 'DIF 上穿 DEA 时进场（简化版 MACD）。',
    category: 'trend',
    code: `# Strategy Lab: MACD
def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=40, field="close")
    if len(closes) < 35:
        return
    dif = _ema(closes, 12) - _ema(closes, 26)
    dea = _ema(dif, 9)
    macd_now  = dif.iloc[-1] - dea.iloc[-1]
    macd_prev = dif.iloc[-2] - dea.iloc[-2]
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and macd_prev <= 0 < macd_now:
        ctx.buy(bar.symbol, weight=0.5, reason="MACD 翻红")
    elif pos.qty > 0 and macd_prev >= 0 > macd_now:
        ctx.sell(bar.symbol, all=True, reason="MACD 翻绿")
`,
  },
  {
    id: 'adx-trend-filter',
    title: 'ADX 趋势过滤后买入',
    description: '用 14 日真实波动率近似 ADX；趋势够强（ADX>25）才允许 SMA 多头入场。',
    category: 'trend',
    code: `# Strategy Lab: 趋势过滤
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=30, field="close")
    if len(closes) < 30:
        return
    rets = closes.pct_change().dropna()
    trend_strength = float(abs(rets.tail(14).mean()) / (rets.tail(14).std() + 1e-9)) * 100
    sma20 = float(closes.tail(20).mean())
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close > sma20 and trend_strength > 25:
        ctx.buy(bar.symbol, weight=0.5, reason=f"ADX≈{trend_strength:.1f}")
    elif pos.qty > 0 and (bar.close < sma20 or trend_strength < 15):
        ctx.sell(bar.symbol, all=True, reason="趋势减弱")
`,
  },

  // --------------------------------------------------------------------
  // 反转 (4)
  // --------------------------------------------------------------------
  {
    id: 'rsi-oversold',
    title: 'RSI 超卖反弹',
    description: 'RSI(14) < 30 买入，RSI > 70 卖出。',
    category: 'reversal',
    code: `# Strategy Lab: RSI 超卖
def _rsi(s, n=14):
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = -delta.clip(upper=0).rolling(n).mean()
    rs = gain / (loss + 1e-9)
    return 100 - 100 / (1 + rs)

def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=30, field="close")
    if len(closes) < 20:
        return
    rsi = _rsi(closes).iloc[-1]
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and rsi < 30:
        ctx.buy(bar.symbol, weight=0.5, reason=f"RSI={rsi:.1f}")
    elif pos.qty > 0 and rsi > 70:
        ctx.sell(bar.symbol, all=True, reason=f"RSI={rsi:.1f}")
`,
  },
  {
    id: 'bbands-meanrev',
    title: '布林带均值回归',
    description: '价格触及 20 日 -2σ 下轨买入、回到中轨卖出。',
    category: 'reversal',
    code: `# Strategy Lab: 布林带均值回归
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    if len(closes) < 20:
        return
    mu = float(closes.mean())
    sd = float(closes.std())
    lower = mu - 2 * sd
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close < lower:
        ctx.buy(bar.symbol, weight=0.5, reason=f"BBlow={lower:.2f}")
    elif pos.qty > 0 and bar.close > mu:
        ctx.sell(bar.symbol, all=True, reason=f"回中轨={mu:.2f}")
`,
  },
  {
    id: 'fib-v3',
    title: 'A/B 斐波那契 v3',
    description: '22 日高低构造 S1/R1，触发 S1 买入并设 ±10/+15% 风控。',
    category: 'reversal',
    code: `# Strategy Lab: 斐波那契 v3
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000
    ctx.benchmark = "SH000300"

def on_bar(ctx, bar):
    sym = bar.symbol
    closes = ctx.history(symbol=sym, n=22, field="close")
    if len(closes) < 22:
        return
    high22 = float(closes.max())
    s1 = high22 * 0.786
    near_s1 = abs(bar.close - s1) / s1 < 0.03
    if ctx.position(sym).qty == 0 and near_s1:
        ctx.buy(sym, weight=0.50, reason="fib_v3:S1_hit",
                detail={"close": bar.close, "s1": s1})
        ctx.set_stop_loss(sym, -0.10)
        ctx.set_take_profit(sym, 0.15)
`,
  },
  {
    id: 'kdj-oversold',
    title: 'KDJ 超卖金叉',
    description: 'K 与 D 均小于 20 且 K 上穿 D 时买入。',
    category: 'reversal',
    code: `# Strategy Lab: KDJ
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    n = 9
    high = ctx.history(symbol=bar.symbol, n=n, field="high")
    low  = ctx.history(symbol=bar.symbol, n=n, field="low")
    close = ctx.history(symbol=bar.symbol, n=n, field="close")
    if len(close) < n:
        return
    rsv = (close.iloc[-1] - low.min()) / (high.max() - low.min() + 1e-9) * 100
    k = float(rsv)
    d = float((rsv + close.iloc[-2:].mean()) / 2)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and k < 20 and d < 20 and k > d:
        ctx.buy(bar.symbol, weight=0.5, reason=f"KDJ K={k:.0f} D={d:.0f}")
    elif pos.qty > 0 and k > 80:
        ctx.sell(bar.symbol, all=True, reason=f"KDJ 超买 K={k:.0f}")
`,
  },

  // --------------------------------------------------------------------
  // 择时 (4)
  // --------------------------------------------------------------------
  {
    id: 'turn-of-month',
    title: '月底末日 → 月初买入持有 3 天',
    description: '日历效应：月末最后一天买入，持仓三天后清仓。',
    category: 'timing',
    code: `# Strategy Lab: 月度效应
import pandas as pd

def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    today = pd.Timestamp(ctx.now())
    last_day_of_month = (today + pd.offsets.MonthEnd(0)).day == today.day
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and last_day_of_month:
        ctx.buy(bar.symbol, weight=0.6, reason="月末买入")
    elif pos.qty > 0 and today.day in (3, 4, 5):
        ctx.sell(bar.symbol, all=True, reason="月初离场")
`,
  },
  {
    id: 'gap-up',
    title: '高开缺口反向做多',
    description: '收盘价较前日高开超过 1% 时买入，次日卖出。',
    category: 'timing',
    code: `# Strategy Lab: 高开缺口
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=2, field="close")
    if len(closes) < 2:
        return
    prev_close = float(closes.iloc[-2])
    gap = (bar.open - prev_close) / prev_close
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and gap > 0.01:
        ctx.buy(bar.symbol, weight=0.5, reason=f"gap={gap*100:.2f}%")
    elif pos.qty > 0:
        ctx.sell(bar.symbol, all=True, reason="持仓 1 日离场")
`,
  },
  {
    id: 'turnaround-3day',
    title: '连跌三日反弹买入',
    description: '连续三个收阴 K，第四日开盘买入，止盈 5%。',
    category: 'timing',
    code: `# Strategy Lab: 连跌反弹
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    opens  = ctx.history(symbol=bar.symbol, n=4, field="open")
    closes = ctx.history(symbol=bar.symbol, n=4, field="close")
    if len(closes) < 4:
        return
    cnt = sum(int(c < o) for o, c in zip(opens.iloc[-4:-1], closes.iloc[-4:-1]))
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and cnt == 3:
        ctx.buy(bar.symbol, weight=0.5, reason="3 阴反弹")
        ctx.set_take_profit(bar.symbol, 0.05)
`,
  },
  {
    id: 'volatility-target',
    title: '低波动期满仓',
    description: '近 20 日年化波动率低于 18% 才入场，否则空仓。',
    category: 'timing',
    code: `# Strategy Lab: 波动率择时
import math

def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    if len(closes) < 20:
        return
    vol = float(closes.pct_change().std()) * math.sqrt(252)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and vol < 0.18:
        ctx.buy(bar.symbol, weight=0.7, reason=f"vol={vol:.2f}")
    elif pos.qty > 0 and vol > 0.30:
        ctx.sell(bar.symbol, all=True, reason="波动放大")
`,
  },

  // --------------------------------------------------------------------
  // 量价 (4)
  // --------------------------------------------------------------------
  {
    id: 'volume-breakout',
    title: '放量突破',
    description: '收盘新高且成交量超过 5 日均量 1.5 倍买入。',
    category: 'volume',
    code: `# Strategy Lab: 放量突破
def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    vols   = ctx.history(symbol=bar.symbol, n=5,  field="volume")
    if len(closes) < 20 or len(vols) < 5:
        return
    high20 = float(closes.max())
    vol_ma = float(vols.mean())
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close >= high20 and bar.volume > vol_ma * 1.5:
        ctx.buy(bar.symbol, weight=0.5, reason="放量破 20")
`,
  },
  {
    id: 'volume-shrink-bot',
    title: '缩量止跌买入',
    description: '收阴但量能小于 5 日均量 0.6，视为抛压减弱。',
    category: 'volume',
    code: `# Strategy Lab: 缩量止跌
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    vols = ctx.history(symbol=bar.symbol, n=5, field="volume")
    if len(vols) < 5:
        return
    vol_ma = float(vols.mean())
    if (bar.close < bar.open) and bar.volume < vol_ma * 0.6:
        if ctx.position(bar.symbol).qty == 0:
            ctx.buy(bar.symbol, weight=0.4, reason="缩量阴线")
            ctx.set_take_profit(bar.symbol, 0.08)
`,
  },
  {
    id: 'obv-confirm',
    title: 'OBV 同步上涨确认',
    description: '价格突破 20 日新高且 OBV 也创新高才入场。',
    category: 'volume',
    code: `# Strategy Lab: OBV 确认
import numpy as np

def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=21, field="close")
    vols   = ctx.history(symbol=bar.symbol, n=21, field="volume")
    if len(closes) < 21:
        return
    sign = np.sign(closes.diff().fillna(0))
    obv = (sign * vols).cumsum()
    if bar.close >= float(closes.tail(20).max()) and obv.iloc[-1] >= float(obv.tail(20).max()):
        if ctx.position(bar.symbol).qty == 0:
            ctx.buy(bar.symbol, weight=0.5, reason="OBV+price 共振")
`,
  },
  {
    id: 'amount-ratio',
    title: '量比异常 → 短线追入',
    description: '当日成交额超过 5 日均量额 2x 时认为有资金推动。',
    category: 'volume',
    code: `# Strategy Lab: 量比短线
def setup(ctx):
    ctx.universe = ["sh600036"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 500_000

def on_bar(ctx, bar):
    vols = ctx.history(symbol=bar.symbol, n=5, field="volume")
    if len(vols) < 5:
        return
    ratio = bar.volume / (float(vols.mean()) + 1e-9)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and ratio > 2.0 and bar.close > bar.open:
        ctx.buy(bar.symbol, weight=0.4, reason=f"量比={ratio:.1f}")
        ctx.set_stop_loss(bar.symbol, -0.05)
        ctx.set_take_profit(bar.symbol, 0.06)
`,
  },

  // --------------------------------------------------------------------
  // 横截面 (5)
  // --------------------------------------------------------------------
  {
    id: 'momentum-rotate',
    title: '动量轮动 (csi300 月初取前 5)',
    description: '每月初按过去 20 日累计收益取前 5，等权重仓。',
    category: 'cross',
    code: `# Strategy Lab: 动量轮动
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    top  = rets.dropna().sort_values(ascending=False).head(ctx.max_positions).index.tolist()
    ctx.set_target_holdings(top, reason=f"top-{ctx.max_positions} mom")
`,
  },
  {
    id: 'low-vol-rotate',
    title: '低波动反转选股',
    description: 'csi300 中近 20 日波动率最低的前 5 名等权重持有。',
    category: 'cross',
    code: `# Strategy Lab: 低波选股
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    vol = history.pct_change().std()
    bottom = vol.dropna().sort_values().head(5).index.tolist()
    ctx.set_target_holdings(bottom, reason="low-vol 5")
`,
  },
  {
    id: 'reversal-rotate',
    title: '短期反转：跌得最多的前 5',
    description: 'csi300 中近 5 日跌幅最大的 5 只，等权重买入做反弹。',
    category: 'cross',
    code: `# Strategy Lab: 短期反转
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).weekday() != 0:
        return
    history = ctx.history(symbols=ctx.universe, n=5, field="close")
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    losers = rets.dropna().sort_values().head(5).index.tolist()
    ctx.set_target_holdings(losers, reason="weekly losers")
`,
  },
  {
    id: 'sector-rotate-momentum',
    title: '行业内动量选龙头',
    description: '同行业内取过去 20 日收益最高的 1 只，每行业一只。',
    category: 'cross',
    code: `# Strategy Lab: 行业龙头动量
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 10

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    by_sector = {}
    for sym in rets.dropna().index:
        sec = ctx.industry(sym) or "未知"
        if sec not in by_sector or rets[sym] > rets[by_sector[sec]]:
            by_sector[sec] = sym
    leaders = list(by_sector.values())[: ctx.max_positions]
    ctx.set_target_holdings(leaders, reason=f"sector-leader {len(leaders)}")
`,
  },
  {
    id: 'long-only-rank',
    title: '综合得分排名前 10',
    description: '把动量、低波、反转得分加权后选前 10 名。',
    category: 'cross',
    code: `# Strategy Lab: 综合排名
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 10

def _rank(s):
    return s.rank(pct=True)

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    mom_20 = history.iloc[-1] / history.iloc[0] - 1
    vol_20 = history.pct_change().std()
    score = 0.6 * _rank(mom_20) - 0.4 * _rank(vol_20)
    top = score.dropna().sort_values(ascending=False).head(10).index.tolist()
    ctx.set_target_holdings(top, reason="momentum+lowvol")
`,
  },

  // --------------------------------------------------------------------
  // 多因子 (4)
  // --------------------------------------------------------------------
  {
    id: 'three-factor',
    title: '三因子打分（动量+波动+趋势）',
    description: '动量、波动、趋势三个因子打分相加，得分最高的前 5。',
    category: 'factor',
    code: `# Strategy Lab: 三因子
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    mom = (history.iloc[-1] / history.iloc[0] - 1).rank(pct=True)
    vol = history.pct_change().std().rank(pct=True)
    trend = (history.iloc[-1] > history.mean()).astype(float).rank(pct=True)
    score = 0.5 * mom + 0.3 * trend - 0.2 * vol
    top = score.dropna().sort_values(ascending=False).head(5).index.tolist()
    ctx.set_target_holdings(top, reason="3-factor")
`,
  },
  {
    id: 'long-short-pairs',
    title: '动量多空（前 5 多 / 后 5 空）',
    description: '注：当前 broker v1 暂不支持做空，做空腿被忽略。',
    category: 'factor',
    code: `# Strategy Lab: 多空轮动 (long only fallback)
import pandas as pd

def setup(ctx):
    ctx.universe = "csi300"
    ctx.start    = "2026-01-05"
    ctx.end      = "2026-06-12"
    ctx.cash     = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field="close")
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    longs = rets.dropna().sort_values(ascending=False).head(5).index.tolist()
    ctx.set_target_holdings(longs, reason="long-leg only")
`,
  },
  {
    id: 'multi-signal-vote',
    title: '多信号投票（动量+RSI+量比）',
    description: '三个信号至少两个为真才入场。',
    category: 'factor',
    code: `# Strategy Lab: 信号投票
def _rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = -d.clip(upper=0).rolling(n).mean()
    rs = up / (dn + 1e-9)
    return 100 - 100 / (1 + rs)

def setup(ctx):
    ctx.universe = ["sh600519"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    vols   = ctx.history(symbol=bar.symbol, n=5,  field="volume")
    if len(closes) < 20 or len(vols) < 5:
        return
    sig_mom  = bar.close > float(closes.mean())
    sig_rsi  = float(_rsi(closes).iloc[-1]) > 50
    sig_vol  = bar.volume > float(vols.mean()) * 1.2
    votes = int(sig_mom) + int(sig_rsi) + int(sig_vol)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and votes >= 2:
        ctx.buy(bar.symbol, weight=0.5, reason=f"votes={votes}/3")
    elif pos.qty > 0 and votes <= 1:
        ctx.sell(bar.symbol, all=True, reason=f"votes={votes}/3")
`,
  },
  {
    id: 'risk-managed-momentum',
    title: '动量 + 风控（止损/止盈/最大回撤）',
    description: '加入 ATR 止损、固定止盈、单股仓位上限的多因子动量。',
    category: 'factor',
    code: `# Strategy Lab: 带风控动量
def setup(ctx):
    ctx.universe = ["sh600036", "sh600519", "sh601318"]
    ctx.start = "2026-01-05"
    ctx.end   = "2026-06-12"
    ctx.cash  = 1_000_000
    ctx.max_position_per_stock = 0.4

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field="close")
    if len(closes) < 20:
        return
    sma20 = float(closes.mean())
    atr = float(closes.pct_change().abs().rolling(14).mean().iloc[-1])
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close > sma20:
        ctx.buy(bar.symbol, weight=0.3, reason=f"momentum>{sma20:.2f}")
        ctx.set_stop_loss(bar.symbol, max(-2 * atr, -0.08))
        ctx.set_take_profit(bar.symbol, 0.12)
`,
  },
];

export const SNIPPETS_BY_CATEGORY: Record<SnippetCategory, SnippetSpec[]> = {
  basic: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'basic'),
  trend: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'trend'),
  reversal: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'reversal'),
  timing: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'timing'),
  volume: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'volume'),
  cross: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'cross'),
  factor: STRATEGY_LAB_SNIPPETS.filter((s) => s.category === 'factor'),
};
