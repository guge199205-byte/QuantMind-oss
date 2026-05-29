"""
技术指标组件

渲染 MACD、RSI、布林带等技术指标图表。
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def render_macd(df: pd.DataFrame, height: int = 200) -> None:
    """渲染 MACD 指标"""
    if df.empty or len(df) < 26:
        return

    try:
        import ta

        close = df["close"]
        macd = ta.trend.MACD(close)
        macd_line = macd.macd()
        signal_line = macd.macd_signal()
        histogram = macd.macd_diff()

        fig = go.Figure()

        # MACD 线
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=macd_line,
                mode="lines",
                name="MACD",
                line=dict(color="#2196f3", width=1.5),
            )
        )

        # 信号线
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=signal_line,
                mode="lines",
                name="信号线",
                line=dict(color="#ff9800", width=1.5),
            )
        )

        # 柱状图
        colors = ["#ef5350" if v >= 0 else "#26a69a" for v in histogram]
        fig.add_trace(
            go.Bar(
                x=df["trade_date"],
                y=histogram,
                name="柱状图",
                marker_color=colors,
            )
        )

        fig.update_layout(
            height=height,
            template="plotly_white",
            margin=dict(l=50, r=50, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="MACD",
            xaxis=dict(type="date", rangebreaks=[dict(bounds=["sat", "mon"])]),
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"MACD 计算失败: {e}")


def render_rsi(df: pd.DataFrame, period: int = 14, height: int = 200) -> None:
    """渲染 RSI 指标"""
    if df.empty or len(df) < period:
        return

    try:
        import ta

        close = df["close"]
        rsi = ta.momentum.rsi(close, window=period)

        fig = go.Figure()

        # RSI 线
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=rsi,
                mode="lines",
                name=f"RSI({period})",
                line=dict(color="#9c27b0", width=1.5),
            )
        )

        # 超买超卖线
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超买")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超卖")
        fig.add_hline(y=50, line_dash="dot", line_color="gray")

        # 填充区域
        fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, line_width=0)
        fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, line_width=0)

        fig.update_layout(
            height=height,
            template="plotly_white",
            margin=dict(l=50, r=50, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="RSI",
            yaxis=dict(range=[0, 100]),
            xaxis=dict(type="date", rangebreaks=[dict(bounds=["sat", "mon"])]),
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"RSI 计算失败: {e}")


def render_bollinger(df: pd.DataFrame, period: int = 20, std_dev: int = 2, height: int = 300) -> None:
    """渲染布林带指标"""
    if df.empty or len(df) < period:
        return

    try:
        import ta

        close = df["close"]
        bb = ta.volatility.BollingerBands(close, window=period, window_dev=std_dev)
        upper = bb.bollinger_hband()
        middle = bb.bollinger_mavg()
        lower = bb.bollinger_lband()

        fig = go.Figure()

        # K 线
        fig.add_trace(
            go.Candlestick(
                x=df["trade_date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                increasing_line_color="#ef5350",
                decreasing_line_color="#26a69a",
                name="K线",
            )
        )

        # 布林带
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=upper,
                mode="lines",
                name="上轨",
                line=dict(color="#ff9800", width=1, dash="dash"),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=middle,
                mode="lines",
                name="中轨",
                line=dict(color="#2196f3", width=1.5),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=lower,
                mode="lines",
                name="下轨",
                line=dict(color="#ff9800", width=1, dash="dash"),
                fill="tonexty",
                fillcolor="rgba(255, 152, 0, 0.1)",
            )
        )

        fig.update_layout(
            height=height,
            template="plotly_white",
            margin=dict(l=50, r=50, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            xaxis=dict(type="date", rangebreaks=[dict(bounds=["sat", "mon"])]),
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"布林带计算失败: {e}")


def render_indicator_summary(indicators: dict) -> None:
    """渲染技术指标摘要卡片"""
    if not indicators:
        return

    cols = st.columns(4)
    with cols[0]:
        if "rsi_14" in indicators and indicators["rsi_14"] is not None:
            rsi = indicators["rsi_14"]
            color = "🔴" if rsi > 70 else "🟢" if rsi < 30 else "⚪"
            st.metric("RSI(14)", f"{rsi:.1f}", delta=f"{color} {'超买' if rsi > 70 else '超卖' if rsi < 30 else '中性'}")

    with cols[1]:
        if "macd" in indicators and indicators["macd"] is not None:
            macd = indicators["macd"]
            st.metric("MACD", f"{macd:.4f}")

    with cols[2]:
        if "sma_20" in indicators and indicators["sma_20"] is not None:
            st.metric("MA20", f"{indicators['sma_20']:.2f}")

    with cols[3]:
        if "bb_upper" in indicators and indicators["bb_upper"] is not None:
            st.metric("布林上轨", f"{indicators['bb_upper']:.2f}")
