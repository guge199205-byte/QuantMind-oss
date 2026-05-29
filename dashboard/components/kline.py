"""
K 线图组件

使用 Plotly 绘制交互式 K 线图，支持成交量显示。
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def render_kline(
    df: pd.DataFrame,
    title: str = "",
    show_volume: bool = True,
    height: int = 500,
    ma_periods: list[int] = None,
) -> None:
    """渲染 K 线图

    Args:
        df: 包含 trade_date, open, high, low, close, volume 的 DataFrame
        title: 图表标题
        show_volume: 是否显示成交量
        height: 图表高度
        ma_periods: 均线周期列表，如 [5, 10, 20]
    """
    if df.empty:
        st.warning("暂无数据")
        return

    if ma_periods is None:
        ma_periods = [5, 10, 20]

    # 创建子图
    rows = 2 if show_volume else 1
    row_heights = [0.7, 0.3] if show_volume else [1.0]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=(title, "成交量") if show_volume and title else (title,) if title else None,
    )

    # K 线
    colors = df.apply(
        lambda row: "#ef5350" if row["close"] >= row["open"] else "#26a69a",
        axis=1,
    )

    fig.add_trace(
        go.Candlestick(
            x=df["trade_date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
            increasing_fillcolor="#ef5350",
            decreasing_fillcolor="#26a69a",
            name="K线",
        ),
        row=1,
        col=1,
    )

    # 均线
    ma_colors = ["#ff9800", "#2196f3", "#9c27b0", "#4caf50"]
    for i, period in enumerate(ma_periods):
        if len(df) >= period:
            ma = df["close"].rolling(window=period).mean()
            fig.add_trace(
                go.Scatter(
                    x=df["trade_date"],
                    y=ma,
                    mode="lines",
                    name=f"MA{period}",
                    line=dict(
                        color=ma_colors[i % len(ma_colors)],
                        width=1,
                    ),
                ),
                row=1,
                col=1,
            )

    # 成交量
    if show_volume and "volume" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df["trade_date"],
                y=df["volume"],
                marker_color=colors,
                name="成交量",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    # 布局
    fig.update_layout(
        height=height,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        margin=dict(l=50, r=50, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            type="date",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # 隐藏周末
            ],
        ),
    )

    if show_volume:
        fig.update_xaxes(type="date", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)


def render_comparison_kline(
    data: dict[str, pd.DataFrame],
    title: str = "多股对比",
    height: int = 400,
    normalize: bool = True,
) -> None:
    """渲染多股对比图

    Args:
        data: {symbol: DataFrame} 字典
        title: 图表标题
        height: 图表高度
        normalize: 是否归一化（以首日为基准 100%）
    """
    if not data:
        st.warning("暂无数据")
        return

    fig = go.Figure()

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    for i, (symbol, df) in enumerate(data.items()):
        if df.empty:
            continue

        y = df["close"]
        if normalize and len(y) > 0 and y.iloc[0] > 0:
            y = y / y.iloc[0] * 100

        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=y,
                mode="lines",
                name=symbol,
                line=dict(
                    color=colors[i % len(colors)],
                    width=2,
                ),
            )
        )

    fig.update_layout(
        title=title,
        height=height,
        template="plotly_white",
        margin=dict(l=50, r=50, t=40, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        yaxis_title="归一化价格 (%)" if normalize else "价格",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)
