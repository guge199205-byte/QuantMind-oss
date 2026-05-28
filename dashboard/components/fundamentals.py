"""
基本面指标组件

渲染 PE、PB、市值等基本面指标卡片。
"""

import streamlit as st
from typing import Any, Optional


def render_fundamentals_card(data: dict[str, Any]) -> None:
    """渲染基本面指标卡片

    Args:
        data: 包含基本面数据的字典
    """
    if not data:
        st.info("暂无基本面数据")
        return

    st.subheader(f"📋 {data.get('name', '')} 基本面")

    # 主要指标
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        market_cap = data.get("market_cap", 0)
        if market_cap > 0:
            if market_cap >= 1e12:
                st.metric("总市值", f"{market_cap/1e12:.2f} 万亿")
            elif market_cap >= 1e8:
                st.metric("总市值", f"{market_cap/1e8:.2f} 亿")
            else:
                st.metric("总市值", f"{market_cap/1e4:.2f} 万")

    with col2:
        pe = data.get("pe_ratio", 0)
        if pe and pe > 0:
            st.metric("PE (TTM)", f"{pe:.2f}")
        else:
            st.metric("PE (TTM)", "N/A")

    with col3:
        pb = data.get("pb_ratio", 0)
        if pb and pb > 0:
            st.metric("PB", f"{pb:.2f}")
        else:
            st.metric("PB", "N/A")

    with col4:
        dividend = data.get("dividend_yield", 0)
        if dividend and dividend > 0:
            st.metric("股息率", f"{dividend:.2f}%")
        else:
            st.metric("股息率", "N/A")

    # 52 周范围
    high_52w = data.get("52w_high", 0)
    low_52w = data.get("52w_low", 0)
    if high_52w and low_52w:
        st.markdown(f"**52 周范围**: {low_52w:.2f} - {high_52w:.2f}")

    # 行业信息
    sector = data.get("sector", "")
    industry = data.get("industry", "")
    if sector or industry:
        st.markdown(f"**行业**: {sector} / {industry}")

    # 公司简介
    description = data.get("description", "")
    if description:
        with st.expander("公司简介"):
            st.write(description)


def render_valuation_comparison(data: dict[str, dict]) -> None:
    """渲染估值对比表

    Args:
        data: {指标名: {symbol: value}} 字典
    """
    if not data:
        return

    import pandas as pd

    df = pd.DataFrame(data)
    st.dataframe(
        df.style.format({
            col: "{:.2f}" for col in df.select_dtypes(include=["float64"]).columns
        }),
        use_container_width=True,
    )


def render_peer_comparison(
    symbol: str,
    peers: list[dict[str, Any]],
) -> None:
    """渲染同行对比

    Args:
        symbol: 当前股票代码
        peers: 同行公司数据列表
    """
    if not peers:
        return

    st.subheader("🏢 同行对比")

    import pandas as pd

    df = pd.DataFrame(peers)
    if "symbol" in df.columns:
        # 高亮当前股票
        def highlight_row(row):
            if row["symbol"] == symbol:
                return ["background-color: #e3f2fd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(highlight_row, axis=1),
            use_container_width=True,
        )
    else:
        st.dataframe(df, use_container_width=True)


def render_financial_health(data: dict[str, Any]) -> None:
    """渲染财务健康指标

    Args:
        data: 财务指标数据
    """
    if not data:
        return

    st.subheader("💰 财务健康")

    col1, col2, col3 = st.columns(3)

    with col1:
        roe = data.get("roe", 0)
        if roe:
            color = "🟢" if roe > 15 else "🟡" if roe > 10 else "🔴"
            st.metric("ROE", f"{roe:.2f}%", delta=f"{color}")

    with col2:
        debt_ratio = data.get("debt_ratio", 0)
        if debt_ratio:
            color = "🟢" if debt_ratio < 50 else "🟡" if debt_ratio < 70 else "🔴"
            st.metric("资产负债率", f"{debt_ratio:.2f}%", delta=f"{color}")

    with col3:
        current_ratio = data.get("current_ratio", 0)
        if current_ratio:
            color = "🟢" if current_ratio > 1.5 else "🟡" if current_ratio > 1 else "🔴"
            st.metric("流动比率", f"{current_ratio:.2f}", delta=f"{color}")
