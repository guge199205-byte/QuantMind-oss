#!/usr/bin/env python3
"""
从数据库构建股票搜索索引 JSON。

默认输出：
  data/stocks/stocks_index.json
可通过环境变量覆盖：
  STOCK_INDEX_JSON_PATH=/abs/path/stocks_index.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_sync_db_url() -> str:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        if "asyncpg" in db_url:
            return db_url.replace("asyncpg", "psycopg2")
        if db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return db_url

    host = os.getenv("DB_MASTER_HOST", "localhost")
    port = os.getenv("DB_MASTER_PORT", "5432")
    user = os.getenv("DB_USER", "quantmind")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    db_name = os.getenv("DB_NAME", "quantmind")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def _guess_exchange(code: str) -> str:
    c = str(code or "").strip()
    if c.startswith(("000", "001", "002", "003", "300")):
        return "SZ"
    if c.startswith(("600", "601", "603", "605", "688")):
        return "SH"
    if c.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize_symbol(code: str, exchange: str) -> str:
    c = str(code or "").strip()
    ex = str(exchange or "").strip().upper() or _guess_exchange(c)
    return f"{c}.{ex}"


def build_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        code = str(row.get("stock_code") or "").strip()
        name = str(row.get("stock_name") or "").strip()
        if not code or not name:
            continue
        exchange = str(row.get("exchange") or "").strip().upper() or _guess_exchange(code)
        symbol = _normalize_symbol(code, exchange)
        items.append(
            {
                "symbol": symbol,
                "code": code,
                "exchange": exchange,
                "name": name,
                # 预留字段：后续可通过离线任务补充拼音简称
                "abbr": code.lower(),
                "pinyin": "",
            }
        )
    return items


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name=:table
            LIMIT 1
            """),
        {"table": table_name},
    ).fetchone()
    return bool(row)


def main() -> None:
    output_path = os.path.abspath(os.getenv("STOCK_INDEX_JSON_PATH", "data/stocks/stocks_index.json"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    db_url = _build_sync_db_url()
    engine = create_engine(db_url)

    with engine.begin() as conn:
        if _table_exists(conn, "stocks"):
            sql = text("""
                SELECT stock_code, stock_name, exchange
                FROM stocks
                WHERE COALESCE(status, 1) = 1
                ORDER BY stock_code
                """)
        elif _table_exists(conn, "symbols"):
            sql = text("""
                SELECT
                  split_part(symbol, '.', 1) AS stock_code,
                  name AS stock_name,
                  COALESCE(NULLIF(exchange, ''), split_part(symbol, '.', 2)) AS exchange
                FROM symbols
                WHERE COALESCE(is_active, true) = true
                ORDER BY symbol
                """)
        else:
            raise RuntimeError("未找到可用股票表（stocks 或 symbols）")

        result = conn.execute(sql)
        rows = [dict(r._mapping) for r in result]

    items = build_items(rows)
    payload = {
        "generated_at": _now_iso(),
        "count": len(items),
        "items": items,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        json.dumps(
            {
                "ok": True,
                "output": output_path,
                "count": len(items),
                "generated_at": payload["generated_at"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
