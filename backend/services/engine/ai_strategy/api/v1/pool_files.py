"""AI Strategy V1 股票池文件路由"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import anyio
from fastapi import APIRouter, Body, Request
from sqlalchemy import text

try:  # 部署模式优先 shared
    from shared.errors import ErrorCode  # type: ignore
    from shared.response import error, success  # type: ignore
except Exception:  # pragma: no cover
    from backend.shared.errors import ErrorCode  # type: ignore
    from backend.shared.response import error, success  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter()


def _legacy_routes_enabled() -> bool:
    return os.getenv("AI_STRATEGY_ENABLE_LEGACY_ROUTES", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@router.post("/legacy/strategy/save-pool-file")
async def save_pool_file(
    request: Request,
    payload: dict[str, Any] = Body(...),
):
    """保存股票池文件并绑定名称与 COS 地址"""
    if not _legacy_routes_enabled():
        return error(
            ErrorCode.FORBIDDEN,
            "legacy 路由已关闭，请使用 /api/v1/strategy/save-pool-file",
        )

    try:
        import anyio

        def _to_qlib_instrument(symbol: str) -> str:
            s = (symbol or "").strip()
            if not s:
                return ""
            u = s.upper()
            if len(u) == 8 and (u.startswith("SZ") or u.startswith("SH")) and u[2:].isdigit():
                return u
            if "." in u:
                base, suffix = u.split(".", 1)
                base = base.strip()
                suffix = suffix.strip()
                if suffix in ("SZ", "SH") and base.isdigit():
                    return f"{suffix}{base.zfill(6)}"
            if (u.startswith("SZ") or u.startswith("SH")) and len(u) >= 8:
                tail = "".join(ch for ch in u[2:] if ch.isdigit())
                if tail:
                    return f"{u[:2]}{tail.zfill(6)[:6]}"
            return u

        user_id = payload.get("user_id")
        tenant_id = payload.get("tenant_id")
        pool_format = payload.get("format", "txt")
        pool_list = payload.get("pool", [])
        pool_name = payload.get("pool_name", "").strip()

        if not user_id or not pool_list:
            return error(ErrorCode.PARAM_INVALID, "缺少必要参数")
        if not pool_name:
            return error(ErrorCode.PARAM_REQUIRED, "pool_name 不能为空")

        if pool_format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["symbol", "name"])
            for item in pool_list:
                writer.writerow([item.get("symbol"), item.get("name", "")])
            content = output.getvalue()
        elif pool_format == "txt":
            seen = set()
            lines = []
            for item in pool_list:
                q = _to_qlib_instrument(str(item.get("symbol", "")))
                if not q:
                    continue
                if q in seen:
                    continue
                seen.add(q)
                lines.append(q)
            content = "\n".join(lines) + ("\n" if lines else "")
        elif pool_format == "json":
            import json as _json

            content = _json.dumps(
                {
                    "generated_at": datetime.now().isoformat(),
                    "count": len(pool_list),
                    "symbols": pool_list,
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return error(ErrorCode.PARAM_INVALID, "format 仅支持 csv/json/txt")

        from ...services.cos_uploader import get_cos_uploader

        uploader = get_cos_uploader()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pool_id = f"pool_{int(datetime.now().timestamp())}"
        upload_res = await uploader.upload_pool_file(
            user_id=user_id,
            pool_id=pool_id,
            content=content,
            fmt=pool_format,
            timestamp=timestamp,
        )

        db_saved = True

        def _sync_write_db() -> None:
            nonlocal db_saved
            try:
                try:
                    from backend.shared.database_pool import get_db as get_sync_db  # type: ignore
                except Exception:
                    from shared.database_pool import get_db as get_sync_db  # type: ignore

                update_sql = """
                update stock_pool_files
                   set is_active = false
                 where user_id = :user_id
                   and is_active = true
                """
                params = {"user_id": user_id}
                if tenant_id:
                    update_sql += " and tenant_id = :tenant_id "
                    params["tenant_id"] = tenant_id

                insert_sql = """
                insert into stock_pool_files (
                    tenant_id, user_id, pool_name, file_key, file_url, relative_path,
                    format, file_size, code_hash, stock_count, is_active
                ) values (
                    :tenant_id, :user_id, :pool_name, :file_key, :file_url, :relative_path,
                    :format, :file_size, :code_hash, :stock_count, true
                )
                returning id
                """

                with get_sync_db() as session:
                    session.execute(text(update_sql), params)
                    result = session.execute(
                        text(insert_sql),
                        {
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "pool_name": pool_name,
                            "file_key": upload_res["object_key"],
                            "file_url": upload_res["url"],
                            "relative_path": upload_res.get("relative_path"),
                            "format": pool_format,
                            "file_size": upload_res["file_size"],
                            "code_hash": upload_res["code_hash"],
                            "stock_count": len(pool_list),
                        },
                    )
                    session.commit()
                    _ = result.scalar()
            except Exception as exc:
                db_saved = False
                logger.error("写入 stock_pool_files 失败(将继续返回上传成功): %s", exc)

        await anyio.to_thread.run_sync(_sync_write_db)

        return success(
            {
                "pool_id": pool_id,
                "pool_name": pool_name,
                "file_key": upload_res["object_key"],
                "file_url": upload_res["url"],
                "relative_path": upload_res.get("relative_path"),
                "file_size": upload_res["file_size"],
                "code_hash": upload_res["code_hash"],
                "stock_count": len(pool_list),
                "db_saved": db_saved,
            }
        )
    except Exception as e:
        logger.error("保存股票池失败: %s", e)
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/legacy/strategy/get-active-pool-file")
async def get_active_pool_file_endpoint(
    request: Request,
    payload: dict[str, Any] = Body(...),
):
    """获取活跃的股票池文件"""
    if not _legacy_routes_enabled():
        return error(
            ErrorCode.FORBIDDEN,
            "legacy 路由已关闭，请使用 /api/v1/strategy/get-active-pool-file",
        )

    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")

    if not user_id:
        return error(ErrorCode.PARAM_REQUIRED, "user_id 不能为空")

    try:
        def _sync_read_active() -> dict[str, Any] | None:
            try:
                try:
                    from backend.shared.database_pool import get_db as get_sync_db  # type: ignore
                except Exception:
                    from shared.database_pool import get_db as get_sync_db  # type: ignore

                base_sql = """
                select
                    id,
                    tenant_id,
                    user_id,
                    pool_name,
                    file_key,
                    file_url,
                    relative_path,
                    format,
                    file_size,
                    code_hash,
                    stock_count,
                    created_at,
                    updated_at,
                    is_active
                from stock_pool_files
                where user_id = :user_id
                  and is_active = true
                """
                if tenant_id:
                    base_sql += " and tenant_id = :tenant_id "
                base_sql += " order by created_at desc limit 1"

                params = {"user_id": user_id}
                if tenant_id:
                    params["tenant_id"] = tenant_id

                with get_sync_db() as session:
                    result = session.execute(text(base_sql), params)
                    row = result.mappings().first()
                    return dict(row) if row else None
            except Exception as exc:
                logger.error("读取活跃股票池失败: %s", exc)
                raise

        row = await anyio.to_thread.run_sync(_sync_read_active)
        if not row:
            return success({"pool_file": None})
        return success({"pool_file": row})
    except Exception as exc:
        logger.error("Get active pool file failed: %s", exc)
        return error(ErrorCode.INTERNAL_ERROR, f"获取失败: {exc}")
