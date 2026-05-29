#!/usr/bin/env python3
"""
最小脚本：生成股票池列表文件并上传到腾讯云 COS。

注意：脚本内置的股票列表为“示例/合成数据”，仅用于测试。
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from backend.shared.cos_service import TencentCOSService

DEFAULT_SYMBOLS = [
    "SH600519",
    "SZ000001",
    "SH600036",
    "SZ000651",
    "SH601318",
]


def _load_env() -> None:
    project_root = Path(__file__).resolve().parents[3]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


def _parse_symbols(raw: str | None) -> List[str]:
    if not raw:
        return DEFAULT_SYMBOLS
    symbols = [item.strip() for item in raw.split(",")]
    return [item for item in symbols if item]


def _fetch_symbols_from_db(
    table: str,
    column: str,
) -> List[str]:
    host = os.getenv("DB_MASTER_HOST", "localhost")
    port = int(os.getenv("DB_MASTER_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    if not all([dbname, user, password]):
        raise RuntimeError("数据库配置不完整（DB_NAME/DB_USER/DB_PASSWORD）")

    try:
        import psycopg2  # type: ignore
        from psycopg2 import sql  # type: ignore

        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
        )
        try:
            with conn.cursor() as cur:
                query = sql.SQL("select distinct {col} from {tbl} where {col} is not null order by {col}").format(
                    col=sql.Identifier(column),
                    tbl=sql.Identifier(table),
                )
                cur.execute(query)
                rows = cur.fetchall()
                return [row[0] for row in rows if row and row[0]]
        finally:
            conn.close()
    except Exception:
        # fallback: use psql CLI
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            dbname,
            "-At",
            "-c",
            f"select distinct {column} from {table} where {column} is not null order by {column};",
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"psql 查询失败: {result.stderr.strip()}")
        lines = [line.strip() for line in result.stdout.splitlines()]
        return [line for line in lines if line]


def _write_pool_file(symbols: List[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for symbol in symbols:
            f.write(f"{symbol}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成股票池列表文件并上传到 COS")
    parser.add_argument(
        "--user-id",
        required=True,
        help="用户ID（用于隔离与路径前缀）",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="股票代码列表，逗号分隔。为空则使用示例/合成数据",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="从数据库表读取股票代码（优先于 --symbols）",
    )
    parser.add_argument(
        "--db-table",
        default="stock_daily_latest",
        help="股票表名（默认 stock_daily_latest）",
    )
    parser.add_argument(
        "--db-column",
        default="code",
        help="股票代码列名（默认 code）",
    )
    parser.add_argument(
        "--filename",
        default="stock_pool.txt",
        help="本地文件名",
    )
    args = parser.parse_args()

    _load_env()

    if args.from_db:
        symbols = _fetch_symbols_from_db(args.db_table, args.db_column)
    else:
        symbols = _parse_symbols(args.symbols)
    output_path = Path("/tmp") / args.filename
    _write_pool_file(symbols, output_path)

    cos = TencentCOSService()
    folder = f"stock_pools/{args.user_id}"
    result = cos.upload_file(str(output_path), output_path.name, folder=folder)

    print("上传成功")
    print(f"key: {result['key']}")
    print(f"url: {result['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
