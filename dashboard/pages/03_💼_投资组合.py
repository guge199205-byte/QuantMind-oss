"""
投资组合页面

持仓监控、绩效归因、风险分析。
"""

import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="投资组合 - QuantMind", layout="wide")

st.title("💼 投资组合")
st.caption("持仓监控 · 绩效分析 · 风险管理")

# 用户选择
with st.sidebar:
    st.subheader("用户设置")
    user_id = st.text_input("用户ID", value="admin", help="QuantMind 用户名")

    st.subheader("显示选项")
    show_chart = st.checkbox("显示饼图", value=True)
    show_risk = st.checkbox("显示风险指标", value=True)

# 获取持仓数据
portfolio = []
try:
    from services.quantmind_db import get_user_portfolio
    portfolio = get_user_portfolio(user_id)
except Exception as e:
    st.info(f"持仓数据加载中: {e}")

if not portfolio:
    st.info("暂无持仓数据，请先在 QuantMind 中配置投资组合。")

    # 展示示例数据
    st.subheader("📊 示例持仓")
    example_data = [
        {"symbol": "600519.SH", "name": "贵州茅台", "quantity": 100, "avg_cost": 1800.00, "current_price": 1850.00},
        {"symbol": "000858.SZ", "name": "五粮液", "quantity": 200, "avg_cost": 150.00, "current_price": 155.00},
        {"symbol": "601318.SH", "name": "中国平安", "quantity": 500, "avg_cost": 45.00, "current_price": 48.00},
    ]
    df = pd.DataFrame(example_data)
    df["market_value"] = df["quantity"] * df["current_price"]
    df["profit"] = df["quantity"] * (df["current_price"] - df["avg_cost"])
    df["profit_pct"] = (df["current_price"] - df["avg_cost"]) / df["avg_cost"] * 100

    st.dataframe(
        df[["symbol", "name", "quantity", "avg_cost", "current_price", "market_value", "profit", "profit_pct"]],
        use_container_width=True,
        column_config={
            "symbol": "代码",
            "name": "名称",
            "quantity": "持仓量",
            "avg_cost": st.column_config.NumberColumn("成本价", format="%.2f"),
            "current_price": st.column_config.NumberColumn("现价", format="%.2f"),
            "market_value": st.column_config.NumberColumn("市值", format="%.0f"),
            "profit": st.column_config.NumberColumn("盈亏", format="%.0f"),
            "profit_pct": st.column_config.NumberColumn("盈亏%", format="%.2f%%"),
        },
    )
    st.stop()

# 持仓总览
df = pd.DataFrame(portfolio)

# 汇总指标
total_value = df.get("market_value", pd.Series([0])).sum()
total_cost = (df.get("quantity", pd.Series([0])) * df.get("avg_cost", pd.Series([0]))).sum()
total_profit = df.get("profit_loss", pd.Series([0])).sum()
total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("总市值", f"¥{total_value:,.0f}")

with col2:
    st.metric("总成本", f"¥{total_cost:,.0f}")

with col3:
    st.metric("总盈亏", f"¥{total_profit:,.0f}", delta=f"{total_profit_pct:+.2f}%")

with col4:
    st.metric("持仓数", f"{len(df)} 只")

st.divider()

# 持仓明细
st.subheader("📋 持仓明细")

st.dataframe(
    df[["symbol", "quantity", "avg_cost", "current_price", "market_value", "profit_loss", "profit_pct"]],
    use_container_width=True,
    column_config={
        "symbol": "代码",
        "quantity": "持仓量",
        "avg_cost": st.column_config.NumberColumn("成本价", format="%.2f"),
        "current_price": st.column_config.NumberColumn("现价", format="%.2f"),
        "market_value": st.column_config.NumberColumn("市值", format="%.0f"),
        "profit_loss": st.column_config.NumberColumn("盈亏", format="%.0f"),
        "profit_pct": st.column_config.NumberColumn("盈亏%", format="%.2f%%"),
    },
)

st.divider()

# 持仓分布
if show_chart and not df.empty:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 持仓分布")
        import plotly.graph_objects as go

        fig = go.Figure(data=[
            go.Pie(
                labels=df["symbol"],
                values=df["market_value"],
                hole=0.4,
                textinfo="label+percent",
            )
        ])
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("📈 盈亏分布")
        colors = ["#ef5350" if p >= 0 else "#26a69a" for p in df["profit_loss"]]

        fig = go.Figure(data=[
            go.Bar(
                x=df["symbol"],
                y=df["profit_loss"],
                marker_color=colors,
                text=[f"{p:+,.0f}" for p in df["profit_loss"]],
                textposition="auto",
            )
        ])
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False,
            yaxis_title="盈亏金额",
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# 风险分析
if show_risk:
    st.subheader("⚠️ 风险分析")

    col1, col2, col3 = st.columns(3)

    with col1:
        # 集中度风险
        if not df.empty and "market_value" in df.columns:
            max_weight = df["market_value"].max() / total_value * 100 if total_value > 0 else 0
            if max_weight > 30:
                st.warning(f"集中度风险: 最大持仓占比 {max_weight:.1f}%")
            else:
                st.success(f"集中度正常: 最大持仓占比 {max_weight:.1f}%")

    with col2:
        # 行业分散度
        st.info("行业分散度分析需要行业数据")

    with col3:
        # 波动率
        st.info("波动率分析需要历史数据")
