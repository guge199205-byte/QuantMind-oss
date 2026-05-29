"""
因子实验室页面

Alpha Agent 因子查看 + RD-Agent 因子列表 + 回测结果。
"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="因子实验室 - QuantMind", layout="wide")

st.title("🧪 因子实验室")
st.caption("Alpha Agent · RD-Agent · 因子回测")

# 侧边栏
with st.sidebar:
    st.subheader("筛选")
    factor_source = st.selectbox(
        "因子来源",
        ["全部", "Alpha Agent", "RD-Agent"],
        index=0,
    )

    status_filter = st.selectbox(
        "状态",
        ["全部", "已完成", "进行中", "失败"],
        index=0,
    )

    limit = st.slider("显示条数", 10, 100, 20)

# 获取因子数据
factors = []
try:
    from services.quantmind_db import get_rd_agent_factors
    factors = get_rd_agent_factors(limit=limit)
except Exception as e:
    st.info(f"因子数据加载中: {e}")

if not factors:
    st.info("暂无因子数据，请先运行 Alpha Agent 或 RD-Agent 因子挖掘任务。")

    # 展示示例数据
    st.subheader("📊 示例因子")
    example_data = [
        {"factor_name": "momentum_20d", "description": "20日动量因子", "ic": 0.05, "ir": 0.8, "sharpe": 1.2, "status": "completed"},
        {"factor_name": "volatility_ratio", "description": "波动率比率因子", "ic": 0.03, "ir": 0.6, "sharpe": 0.9, "status": "completed"},
        {"factor_name": "volume_price_divergence", "description": "量价背离因子", "ic": 0.04, "ir": 0.7, "sharpe": 1.1, "status": "completed"},
    ]
    df = pd.DataFrame(example_data)
    st.dataframe(df, use_container_width=True)
    st.stop()

# 因子列表
df = pd.DataFrame(factors)

# 统计卡片
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("总因子数", len(df))

with col2:
    if "status" in df.columns:
        completed = len(df[df["status"] == "completed"])
        st.metric("已完成", completed)

with col3:
    if "ic" in df.columns:
        avg_ic = df["ic"].mean()
        st.metric("平均IC", f"{avg_ic:.4f}")

with col4:
    if "sharpe" in df.columns:
        avg_sharpe = df["sharpe"].mean()
        st.metric("平均Sharpe", f"{avg_sharpe:.2f}")

st.divider()

# 因子列表
st.subheader("📋 因子列表")

# 格式化显示
display_cols = []
if "factor_name" in df.columns:
    display_cols.append("factor_name")
if "description" in df.columns:
    display_cols.append("description")
if "ic" in df.columns:
    display_cols.append("ic")
if "ir" in df.columns:
    display_cols.append("ir")
if "sharpe" in df.columns:
    display_cols.append("sharpe")
if "status" in df.columns:
    display_cols.append("status")
if "created_at" in df.columns:
    display_cols.append("created_at")

if display_cols:
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        column_config={
            "factor_name": "因子名称",
            "description": "描述",
            "ic": st.column_config.NumberColumn("IC", format="%.4f"),
            "ir": st.column_config.NumberColumn("IR", format="%.2f"),
            "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "status": "状态",
            "created_at": "创建时间",
        },
    )
else:
    st.dataframe(df, use_container_width=True)

st.divider()

# 因子分析
st.subheader("📊 因子分析")

if "ic" in df.columns and not df["ic"].isna().all():
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### IC 分布")
        import plotly.graph_objects as go

        fig = go.Figure(data=[
            go.Histogram(x=df["ic"].dropna(), nbinsx=20, marker_color="#2196f3")
        ])
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
            xaxis_title="IC 值",
            yaxis_title="频次",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("#### IC vs Sharpe")
        if "sharpe" in df.columns:
            fig = go.Figure(data=[
                go.Scatter(
                    x=df["ic"],
                    y=df["sharpe"],
                    mode="markers",
                    marker=dict(
                        size=10,
                        color=df["ic"],
                        colorscale="Viridis",
                        showscale=True,
                    ),
                    text=df.get("factor_name", ""),
                    hovertemplate="%{text}<br>IC: %{x:.4f}<br>Sharpe: %{y:.2f}",
                )
            ])
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis_title="IC",
                yaxis_title="Sharpe Ratio",
            )
            st.plotly_chart(fig, use_container_width=True)

st.divider()

# 启动新任务
st.subheader("🚀 启动因子挖掘")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Alpha Agent")
    loop_n = st.slider("进化轮次", 1, 10, 3, key="alpha_loop")
    direction = st.text_input("研究方向", value="", key="alpha_direction", help="可选，如: 动量因子、波动率因子")

    if st.button("启动 Alpha Agent", type="primary"):
        st.info("请通过 QuantBot 聊天界面启动因子挖掘任务。")

with col2:
    st.markdown("#### RD-Agent")
    if st.button("启动 RD-Agent"):
        st.info("请通过 QuantBot 聊天界面启动因子挖掘任务。")
