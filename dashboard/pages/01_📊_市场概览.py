"""
市场概览页面

展示大盘指数、涨跌分布、板块热力图、资金流向。
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="市场概览 - QuantMind", layout="wide")

st.title("📊 市场概览")
st.caption("大盘走势 · 板块轮动 · 资金流向")

# 大盘指数
st.subheader("📈 主要指数")
try:
    from services.quantmind_db import get_latest_indices
    indices = get_latest_indices()

    cols = st.columns(len(indices) if indices else 4)
    for i, (name, data) in enumerate(indices.items()):
        with cols[i]:
            delta = data.get("change_pct", 0)
            st.metric(
                label=name,
                value=f"{data.get('close', 0):,.2f}",
                delta=f"{delta:+.2f}%",
                delta_color="normal",
            )
except Exception as e:
    st.info(f"指数数据加载中: {e}")

st.divider()

# 涨跌分布 + 热门板块
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📊 涨跌分布")
    try:
        from services.quantmind_db import get_market_breadth
        breadth = get_market_breadth()

        import plotly.graph_objects as go

        categories = ["涨停", "涨>5%", "涨0-5%", "平盘", "跌0-5%", "跌>5%", "跌停"]
        values = [
            breadth.get("limit_up", 0),
            breadth.get("up_gt5", 0),
            breadth.get("up_0_5", 0),
            breadth.get("flat", 0),
            breadth.get("down_0_5", 0),
            breadth.get("down_gt5", 0),
            breadth.get("limit_down", 0),
        ]
        colors = ["#d32f2f", "#f44336", "#ef9a9a", "#bdbdbd", "#a5d6a7", "#66bb6a", "#2e7d32"]

        fig = go.Figure(data=[
            go.Bar(x=categories, y=values, marker_color=colors, text=values, textposition="auto")
        ])
        fig.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=10, b=20),
            showlegend=False,
            yaxis_title="股票数量",
        )
        st.plotly_chart(fig, use_container_width=True)

        # 统计摘要
        total = sum(values)
        up_total = sum(values[:3])
        down_total = sum(values[4:])
        st.markdown(f"**上涨**: {up_total} 只 ({up_total/total*100:.1f}%) | **下跌**: {down_total} 只 ({down_total/total*100:.1f}%)")

    except Exception as e:
        st.info(f"涨跌分布数据加载中: {e}")

with col_right:
    st.subheader("🔥 热门板块")
    try:
        from services.quantmind_db import get_hot_sectors
        sectors = get_hot_sectors(limit=15)

        for sector in sectors:
            change = sector.get("change_pct", 0)
            color = "🟢" if change >= 0 else "🔴"
            count = sector.get("stock_count", 0)
            st.markdown(f"{color} **{sector['name']}** ({count}只) {change:+.2f}%")

    except Exception as e:
        st.info(f"板块数据加载中: {e}")

st.divider()

# 资金流向（示例）
st.subheader("💰 资金流向")
st.info("资金流向数据需要对接专用数据源，暂未实现。")

# 市场情绪
st.subheader("🌡️ 市场情绪")
col1, col2, col3 = st.columns(3)

with col1:
    try:
        breadth = get_market_breadth()
        total = sum(breadth.values())
        if total > 0:
            up_ratio = (breadth.get("limit_up", 0) + breadth.get("up_gt5", 0) + breadth.get("up_0_5", 0)) / total * 100
            if up_ratio > 60:
                st.success(f"偏多 ({up_ratio:.1f}% 上涨)")
            elif up_ratio > 40:
                st.warning(f"中性 ({up_ratio:.1f}% 上涨)")
            else:
                st.error(f"偏空 ({up_ratio:.1f}% 上涨)")
    except Exception:
        st.info("情绪指标加载中")

with col2:
    st.metric("涨停数", "计算中...")

with col3:
    st.metric("跌停数", "计算中...")
