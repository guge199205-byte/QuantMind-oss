#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史修复脚本：从 COS 回填 stock_pool_files 元数据。

用途：
1. 修复历史上“save-pool-file 假成功（仅上传 COS，未落库）”导致的不可复用问题。
2. 扫描 COS 前缀 user_pools/，按 user_id + file_key 幂等写入 stock_pool_files。

示例：
  # 仅预览，不写库
  PYTHONPATH=/Users/qusong/git/quantmind \
  python backend/services/engine/ai_strategy/scripts/backfill_stock_pool_files.py --dry-run

  # 实际回填
  PYTHONPATH=/Users/qusong/git/quantmind \
  python backend/services/engine/ai_strategy/scripts/backfill_stock_pool_files.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

POOL_KEY_PATTERN = re.compile(r"^user_pools/(?P<user_id>[^/]+)/(?P<ts>[^/]+)/(?P<name>[^/]+)$")


@dataclass
class PoolObject:
    user_id: str
    timestamp_folder: str
    file_name: str
    file_key: str
    fmt: str
    size: int
    last_modified: Optional[datetime]
    etag: str


def _load_env() -> None:
    root_env = Path(__file__).resolve().parents[5] / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=True)
    else:
        load_dotenv(override=True)


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if "asyncpg" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg2://")
    if url.startswith("postgresql"):
        return url
    host = os.getenv("DB_MASTER_HOST", os.getenv("DB_HOST", "localhost"))
    port = os.getenv("DB_MASTER_PORT", os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "quantmind")
    pwd = quote_plus(os.getenv("DB_PASSWORD", ""))
    name = os.getenv("DB_NAME", "quantmind")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"


def _make_engine() -> Engine:
    return create_engine(_db_url(), pool_pre_ping=True)


def _ensure_table(engine: Engine) -> None:
    sql_path = Path(__file__).resolve().parents[1] / "migrations" / "create_stock_pool_files.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"迁移文件不存在: {sql_path}")

    with engine.begin() as conn:
        exists = conn.execute(text("""
                SELECT EXISTS (
                  SELECT 1
                  FROM information_schema.tables
                  WHERE table_schema = 'public'
                    AND table_name = 'stock_pool_files'
                )
                """)).scalar()
        if exists:
            return
        conn.execute(text(sql_path.read_text(encoding="utf-8")))
        print("已自动创建表: public.stock_pool_files")


def _make_cos_client():
    from qcloud_cos import CosConfig, CosS3Client

    secret_id = os.getenv("TENCENT_SECRET_ID") or os.getenv("COS_SECRET_ID")
    secret_key = os.getenv("TENCENT_SECRET_KEY") or os.getenv("COS_SECRET_KEY")
    region = os.getenv("TENCENT_REGION") or os.getenv("COS_REGION") or "ap-guangzhou"
    bucket = os.getenv("TENCENT_BUCKET") or os.getenv("COS_BUCKET")
    if not (secret_id and secret_key and bucket):
        raise RuntimeError("COS 配置不完整，请检查 TENCENT_SECRET_ID/KEY/BUCKET")

    cfg = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Scheme="https")
    return CosS3Client(cfg), str(bucket), str(region)


def _cos_base_url(bucket: str, region: str) -> str:
    custom = (os.getenv("TENCENT_COS_URL") or os.getenv("COS_URL") or "").strip().rstrip("/")
    if custom:
        return custom
    return f"https://{bucket}.cos.{region}.myqcloud.com"


def _iter_pool_objects(
    max_files: int,
    user_filter: str,
) -> Iterable[PoolObject]:
    client, bucket, region = _make_cos_client()
    marker = ""
    produced = 0

    while True:
        resp = client.list_objects(
            Bucket=bucket,
            Prefix="user_pools/",
            Marker=marker,
            MaxKeys=1000,
        )

        for item in resp.get("Contents", []) or []:
            key = str(item.get("Key") or "").strip()
            m = POOL_KEY_PATTERN.match(key)
            if not m:
                continue
            user_id = m.group("user_id")
            if user_filter and user_id != user_filter:
                continue
            file_name = m.group("name")
            fmt = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            if fmt not in {"txt", "csv", "json"}:
                continue

            lm_raw = str(item.get("LastModified") or "")
            lm: Optional[datetime] = None
            if lm_raw:
                try:
                    lm = datetime.strptime(lm_raw, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        lm = datetime.strptime(lm_raw, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        lm = None

            etag = str(item.get("ETag") or "").strip('"')
            yield PoolObject(
                user_id=user_id,
                timestamp_folder=m.group("ts"),
                file_name=file_name,
                file_key=key,
                fmt=fmt,
                size=int(item.get("Size") or 0),
                last_modified=lm,
                etag=etag,
            )

            produced += 1
            if max_files > 0 and produced >= max_files:
                return

        if resp.get("IsTruncated") == "false":
            break
        marker = str(resp.get("NextMarker") or "")
        if not marker:
            break


def _count_symbols_from_content(content: str, fmt: str) -> Optional[int]:
    try:
        if fmt == "txt":
            symbols = {ln.strip().upper() for ln in content.splitlines() if ln.strip()}
            return len(symbols)

        if fmt == "csv":
            rows = list(csv.reader(content.splitlines()))
            if not rows:
                return 0
            start = 1 if rows[0] and rows[0][0].strip().lower() in {"symbol", "code"} else 0
            symbols = set()
            for row in rows[start:]:
                if not row:
                    continue
                s = (row[0] or "").strip().upper()
                if s:
                    symbols.add(s)
            return len(symbols)

        if fmt == "json":
            obj = json.loads(content)
            if isinstance(obj, dict) and isinstance(obj.get("symbols"), list):
                vals = obj.get("symbols") or []
                if vals and isinstance(vals[0], dict):
                    symbols = {
                        str(v.get("symbol", "")).strip().upper() for v in vals if str(v.get("symbol", "")).strip()
                    }
                    return len(symbols)
                symbols = {str(v).strip().upper() for v in vals if str(v).strip()}
                return len(symbols)
            if isinstance(obj, list):
                symbols = {
                    str(v.get("symbol", "")).strip().upper()
                    for v in obj
                    if isinstance(v, dict) and str(v.get("symbol", "")).strip()
                }
                return len(symbols)
    except Exception:
        return None
    return None


def _fetch_object_text(file_key: str) -> str:
    client, bucket, _region = _make_cos_client()
    resp = client.get_object(Bucket=bucket, Key=file_key)
    return resp["Body"].get_raw_stream().read().decode("utf-8")


def _upsert_row(
    engine: Engine,
    obj: PoolObject,
    base_url: str,
    stock_count: Optional[int],
    apply: bool,
) -> Tuple[str, int]:
    """
    Returns:
      (action, id_or_0) where action in {"insert","update","skip"}
    """
    file_url = f"{base_url}/{obj.file_key}"
    relative_path = f"{obj.timestamp_folder}/{obj.file_name}"
    pool_name = f"历史导入_{obj.timestamp_folder}"
    now = datetime.now()

    with engine.begin() as conn:
        existed = conn.execute(
            text("""
                SELECT id
                FROM stock_pool_files
                WHERE user_id = :uid AND file_key = :fkey
                ORDER BY id DESC
                LIMIT 1
                """),
            {"uid": obj.user_id, "fkey": obj.file_key},
        ).fetchone()

        if existed:
            sid = int(existed[0])
            if not apply:
                return "update", sid
            conn.execute(
                text("""
                    UPDATE stock_pool_files
                    SET file_url = :file_url,
                        relative_path = :relative_path,
                        format = :fmt,
                        file_size = :file_size,
                        code_hash = :code_hash,
                        stock_count = COALESCE(:stock_count, stock_count),
                        updated_at = :updated_at
                    WHERE id = :sid
                    """),
                {
                    "sid": sid,
                    "file_url": file_url,
                    "relative_path": relative_path,
                    "fmt": obj.fmt,
                    "file_size": obj.size,
                    "code_hash": obj.etag or None,
                    "stock_count": stock_count,
                    "updated_at": now,
                },
            )
            return "update", sid

        if not apply:
            return "insert", 0

        row = conn.execute(
            text("""
                INSERT INTO stock_pool_files (
                    tenant_id, user_id, pool_name, session_id,
                    file_key, file_url, relative_path, format,
                    file_size, code_hash, stock_count,
                    created_at, updated_at, is_active
                ) VALUES (
                    NULL, :uid, :pool_name, NULL,
                    :file_key, :file_url, :relative_path, :fmt,
                    :file_size, :code_hash, :stock_count,
                    :created_at, :updated_at, FALSE
                ) RETURNING id
                """),
            {
                "uid": obj.user_id,
                "pool_name": pool_name,
                "file_key": obj.file_key,
                "file_url": file_url,
                "relative_path": relative_path,
                "fmt": obj.fmt,
                "file_size": obj.size,
                "code_hash": obj.etag or None,
                "stock_count": stock_count,
                "created_at": obj.last_modified or now,
                "updated_at": now,
            },
        ).fetchone()
        return "insert", int(row[0]) if row else 0


def _fix_active_flags(engine: Engine, apply: bool) -> int:
    """
    每个 user_id 至少保证一条 is_active=true（若该用户当前全为 false）。
    """
    changed = 0
    with engine.begin() as conn:
        user_rows = conn.execute(text("SELECT DISTINCT user_id FROM stock_pool_files")).fetchall()
        for (uid,) in user_rows:
            has_active = conn.execute(
                text("SELECT 1 FROM stock_pool_files WHERE user_id=:uid AND is_active=TRUE LIMIT 1"),
                {"uid": uid},
            ).fetchone()
            if has_active:
                continue
            latest = conn.execute(
                text("""
                    SELECT id
                    FROM stock_pool_files
                    WHERE user_id=:uid
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """),
                {"uid": uid},
            ).fetchone()
            if not latest:
                continue
            changed += 1
            if apply:
                conn.execute(
                    text("UPDATE stock_pool_files SET is_active=TRUE WHERE id=:sid"),
                    {"sid": int(latest[0])},
                )
    return changed


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(description="回填 stock_pool_files 历史数据")
    parser.add_argument("--apply", action="store_true", help="执行写库（默认仅预览）")
    parser.add_argument("--dry-run", action="store_true", help="显式仅预览（与 --apply 互斥）")
    parser.add_argument("--user-id", default="", help="仅处理指定 user_id")
    parser.add_argument("--max-files", type=int, default=0, help="最多处理文件数（0=不限制）")
    parser.add_argument(
        "--compute-stock-count",
        action="store_true",
        help="读取对象内容并计算 stock_count（耗时更长）",
    )
    args = parser.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("--apply 与 --dry-run 不能同时使用")
    apply = bool(args.apply and not args.dry_run)

    engine = _make_engine()
    _ensure_table(engine)

    client, bucket, region = _make_cos_client()
    _ = client  # 仅用于初始化检查
    base_url = _cos_base_url(bucket, region)

    totals: Dict[str, int] = {"seen": 0, "insert": 0, "update": 0, "error": 0}

    for obj in _iter_pool_objects(max_files=args.max_files, user_filter=args.user_id):
        totals["seen"] += 1
        try:
            stock_count = None
            if args.compute_stock_count:
                content = _fetch_object_text(obj.file_key)
                stock_count = _count_symbols_from_content(content, obj.fmt)

            action, sid = _upsert_row(
                engine=engine,
                obj=obj,
                base_url=base_url,
                stock_count=stock_count,
                apply=apply,
            )
            totals[action] += 1
            if totals["seen"] <= 20:
                sid_text = f" id={sid}" if sid else ""
                print(f"[{action}] user={obj.user_id} key={obj.file_key}{sid_text}")
        except Exception as e:
            totals["error"] += 1
            print(f"[error] key={obj.file_key} err={e}")

    active_changed = _fix_active_flags(engine, apply=apply)

    mode = "APPLY" if apply else "DRY-RUN"
    print("")
    print(f"[{mode}] done")
    print(
        f"seen={totals['seen']} insert={totals['insert']} update={totals['update']} error={totals['error']} active_fixed={active_changed}"
    )


if __name__ == "__main__":
    main()
