#!/usr/bin/env python3
"""
一次性迁移脚本：将历史 user_strategies 迁移到 strategies。

特性：
- 幂等：通过 parameters.legacy_user_strategy_id 防重复迁移
- 支持 dry-run
- 支持按 user_id 过滤
- 默认尝试从 cos_url 读取代码写入 strategies.code/config.code
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import psycopg2
import psycopg2.extras


@dataclass
class Counters:
    total: int = 0
    migrated: int = 0
    skipped_exists: int = 0
    skipped_user_missing: int = 0
    skipped_code_missing: int = 0
    failed: int = 0


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def _db_config_from_env() -> Dict[str, Any]:
    return {
        "host": _env("DB_MASTER_HOST", "localhost"),
        "port": int(_env("DB_MASTER_PORT", "5432")),
        "dbname": _env("DB_NAME", "quantmind"),
        "user": _env("DB_USER", "quantmind"),
        "password": _env("DB_PASSWORD", ""),
    }


def _parse_tags(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        # PG text[] 在某些驱动场景可能返回 "{a,b}" 字符串
        if s.startswith("{") and s.endswith("}"):
            body = s[1:-1].strip()
            if not body:
                return []
            return [item.strip().strip('"') for item in body.split(",") if item.strip()]
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        return [s]
    return []


def _json_or_default(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default
    return default


def _read_code_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    if url.startswith("file://"):
        path = url[len("file://") :]
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    try:
        with urlopen(url, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError):
        return ""
    except Exception:
        return ""


def _resolve_user_int_id(cur, legacy_user_id: str) -> Optional[int]:
    # 优先按业务 user_id 映射
    cur.execute("SELECT id FROM users WHERE user_id = %s", (legacy_user_id,))
    row = cur.fetchone()
    if row:
        return int(row[0])

    # 兼容：如果 legacy_user_id 本身是数字，再按 users.id 尝试
    if legacy_user_id.isdigit():
        cur.execute("SELECT id FROM users WHERE id = %s", (int(legacy_user_id),))
        row2 = cur.fetchone()
        if row2:
            return int(row2[0])
    return None


def _already_migrated(cur, legacy_id: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM strategies
        WHERE parameters::jsonb ->> 'legacy_user_strategy_id' = %s
        LIMIT 1
        """,
        (legacy_id,),
    )
    return cur.fetchone() is not None


def migrate(args) -> int:
    cfg = _db_config_from_env()
    conn = psycopg2.connect(**cfg)
    conn.autocommit = False

    counters = Counters()
    errors: List[Tuple[str, str]] = []

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT id, user_id, strategy_name, description,
                       conditions, stock_pool, position_config, style, risk_config,
                       cos_url, file_size, code_hash,
                       qlib_validated, validation_result,
                       tags, is_public, downloads, created_at, updated_at
                FROM user_strategies
            """
            params: List[Any] = []
            where: List[str] = []
            if args.user_id:
                where.append("user_id = %s")
                params.append(args.user_id)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY created_at ASC"
            if args.limit and args.limit > 0:
                sql += " LIMIT %s"
                params.append(args.limit)

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            counters.total = len(rows)

            for row in rows:
                legacy_id = str(row["id"])
                try:
                    if _already_migrated(cur, legacy_id):
                        counters.skipped_exists += 1
                        continue

                    legacy_user_id = str(row["user_id"])
                    user_int_id = _resolve_user_int_id(cur, legacy_user_id)
                    if user_int_id is None:
                        counters.skipped_user_missing += 1
                        continue

                    code = _read_code_from_url(row.get("cos_url"))
                    if not code and not args.allow_empty_code:
                        counters.skipped_code_missing += 1
                        continue

                    tags = _parse_tags(row.get("tags"))
                    config = {
                        "code": code,
                        "legacy_migration": {
                            "from_table": "user_strategies",
                            "legacy_id": legacy_id,
                        },
                    }
                    parameters = {
                        "legacy_user_strategy_id": legacy_id,
                        "legacy_user_id": legacy_user_id,
                        "conditions": _json_or_default(row.get("conditions"), {}),
                        "stock_pool": _json_or_default(row.get("stock_pool"), {}),
                        "position_config": _json_or_default(row.get("position_config"), {}),
                        "style": row.get("style"),
                        "risk_config": _json_or_default(row.get("risk_config"), {}),
                        "qlib_validated": bool(row.get("qlib_validated") or False),
                        "validation_result": _json_or_default(row.get("validation_result"), {}),
                        "downloads": int(row.get("downloads") or 0),
                    }
                    created_at = row.get("created_at") or datetime.now()
                    updated_at = row.get("updated_at") or created_at

                    if args.dry_run:
                        counters.migrated += 1
                        continue

                    cur.execute(
                        """
                        INSERT INTO strategies (
                            user_id, name, description, strategy_type, status,
                            config, parameters, code, cos_url, code_hash, file_size,
                            tags, is_public, shared_users,
                            backtest_count, view_count, like_count,
                            created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, 'QUANTITATIVE', 'DRAFT',
                            CAST(%s AS json), CAST(%s AS json), %s, %s, %s, %s,
                            CAST(%s AS json), %s, CAST(%s AS json),
                            0, 0, 0,
                            %s, %s
                        )
                        """,
                        (
                            user_int_id,
                            row.get("strategy_name") or f"legacy-{legacy_id}",
                            row.get("description"),
                            json.dumps(config, ensure_ascii=False),
                            json.dumps(parameters, ensure_ascii=False),
                            code,
                            row.get("cos_url"),
                            row.get("code_hash"),
                            row.get("file_size"),
                            json.dumps(tags, ensure_ascii=False),
                            bool(row.get("is_public") or False),
                            json.dumps([], ensure_ascii=False),
                            created_at,
                            updated_at,
                        ),
                    )
                    counters.migrated += 1
                except Exception as e:
                    counters.failed += 1
                    errors.append((legacy_id, str(e)))
                    if args.fail_fast:
                        raise

            if args.dry_run:
                conn.rollback()
            else:
                conn.commit()

    finally:
        conn.close()

    print("=== Migration Summary ===")
    print(f"total={counters.total}")
    print(f"migrated={counters.migrated}")
    print(f"skipped_exists={counters.skipped_exists}")
    print(f"skipped_user_missing={counters.skipped_user_missing}")
    print(f"skipped_code_missing={counters.skipped_code_missing}")
    print(f"failed={counters.failed}")
    print(f"dry_run={args.dry_run}")

    if errors:
        print("=== Failures (legacy_id -> error) ===")
        for legacy_id, err in errors[:20]:
            print(f"{legacy_id} -> {err}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more")

    return 0 if counters.failed == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一次性迁移 user_strategies 到 strategies（幂等）")
    parser.add_argument("--user-id", default="", help="仅迁移指定 user_strategies.user_id")
    parser.add_argument("--limit", type=int, default=0, help="限制迁移条数（0 表示不限制）")
    parser.add_argument(
        "--allow-empty-code",
        action="store_true",
        help="允许 cos_url 读取失败时仍迁移（code 留空）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预演，不落库（会输出将要迁移的统计）",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="遇到第一条错误即退出",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return migrate(args)


if __name__ == "__main__":
    sys.exit(main())
