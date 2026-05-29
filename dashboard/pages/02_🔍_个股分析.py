"""
个股分析页面

K 线图 + 技术指标 + 基本面分析。
支持 A 股、港股、美股。
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="个股分析 - QuantMind", layout="wide")

st.title("🔍 个股分析")
st.caption("K 线走势 · 技术指标 · 基本面数据")

# 侧边栏：股票选择
with st.sidebar:
    st.subheader("股票选择")

    market = st.selectbox("市场", ["A 股", "港股", "美股"], index=0)

    # 股票输入
    if market == "A 股":
        symbol = st.text_input("股票代码", value="600519.SH", help="格式: 600519.SH")
    elif market == "港股":
        symbol = st.text_input("股票代码", value="00700.HK", help="格式: 00700.HK")
    else:
        symbol = st.text_input("股票代码", value="AAPL", help="格式: AAPL")

    days = st.slider("显示天数", 30, 360, 120)

    # 技术指标选择
    st.subheader("技术指标")
    show_macd = st.checkbox("MACD", value=True)
    show_rsi = st.checkbox("RSI", value=True)
    show_bollinger = st.checkbox("布林带", value=False)

# 获取数据
market_code = {"A 股": "A", "港股": "HK", "美股": "US"}[market]

df = pd.DataFrame()
data_source = ""

# A 股优先走 QuantMind DB
if market_code == "A":
    try:
        from services.quantmind_db import get_stock_daily
        df = get_stock_daily(symbol, days=days)
        if not df.empty:
            data_source = "QuantMind DB"
    except Exception as e:
        st.warning(f"QuantMind DB 查询失败: {e}")

# 国际市场或 A 股无数据时走 OpenBB
if df.empty:
    try:
        from services.openbb_client import get_stock_history, is_available
        if is_available():
            df = get_stock_history(symbol, market=market_code, days=days)
            if not df.empty:
                data_source = "OpenBB (yfinance)"
    except Exception as e:
        st.info(f"OpenBB 数据获取: {e}")

# 主区域
if df.empty:
    st.warning(f"未找到 {symbol} 的数据，请检查股票代码是否正确。")
    st.stop()

# 数据源提示
st.caption(f"数据来源: {data_source} | 数据条数: {len(df)}")

# 股票信息
col_info1, col_info2, col_info3, col_info4 = st.columns(4)

latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else latest

with col_info1:
    price = latest["close"]
    change = price - prev["close"]
    change_pct = (change / prev["close"] * 100) if prev["close"] > 0 else 0
    st.metric(
        label="最新价",
        value=f"{price:.2f}",
        delta=f"{change:+.2f} ({change_pct:+.2f}%)",
    )

with col_info2:
    st.metric("最高", f"{latest['high']:.2f}")

with col_info3:
    st.metric("最低", f"{latest['low']:.2f}")

with col_info4:
    vol = latest.get("volume", 0)
    if vol >= 1e8:
        st.metric("成交量", f"{vol/1e8:.2f} 亿")
    elif vol >= 1e4:
        st.metric("成交量", f"{vol/1e4:.2f} 万")
    else:
        st.metric("成交量", f"{vol:.0f}")

st.divider()

# K 线图
from components.kline import render_kline
render_kline(df, title=f"{symbol} 日K线", show_volume=True, height=500)

# 技术指标
st.subheader("📈 技术指标")

if show_macd:
    from components.indicators import render_macd
    render_macd(df)

if show_rsi:
    from components.indicators import render_rsi
    render_rsi(df)

if show_bollinger:
    from components.indicators import render_bollinger
    render_bollinger(df)

# 技术指标摘要
st.subheader("📋 指标摘要")
try:
    from services.openbb_client import get_technical_indicators
    indicators = get_technical_indicators(df)
    if indicators:
        from components.indicators import render_indicator_summary
        render_indicator_summary(indicators)
except Exception as e:
    st.info(f"技术指标计算: {e}")

st.divider()

# 基本面数据
st.subheader("📊 基本面")
try:
    from services.openbb_client import get_fundamentals, is_available
    if is_available():
        fund_data = get_fundamentals(symbol, market=market_code)
        if fund_data:
            from components.fundamentals import render_fundamentals_card
            render_fundamentals_card(fund_data)
        else:
            st.info("基本面数据暂不可用")
    else:
        st.info("OpenBB 未启用，无法获取基本面数据")
except Exception as e:
    st.info(f"基本面数据: {e}")
