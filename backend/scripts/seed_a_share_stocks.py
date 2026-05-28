"""
A股基础信息种子脚本：baostock 拿股票主表与行业，THS 拿行业/概念板块名称。

写入：
- stocks (代码、名称、行业、板块)
- stock_aliases (匹配字符串 → ticker)
- finance_lexicon 新增 event_tag = "行业板块" / "概念板块" 词条，
  用于让新闻命中板块名后能反向召回这一组股票

幂等：UPSERT；任一数据源失败不阻断其他源。

运行：
  sudo docker exec quantmind python3 /app/backend/scripts/seed_a_share_stocks.py
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Iterable

import psycopg2
from psycopg2.extras import execute_batch

logger = logging.getLogger("seed_a_share")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


# ---------- DB ----------

def _conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "quantmind-db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "quantmind"),
        password=os.getenv("POSTGRES_PASSWORD", "quantmind2026"),
        dbname=os.getenv("POSTGRES_DB", "quantmind"),
    )


def _bs_code_to_ticker(bs_code: str) -> str:
    """baostock 'sh.600519' -> '600519.SH', 'sz.000001' -> '000001.SZ'"""
    if "." not in bs_code:
        return bs_code
    prefix, code = bs_code.split(".", 1)
    return f"{code}.{prefix.upper()}"


def _classify_exchange(ticker: str) -> str:
    return ticker.split(".")[-1] if "." in ticker else ""


def _retry(fn, *, attempts: int = 3, delay: float = 2.0, name: str = ""):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            logger.warning("%s 第%d/%d次失败: %s", name, i + 1, attempts, str(e)[:120])
            time.sleep(delay * (i + 1))
    raise last  # type: ignore[misc]


# ---------- baostock: 股票 + 行业 ----------

def fetch_stocks_baostock() -> list[dict]:
    """通过 baostock 拉取所有 A 股 + 行业（证监会分类）。"""
    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock login 失败: {lg.error_msg}")

    try:
        # 1. 行业（含 code + code_name + industry）
        rs = bs.query_stock_industry()
        if rs.error_code != "0":
            raise RuntimeError(f"query_stock_industry 失败: {rs.error_msg}")

        industry_rows: list[list[str]] = []
        while rs.next():
            industry_rows.append(rs.get_row_data())
        logger.info("baostock 行业表行数: %d", len(industry_rows))

        out: list[dict] = []
        for row in industry_rows:
            # row = [updateDate, code, code_name, industry, industryClassification]
            if len(row) < 4:
                continue
            bs_code = row[1]
            name = row[2].strip()
            industry = (row[3] or "").strip()  # e.g. "J66货币金融服务" / 空
            if not name or not bs_code:
                continue
            # 跳过指数 (sh.000xxx / sz.399xxx 等)
            if bs_code.startswith(("sh.000", "sh.999", "sz.399")):
                continue

            ticker = _bs_code_to_ticker(bs_code)
            code = ticker.split(".")[0]

            # 拆出行业中文（去掉前导字母数字）
            industry_clean = industry
            # 形如 "J66货币金融服务" → 取中文部分
            import re
            m = re.match(r"^[A-Z]?\d*(.+)$", industry)
            if m:
                industry_clean = m.group(1).strip()

            out.append({
                "code": code,
                "ticker": ticker,
                "name": name,
                "exchange": _classify_exchange(ticker),
                "industry": industry_clean or None,
                "industry_raw": industry or None,
            })
        return out
    finally:
        bs.logout()


# ---------- THS 行业 / 概念板块名称 ----------

def fetch_board_names() -> tuple[list[str], list[str]]:
    """返回 (行业板块名列表, 概念板块名列表)。失败返回空。"""
    import akshare as ak
    industries: list[str] = []
    concepts: list[str] = []
    try:
        df = _retry(ak.stock_board_industry_name_ths, name="ths_industry_names")
        industries = [str(x).strip() for x in df["name"].tolist() if str(x).strip()]
        logger.info("THS 行业板块数: %d", len(industries))
    except Exception as e:
        logger.warning("THS 行业板块拉取失败: %s", e)

    try:
        df = _retry(ak.stock_board_concept_name_ths, name="ths_concept_names")
        concepts = [str(x).strip() for x in df["name"].tolist() if str(x).strip()]
        logger.info("THS 概念板块数: %d", len(concepts))
    except Exception as e:
        logger.warning("THS 概念板块拉取失败: %s", e)

    return industries, concepts


# ---------- 别名生成 ----------

_NAME_SUFFIX_STRIP = ["股份有限公司", "有限公司", "（集团）", "(集团)", "集团股份", "(", "（"]
# 标记型前缀（不去掉，但生成一个清洁版别名）
_NAME_PREFIX_MARKERS = ["*ST", "ST", "SST", "S*ST"]


def derive_aliases(name: str, ticker: str, code: str) -> list[tuple[str, str, int]]:
    """从公司名生成多个别名: (alias, alias_type, priority)。"""
    aliases: list[tuple[str, str, int]] = []
    name_clean = name.replace(" ", "").replace("　", "").replace("Ａ", "A").replace("Ｂ", "B")

    if name_clean and len(name_clean) >= 2:
        aliases.append((name_clean, "name", 90))

        # 去 ST 前缀
        for p in _NAME_PREFIX_MARKERS:
            if name_clean.startswith(p):
                bare = name_clean[len(p):].strip()
                if bare and len(bare) >= 2:
                    aliases.append((bare, "name_clean", 85))
                break

        # 去公司后缀
        short = name_clean
        for suf in _NAME_SUFFIX_STRIP:
            if suf in short:
                short = short.split(suf, 1)[0]
        short = short.strip()
        if short and short != name_clean and len(short) >= 2:
            aliases.append((short, "short", 75))

    # ticker + 纯6位代码
    aliases.append((ticker, "code", 60))
    if code and code != ticker:
        aliases.append((code, "code", 50))

    # 去重保留最大 priority
    dedup: dict[str, tuple[str, str, int]] = {}
    for a, t, p in aliases:
        # 太短的中文别名（<2字）会大量误命中，过滤
        if len(a) < 2:
            continue
        if a not in dedup or dedup[a][2] < p:
            dedup[a] = (a, t, p)
    return list(dedup.values())


# ---------- writers ----------

def upsert_stocks(conn, stocks: list[dict]):
    rows = [
        (s["ticker"], s["name"], s["exchange"], s.get("industry"), s.get("industry"))
        for s in stocks
    ]
    sql = """
        INSERT INTO stocks (symbol, name, exchange, industry, sector, is_active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (symbol) DO UPDATE
        SET name = EXCLUDED.name,
            exchange = EXCLUDED.exchange,
            industry = COALESCE(EXCLUDED.industry, stocks.industry),
            sector = COALESCE(EXCLUDED.sector, stocks.sector),
            is_active = TRUE,
            updated_at = NOW();
    """
    with conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=500)
    conn.commit()
    logger.info("stocks UPSERT 完成: %d", len(rows))


def upsert_aliases(conn, stocks: list[dict]):
    rows: list[tuple] = []
    for s in stocks:
        ind = s.get("industry")
        for alias, alias_type, prio in derive_aliases(s["name"], s["ticker"], s["code"]):
            rows.append((s["ticker"], alias, alias_type, prio, ind, ind))
    sql = """
        INSERT INTO stock_aliases (ticker, alias, alias_type, priority, industry, sector)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, alias) DO UPDATE
        SET alias_type = EXCLUDED.alias_type,
            priority = EXCLUDED.priority,
            industry = COALESCE(EXCLUDED.industry, stock_aliases.industry),
            sector = COALESCE(EXCLUDED.sector, stock_aliases.sector);
    """
    with conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=1000)
    conn.commit()
    logger.info("stock_aliases UPSERT 完成: %d", len(rows))


def upsert_board_lexicon(conn, industries: list[str], concepts: list[str], stock_industries: set[str]):
    """把行业板块名、概念板块名、股票自带行业写入 finance_lexicon（kind=event, event_tag=行业/概念/股票行业）。

    新闻匹配到这些词条后，前端可以反向召回相关股票（按 industry 列）。
    """
    rows: list[tuple] = []
    for n in industries:
        rows.append((n, "event", "行业板块", 1.0, "THS 一级行业板块", True))
    for n in concepts:
        rows.append((n, "event", "概念板块", 1.0, "THS 概念板块", True))
    for n in stock_industries:
        if n:
            rows.append((n, "event", "股票行业", 0.5, "baostock 证监会行业", True))

    if not rows:
        logger.info("无板块词条可写")
        return

    sql = """
        INSERT INTO finance_lexicon (term, kind, event_tag, weight, note, enabled)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (term, kind) DO UPDATE
        SET event_tag = EXCLUDED.event_tag,
            weight = EXCLUDED.weight,
            note = EXCLUDED.note,
            enabled = TRUE;
    """
    with conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=500)
    conn.commit()
    logger.info("finance_lexicon 板块词条 UPSERT: %d", len(rows))


# ---------- 内置金融情感与事件词 ----------

_BUILTIN_SENTIMENT_POS = [
    ("超预期", 1.0), ("利好", 1.0), ("大涨", 0.8), ("飙升", 0.9), ("增持", 0.7),
    ("回购", 0.6), ("收购", 0.4), ("中标", 0.7), ("订单", 0.4), ("突破", 0.6),
    ("创新高", 0.8), ("营收增长", 0.7), ("净利润增长", 0.8), ("分红", 0.5),
    ("送转", 0.4), ("批文", 0.5), ("获批", 0.6), ("放量", 0.3), ("回暖", 0.5),
    ("复苏", 0.5), ("提速", 0.5), ("扩产", 0.5), ("打开涨停", 0.5),
    ("基本面改善", 0.7), ("超额完成", 0.7), ("上调评级", 0.7), ("买入评级", 0.6),
]
_BUILTIN_SENTIMENT_NEG = [
    ("利空", -1.0), ("暴跌", -1.0), ("巨亏", -1.0), ("业绩预亏", -0.9),
    ("减持", -0.6), ("套现", -0.5), ("立案调查", -1.0), ("被处罚", -0.9),
    ("违规", -0.7), ("停牌", -0.4), ("退市", -1.0), ("ST", -0.6), ("*ST", -0.8),
    ("商誉减值", -0.8), ("计提减值", -0.7), ("跌停", -0.8), ("破发", -0.6),
    ("下调评级", -0.7), ("卖出评级", -0.7), ("亏损扩大", -0.9), ("营收下滑", -0.7),
    ("被起诉", -0.7), ("解禁", -0.4), ("质押", -0.3), ("商誉爆雷", -1.0),
    ("债务违约", -1.0), ("被动减持", -0.6), ("跑路", -1.0), ("股东减持", -0.5),
]
_BUILTIN_EVENTS = [
    ("回购", "回购"), ("增持", "增持"), ("减持", "减持"),
    ("业绩快报", "业绩"), ("业绩预告", "业绩"), ("业绩预增", "业绩超预期"),
    ("业绩预减", "业绩不及预期"), ("业绩预亏", "业绩不及预期"),
    ("重大资产重组", "重组"), ("并购", "并购"), ("收购", "并购"),
    ("定增", "定增"), ("可转债", "可转债"), ("IPO", "IPO"),
    ("中标", "中标"), ("订单", "订单"), ("立案调查", "监管"),
    ("被处罚", "监管"), ("违规", "监管"), ("退市", "退市"),
    ("分红", "分红"), ("送转", "送转"), ("股权激励", "激励"),
    ("股东大会", "公司治理"), ("更换董事长", "公司治理"),
    ("商誉减值", "减值"), ("计提减值", "减值"),
    ("解禁", "解禁"), ("质押", "质押"), ("债务违约", "债务"),
]


def upsert_builtin_lexicon(conn):
    rows: list[tuple] = []
    for term, weight in _BUILTIN_SENTIMENT_POS:
        rows.append((term, "sentiment_pos", None, weight, "内置正向情感词", True))
    for term, weight in _BUILTIN_SENTIMENT_NEG:
        rows.append((term, "sentiment_neg", None, abs(weight), "内置负向情感词", True))
    for term, tag in _BUILTIN_EVENTS:
        rows.append((term, "event", tag, 1.0, "内置事件类型", True))

    sql = """
        INSERT INTO finance_lexicon (term, kind, event_tag, weight, note, enabled)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (term, kind) DO UPDATE
        SET event_tag = EXCLUDED.event_tag,
            weight = EXCLUDED.weight,
            note = EXCLUDED.note,
            enabled = TRUE;
    """
    with conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=500)
    conn.commit()
    logger.info("finance_lexicon 内置情感/事件 UPSERT: %d", len(rows))


def main():
    logger.info("=== 开始 A 股基础信息种子 ===")

    stocks = fetch_stocks_baostock()
    if not stocks:
        logger.error("baostock 返回空，终止")
        sys.exit(1)
    logger.info("有效股票数: %d", len(stocks))

    industries_ths, concepts_ths = fetch_board_names()
    stock_industries = {s["industry"] for s in stocks if s.get("industry")}

    with _conn() as conn:
        upsert_stocks(conn, stocks)
        upsert_aliases(conn, stocks)
        upsert_board_lexicon(conn, industries_ths, concepts_ths, stock_industries)
        upsert_builtin_lexicon(conn)

    logger.info("=== 种子完成 ===")


if __name__ == "__main__":
    main()
