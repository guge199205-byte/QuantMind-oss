"""
QuantMind 数据看板 — Streamlit 主入口

首页展示市场概览：大盘指数、涨跌分布、资金流向。
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(
    page_title="QuantMind 数据看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS
st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; max-width: 100%; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
    div[data-testid="stSidebar"] { min-width: 240px; }
</style>
""", unsafe_allow_html=True)


def render_market_overview():
    """市场概览首页"""
    st.title("📊 QuantMind 数据看板")
    st.caption("全市场行情 · 智能分析 · 投资组合管理")

    # 大盘指数
    st.subheader("📈 大盘指数")
    col1, col2, col3, col4 = st.columns(4)

    try:
        from services.quantmind_db import get_latest_indices
        indices = get_latest_indices()
        for i, (name, data) in enumerate(indices.items()):
            cols = [col1, col2, col3, col4]
            if i < len(cols):
                with cols[i]:
                    delta = data.get("change_pct", 0)
                    st.metric(
                        label=name,
                        value=f"{data.get('close', 0):.2f}",
                        delta=f"{delta:+.2f}%",
                    )
    except Exception as e:
        st.info("正在连接数据库...")
        # 展示占位数据
        col1.metric("上证指数", "3,200.00", "+0.50%")
        col2.metric("深证成指", "10,800.00", "-0.30%")
        col3.metric("创业板指", "2,100.00", "+1.20%")
        col4.metric("科创50", "980.00", "+0.80%")

    st.divider()

    # 涨跌分布
    st.subheader("📊 涨跌分布")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        try:
            from services.quantmind_db import get_market_breadth
            breadth = get_market_breadth()
            import plotly.graph_objects as go

            fig = go.Figure(data=[
                go.Bar(
                    x=["涨停", "涨>5%", "涨0-5%", "平", "跌0-5%", "跌>5%", "跌停"],
                    y=[
                        breadth.get("limit_up", 0),
                        breadth.get("up_gt5", 0),
                        breadth.get("up_0_5", 0),
                        breadth.get("flat", 0),
                        breadth.get("down_0_5", 0),
                        breadth.get("down_gt5", 0),
                        breadth.get("limit_down", 0),
                    ],
                    marker_color=["#ff4444", "#ff6666", "#ff9999", "#cccccc", "#99cc99", "#66cc66", "#33cc33"],
                )
            ])
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=10, b=20),
                showlegend=False,
                yaxis_title="股票数量",
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("涨跌分布数据加载中...")

    with col_right:
        st.markdown("#### 热门板块")
        try:
            from services.quantmind_db import get_hot_sectors
            sectors = get_hot_sectors()
            for sector in sectors[:8]:
                color = "🟢" if sector["change_pct"] >= 0 else "🔴"
                st.markdown(f"{color} **{sector['name']}** {sector['change_pct']:+.2f}%")
        except Exception:
            st.info("板块数据加载中...")

    st.divider()

    # 快速入口
    st.subheader("🚀 快速入口")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.page_link("pages/01_📊_市场概览.py", label="市场概览", icon="📊")
    with c2:
        st.page_link("pages/02_🔍_个股分析.py", label="个股分析", icon="🔍")
    with c3:
        st.page_link("pages/03_💼_投资组合.py", label="投资组合", icon="💼")
    with c4:
        st.page_link("pages/04_📰_财经资讯.py", label="财经资讯", icon="📰")


# 侧边栏
with st.sidebar:
    st.image("https://img.shields.io/badge/QuantMind-Dashboard-blue", width=180)
    st.markdown("---")
    st.markdown("### 数据源状态")
    try:
        from services.quantmind_db import check_connection
        if check_connection():
            st.success("PostgreSQL 已连接")
        else:
            st.error("PostgreSQL 未连接")
    except Exception:
        st.warning("数据库检查中...")

    try:
        from services.cache import check_redis
        if check_redis():
            st.success("Redis 已连接")
        else:
            st.warning("Redis 未连接")
    except Exception:
        st.warning("Redis 检查中...")

    st.markdown("---")
    st.caption("v1.0.0 · OpenBB + Streamlit")

# 渲染首页
render_market_overview()
