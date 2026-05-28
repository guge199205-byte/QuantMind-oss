"""
财经资讯页面

Huntly 资讯聚合 + OpenBB 新闻。
"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="财经资讯 - QuantMind", layout="wide")

st.title("📰 财经资讯")
st.caption("市场动态 · 公司新闻 · 宏观经济")

# 侧边栏
with st.sidebar:
    st.subheader("资讯来源")
    source = st.radio(
        "数据源",
        ["Huntly (RSS)", "OpenBB 新闻", "全部"],
        index=0,
    )

    st.subheader("筛选")
    keyword = st.text_input("关键词搜索", value="")
    limit = st.slider("显示条数", 10, 100, 30)

# Huntly 资讯
if source in ["Huntly (RSS)", "全部"]:
    st.subheader("📡 Huntly 资讯聚合")

    try:
        import httpx
        import os

        huntly_url = os.getenv("HUNTLY_BASE_URL", "http://quantmind-huntly")
        huntly_user = os.getenv("HUNTLY_USERNAME", "")
        huntly_pass = os.getenv("HUNTLY_PASSWORD", "")

        # 获取文章列表
        resp = httpx.get(
            f"{huntly_url}/api/articles",
            params={"page": 0, "size": limit},
            auth=(huntly_user, huntly_pass),
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            articles = data.get("content", [])

            if articles:
                for article in articles:
                    title = article.get("title", "无标题")
                    url = article.get("url", "")
                    source_name = article.get("sourceName", "")
                    publish_time = article.get("publishTime", "")
                    starred = article.get("starred", False)

                    col1, col2 = st.columns([4, 1])

                    with col1:
                        if url:
                            st.markdown(f"**[{title}]({url})**")
                        else:
                            st.markdown(f"**{title}**")

                        meta_parts = []
                        if source_name:
                            meta_parts.append(f"来源: {source_name}")
                        if publish_time:
                            meta_parts.append(f"时间: {publish_time}")
                        if meta_parts:
                            st.caption(" | ".join(meta_parts))

                    with col2:
                        if starred:
                            st.markdown("⭐")

                    st.divider()
            else:
                st.info("暂无文章")
        else:
            st.warning(f"Huntly API 返回 {resp.status_code}")

    except httpx.ConnectError:
        st.warning("Huntly 服务未启动，请检查 docker-compose 中的 huntly 容器。")
    except Exception as e:
        st.error(f"Huntly 数据获取失败: {e}")

    if source == "全部":
        st.divider()

# OpenBB 新闻
if source in ["OpenBB 新闻", "全部"]:
    st.subheader("🌐 OpenBB 新闻")

    try:
        from services.openbb_client import get_news, is_available

        if is_available():
            query = keyword if keyword else "stock market"
            news = get_news(query=query, limit=limit)

            if news:
                for item in news:
                    title = item.get("title", "无标题")
                    summary = item.get("summary", "")
                    url = item.get("url", "")
                    source_name = item.get("source", "")
                    pub_date = item.get("date", "")

                    col1, col2 = st.columns([4, 1])

                    with col1:
                        if url:
                            st.markdown(f"**[{title}]({url})**")
                        else:
                            st.markdown(f"**{title}**")

                        if summary:
                            st.caption(summary[:200] + "..." if len(summary) > 200 else summary)

                        meta_parts = []
                        if source_name:
                            meta_parts.append(f"来源: {source_name}")
                        if pub_date:
                            meta_parts.append(f"时间: {pub_date}")
                        if meta_parts:
                            st.caption(" | ".join(meta_parts))

                    st.divider()
            else:
                st.info("暂无新闻")
        else:
            st.info("OpenBB 未启用，请安装 openbb 包。")

    except Exception as e:
        st.error(f"OpenBB 新闻获取失败: {e}")

# 底部：关键词搜索提示
if keyword:
    st.caption(f"搜索关键词: {keyword}")
