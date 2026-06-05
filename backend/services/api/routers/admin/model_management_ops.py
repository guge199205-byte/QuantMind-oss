import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import exchange_calendars as xcals
except Exception:
    xcals = None

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.services.api.user_app.middleware.auth import require_admin
from backend.services.engine.inference.script_runner import InferenceScriptRunner
from backend.shared.database_manager_v2 import get_session
from backend.shared.redis_sentinel_client import get_redis_sentinel_client
from backend.shared.trading_calendar import calendar_service

try:
    from backend.services.engine.qlib_app.celery_config import celery_app
except ImportError:
    celery_app = None

from .model_management_utils import (
    FEATURE_SNAPSHOT_DIR,
    MODELS_PRODUCTION,
    MODELS_ROOT,
    _enrich_feature_catalog_with_data_coverage,
    _find_model_directories,
    _load_feature_catalog_from_db,
    _load_feature_catalog_from_file,
    _resolve_expected_feature_dim,
    _resolve_inference_dates_with_calendar,
    _resolve_ready_threshold,
    _scan_model_directory,
    _scan_feature_snapshots_status,
)

router = APIRouter()

DAILY_SYNC_SHELL_SCRIPT = (
    Path(os.getcwd()) / "scripts" / "data" / "maintenance" / "run_daily_pg_parquet_and_qlib_sync.sh"
)


class OfficialDataUpdateRequest(BaseModel):
    api_base_url: str | None = Field(default=None)
    access_key: str | None = Field(default=None)
    secret_key: str | None = Field(default=None)
    version: str | None = Field(default=None)
    dry_run: bool = Field(default=False)


@router.get("/scan", summary="扫描本地模型目录")
async def scan_model_directories(
    current_user: dict = Depends(require_admin),
):
    """
    自动扫描 models/ 下所有有效模型目录，聚合 metadata.json、
    workflow_config.yaml、best_params.yaml 等元数据文件，返回结构化列表。
    使用线程池避免阻塞事件循环。
    """
    import concurrent.futures

    try:
        dirs = _find_model_directories(MODELS_ROOT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描目录失败: {e}") from e

    def _scan_all():
        results = []
        for d in dirs:
            try:
                results.append(_scan_model_directory(d))
            except Exception as e:
                results.append({"model_id": Path(d).name, "dir_path": d, "error": str(e)})
        return results

    loop = __import__("asyncio").get_event_loop()
    results = await loop.run_in_executor(None, _scan_all)

    return {"total": len(results), "models": results}


@router.get("/feature-catalog", summary="获取模型训练特征字典（动态）")
async def get_model_feature_catalog(
    market: str | None = None,
    current_user: dict = Depends(require_admin),
):
    """
    返回训练页第一步所需的特征分类与字段列表：
    - 优先读取 PostgreSQL 特征注册表
    - 若注册表未初始化，回退到 config/features/*.json
    """
    _ = current_user
    try:
        catalog = await _load_feature_catalog_from_db()
    except Exception:
        catalog = None

    if catalog:
        return _enrich_feature_catalog_with_data_coverage(catalog, market=market)

    fallback = _load_feature_catalog_from_file()
    if fallback:
        return _enrich_feature_catalog_with_data_coverage(fallback, market=market)

    raise HTTPException(
        status_code=404, detail="未找到可用的特征字典（DB/文件均不可用）"
    )


@router.put("/feature-catalog", summary="更新特征字典（保存到 JSON 文件）")
async def update_feature_catalog(
    catalog: dict[str, Any],
    current_user: dict = Depends(require_admin),
):
    """保存特征字典到 JSON 文件，前端训练页下次加载时自动生效。"""
    categories = catalog.get("categories")
    if not isinstance(categories, list):
        raise HTTPException(status_code=400, detail="categories must be a list")

    # 计算总特征数
    total_features = 0
    for cat in categories:
        features = cat.get("features", [])
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail=f"Category '{cat.get('id')}' features must be a list")
        cat["feature_count"] = len(features)
        total_features += len(features)
    catalog["feature_count"] = total_features

    path = Path(os.getcwd()) / "config" / "features" / "model_training_feature_catalog_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "feature_count": total_features, "path": str(path)}


@router.get("/data-status", summary="查看当前数据状态（Qlib + 特征快照）")
async def get_data_status(
    refresh: bool = Query(False, description="是否强制刷新（后台异步）"),
    market: str = Query("a_share", description="市场: a_share, crypto, hong_kong, us_stock"),
    current_user: dict = Depends(require_admin),
):
    """
    管理后台数据管理接口：
    - 优先从 Redis 获取缓存结果
    - Qlib 文件数据（calendar/instruments/features）状态
    - feature_snapshots 目录下的 parquet 文件状态
    - 支持按市场筛选
    """
    _ = current_user
    redis = None
    try:
        redis = get_redis_sentinel_client()
    except Exception:
        pass

    # 非 A 股市场使用市场专属缓存 key
    cache_key = f"qm:admin:data_status:{market}"

    # 1. 如果不是强制刷新，尝试读取缓存
    if not refresh and redis:
        try:
            cached = redis.get(cache_key)
            if cached:
                result = json.loads(cached)
                result["from_cache"] = True
                return result
        except Exception as e:
            print(f"Redis cache read failed: {e}")

    # 2. 如果强制刷新，或者没缓存，则触发后台任务
    if celery_app:
        try:
            celery_app.send_task("engine.tasks.get_data_status_task")
        except Exception as e:
            print(f"Failed to trigger background task: {e}")

    # 3. 实时辅助扫描（作为 fallback 或首次加载的快速反馈）
    try:
        now_local = datetime.now(ZoneInfo("Asia/Shanghai"))
        tenant_id = str(current_user.get("tenant_id") or "default")
        user_id = str(current_user.get("user_id") or current_user.get("sub") or "admin")

        # 市场 → Qlib 子目录映射
        market_qlib_dirs = {
            "a_share": Path(os.getcwd()) / "db" / "qlib_data",
            "crypto": Path(os.getcwd()) / "db" / "qlib_data" / "crypto_data",
            "hong_kong": Path(os.getcwd()) / "db" / "qlib_data" / "hk_data",
            "us_stock": Path(os.getcwd()) / "db" / "qlib_data" / "us_data",
        }

        # 市场 → 交易日历服务 market 代码
        calendar_market_map = {
            "a_share": "SSE",
            "crypto": "SSE",  # 7x24，用 A 股日历近似
            "hong_kong": "HKEX",
            "us_stock": "NYSE",
        }

        cal_market = calendar_market_map.get(market, "SSE")

        if now_local.time() < datetime.strptime("09:30", "%H:%M").time():
            trade_date_obj = await calendar_service.prev_trading_day(
                market=cal_market,
                trade_date=now_local.date(),
                tenant_id=tenant_id,
                user_id=user_id
            )
        else:
            is_td = await calendar_service.is_trading_day(
                market=cal_market,
                trade_date=now_local.date(),
                tenant_id=tenant_id,
                user_id=user_id
            )
            if is_td:
                trade_date_obj = now_local.date()
            else:
                trade_date_obj = await calendar_service.prev_trading_day(
                    market=cal_market,
                    trade_date=now_local.date(),
                    tenant_id=tenant_id,
                    user_id=user_id
                )
        trade_date = trade_date_obj.isoformat()

        # ========== Qlib 数据状态扫描（市场感知） ==========
        qlib_data_dir = market_qlib_dirs.get(market, market_qlib_dirs["a_share"])

        # 日历文件名：crypto 用 5min.txt，其他用 day.txt
        calendar_files = []
        cal_dir = qlib_data_dir / "calendars"
        if cal_dir.exists():
            for f in cal_dir.iterdir():
                if f.suffix == ".txt":
                    calendar_files.append(f.name)

        cal_file = "5min.txt" if market == "crypto" and (cal_dir / "5min.txt").exists() else "day.txt"
        calendars_path = qlib_data_dir / "calendars" / cal_file
        instruments_all_path = qlib_data_dir / "instruments" / "all.txt"
        features_root = qlib_data_dir / "features"

        qlib_info: dict[str, Any] = {
            "qlib_dir": str(qlib_data_dir),
            "exists": qlib_data_dir.exists() and qlib_data_dir.is_dir(),
            "calendar_total_days": 0,
            "calendar_start_date": None,
            "calendar_last_date": None,
            "calendar_files": calendar_files,
            "instruments": {"total": 0, "sh": 0, "sz": 0, "bj": 0, "other": 0},
            "feature_dirs_total": 0,
            "feature_dirs_sh_sz_bj": 0,
            "latest_date_coverage": {
                "target_date": None,
                "at_target_count": 0,
                "older_count": 0,
                "invalid_count": 0,
            },
        }

        calendar: list[str] = []
        if calendars_path.exists():
            try:
                calendar = [
                    x.strip()
                    for x in calendars_path.read_text(encoding="utf-8").splitlines()
                    if x.strip()
                ]
                if calendar:
                    qlib_info["calendar_total_days"] = len(calendar)
                    qlib_info["calendar_start_date"] = calendar[0]
                    qlib_info["calendar_last_date"] = calendar[-1]
                    qlib_info["latest_date_coverage"]["target_date"] = calendar[-1]
            except Exception:
                pass

        if instruments_all_path.exists():
            try:
                for line in instruments_all_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    code = line.split()[0].strip().upper()
                    qlib_info["instruments"]["total"] += 1
                    if code.startswith("SH"):
                        qlib_info["instruments"]["sh"] += 1
                    elif code.startswith("SZ"):
                        qlib_info["instruments"]["sz"] += 1
                    elif code.startswith("BJ"):
                        qlib_info["instruments"]["bj"] += 1
                    else:
                        qlib_info["instruments"]["other"] += 1
            except Exception:
                pass

        if features_root.exists() and features_root.is_dir():
            feature_dirs = [p for p in features_root.iterdir() if p.is_dir()]
            qlib_info["feature_dirs_total"] = len(feature_dirs)
            qlib_info["sync_partial"] = True

        # ========== Feature Snapshots 状态扫描 ==========
        feature_snapshots_info = _scan_feature_snapshots_status(
            target_date=trade_date,
            topn=20,
            market=market,
        )

        return {
            "checked_at": now_local.isoformat(),
            "trade_date": trade_date,
            "market": market,
            "qlib_data": qlib_info,
            "feature_snapshots": feature_snapshots_info,
            "async_trigger": bool(celery_app),
            "message": "数据正在后台扫描中，请稍后刷新"
            if not refresh
            else "已触发强制刷新任务",
        }
    except Exception as e:
        import traceback
        error_msg = f"Data status scanning failed: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "market": market,
            "qlib_data": {"exists": False},
            "feature_snapshots": {"exists": False},
            "message": f"状态扫描异常: {str(e)}"
        }


@router.post(
    "/sync-stock-daily-latest",
    summary="手动触发 Baostock 同步基础行情到 stock_daily_latest",
)
async def sync_stock_daily_latest(
    target_date: str | None = Query(None, description="目标日期 YYYY-MM-DD，默认今天"),
    max_symbols: int = Query(
        0, ge=0, le=10000, description="仅处理前 N 个标的（0=全部）"
    ),
    apply: bool = Query(True, description="是否执行写入（false=dry-run）"),
    background: bool = Query(
        True, description="是否在后台执行（解决 504 超时业务推荐）"
    ),
    current_user: dict = Depends(require_admin),
):
    """
    [已废弃] 数据现由官方服务器统一推送，不再需要手动从 Baostock 同步。
    """
    _ = current_user

    raise HTTPException(
        status_code=410, detail="该接口已废弃，数据由官方服务器统一推送，无需手动同步"
    )


@router.post(
    "/sync-official-data-update",
    summary="一键拉取并应用官方数据增量包",
)
async def sync_official_data_update(
    payload: OfficialDataUpdateRequest,
    current_user: dict = Depends(require_admin),
):
    _ = current_user

    # OSS 部署模式：直接在当前容器内执行 Python 同步脚本
    # 脚本路径在容器内为 /app/scripts/data/maintenance/
    scripts_dir = Path("/app/scripts/data/maintenance")
    processing_dir = Path("/app/scripts/data/processing")

    # 按顺序执行同步步骤（完整流程：远程PG → parquet → qlib/stock_daily → 收益计算）
    steps = [
        ("Step 0: 从远程PG拉取最新数据", "sync_parquets_from_remote_pg.py"),
        ("Step 1: 同步 qlib_data", "sync_qlib_from_fundamental_parquet.py"),
        ("Step 2: 同步 stock_daily_latest", "sync_stock_daily_latest_from_parquet.py"),
        ("Step 3: 滚动计算一日/三日收益", "../processing/backfill_return_fields.py"),
    ]

    results = []
    for step_name, script_name in steps:
        # 处理相对路径
        if script_name.startswith("../"):
            script_path = processing_dir / script_name[3:]
        else:
            script_path = scripts_dir / script_name

        if not script_path.exists():
            results.append({
                "step": step_name,
                "success": False,
                "error": f"脚本不存在: {script_path}",
            })
            continue

        # 收益计算脚本需要 --recent-days 参数
        cmd = ["python", str(script_path)]
        if "backfill_return" in script_name:
            cmd.extend(["--recent-days", "5"])

        try:
            proc = subprocess.run(
                cmd,
                cwd="/app",
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
            results.append({
                "step": step_name,
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[-2000:] if proc.stdout else "",
                "stderr": proc.stderr[-2000:] if proc.stderr else "",
            })
        except subprocess.TimeoutExpired as exc:
            results.append({
                "step": step_name,
                "success": False,
                "error": f"执行超时: {exc}",
            })
        except Exception as exc:
            results.append({
                "step": step_name,
                "success": False,
                "error": str(exc),
            })

    all_success = all(r.get("success", False) for r in results)
    return {
        "success": all_success,
        "steps": results,
    }


@router.post(
    "/update-feature-parquet",
    summary="更新特征快照 Parquet（从 DB 计算全部 51 个模型特征）",
)
async def update_feature_parquet(
    rebuild: bool = Query(False, description="是否重建全部日期的特征（默认仅补充缺失日期）"),
    current_user: dict = Depends(require_admin),
):
    """
    运行 update_feature_parquet.py 脚本，从 stock_daily_latest 读取 OHLCV 数据，
    计算全部 51 个模型特征（动量、波动率、流动性、资金流、风格因子等），
    更新 /app/db/feature_snapshots/model_features_2026.parquet。
    """
    _ = current_user

    script_path = Path("/app/backend/scripts/update_feature_parquet.py")
    if not script_path.exists():
        raise HTTPException(status_code=404, detail=f"脚本不存在: {script_path}")

    cmd = ["python", str(script_path)]
    if rebuild:
        cmd.append("--rebuild")

    try:
        proc = subprocess.run(
            cmd,
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-3000:] if proc.stdout else "",
            "stderr": proc.stderr[-3000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="特征更新超时（>600s），请稍后重试")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/update-market-features",
    summary="更新非 A 股市场的特征快照（从 H5 数据计算 OHLCV 特征）",
)
async def update_market_features(
    market: str = Query(..., description="市场: crypto, hong_kong, us_stock"),
    rebuild: bool = Query(False, description="是否重建全部特征（默认增量）"),
    current_user: dict = Depends(require_admin),
):
    """
    运行 update_market_features.py 脚本，从 H5 文件读取 OHLCV 数据，
    计算 134 维模型特征，保存到 market-specific parquet。
    """
    _ = current_user

    if market not in ("crypto", "hong_kong", "us_stock"):
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    script_path = Path("/app/backend/scripts/update_market_features.py")
    if not script_path.exists():
        # 回退到主机路径
        script_path = Path(os.getcwd()) / "backend" / "scripts" / "update_market_features.py"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail=f"脚本不存在: {script_path}")

    cmd = ["python", str(script_path), "--market", market]
    if rebuild:
        cmd.append("--rebuild")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(script_path.parent.parent.parent),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return {
            "success": proc.returncode == 0,
            "market": market,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-3000:] if proc.stdout else "",
            "stderr": proc.stderr[-3000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="特征更新超时（>600s），请稍后重试")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/sync-stock-daily-full",
    summary="日常全量同步：从本地 parquet 补齐 stock_daily_latest 所有列（含 is_st/指数成分/技术指标等）",
)
async def sync_stock_daily_full(
    max_days: int = Query(30, ge=1, le=365, description="同步最近 N 个交易日（默认30）"),
    current_user: dict = Depends(require_admin),
):
    """
    从 /app/db/custom/fundamental_aligned.parquet 全量同步所有列到 stock_daily_latest。
    包含 is_st、idx_hs300、idx_zz1000、idx_margin、各类技术指标、概念标签等。
    """
    _ = current_user

    script_path = Path("/app/scripts/data/maintenance/sync_stock_daily_full.py")
    if not script_path.exists():
        raise HTTPException(status_code=404, detail=f"同步脚本不存在: {script_path}")

    try:
        env = os.environ.copy()
        env["SYNC_MAX_DAYS"] = str(max_days)
        proc = subprocess.run(
            ["python", str(script_path)],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env=env,
        )
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-3000:] if proc.stdout else "",
            "stderr": proc.stderr[-3000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="同步超时，请检查数据量是否过大")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"同步执行异常: {exc}")


@router.get("/precheck-inference", summary="生成明日信号前置检查")
async def precheck_inference(
    current_user: dict = Depends(require_admin),
):
    """
    在执行“生成明日信号”前检查关键依赖是否存在。
    仅返回可读检查结果，不执行实际推理。
    """
    checks: list[dict[str, Any]] = []

    production_dir = Path(MODELS_PRODUCTION)
    production_exists = production_dir.exists() and production_dir.is_dir()
    checks.append(
        {
            "key": "production_model_dir",
            "label": "生产模型目录存在",
            "passed": production_exists,
            "detail": str(production_dir),
        }
    )

    model_files = []
    for ext in ["bin", "txt", "pkl", "pth", "onnx", "pt"]:
        model_files.extend(list(production_dir.glob(f"model.{ext}")))

    model_exists = len(model_files) > 0
    checks.append(
        {
            "key": "model_file",
            "label": "模型文件存在（model.txt/bin/pkl/etc）",
            "passed": model_exists,
            "detail": str(model_files[0]) if model_files else "None",
        }
    )

    metadata_file = production_dir / "metadata.json"
    metadata_exists = metadata_file.exists() and metadata_file.is_file()
    checks.append(
        {
            "key": "metadata",
            "label": "模型元数据存在（metadata.json）",
            "passed": metadata_exists,
            "detail": str(metadata_file),
        }
    )

    qlib_data_dir = Path(os.path.join(os.getcwd(), "db", "qlib_data"))
    qlib_data_exists = qlib_data_dir.exists() and qlib_data_dir.is_dir()
    checks.append(
        {
            "key": "qlib_data_dir",
            "label": "Qlib 数据目录存在",
            "passed": qlib_data_exists,
            "detail": str(qlib_data_dir),
        }
    )

    # 业务门禁：统一日期口径（数据交易日 + 预测生效交易日）
    tz = ZoneInfo("Asia/Shanghai")
    now_local = datetime.now(tz)
    (
        requested_data_trade_date_str,
        data_trade_date_str,
        prediction_trade_date_str,
        calendar_adjusted,
    ) = await _resolve_inference_dates_with_calendar(
        current_user=current_user, now_local=now_local
    )
    trade_date_obj = date.fromisoformat(data_trade_date_str)
    checks.append(
        {
            "key": "calendar_trade_date",
            "label": "交易日历校验",
            "passed": True,
            "detail": (
                f"候选 {requested_data_trade_date_str} 非交易日，已回退到 {data_trade_date_str}"
                if calendar_adjusted
                else f"{data_trade_date_str} 为交易日"
            ),
        }
    )

    checks.append(
        {
            "key": "data_trade_date",
            "label": "检测数据交易日",
            "passed": True,
            "detail": data_trade_date_str,
        }
    )
    checks.append(
        {
            "key": "prediction_trade_date",
            "label": "预测生效交易日（明日）",
            "passed": True,
            "detail": prediction_trade_date_str,
        }
    )

    runner = InferenceScriptRunner(MODELS_PRODUCTION)
    primary_script_exists = runner.check_script_exists()
    fallback_script_exists = runner.check_fallback_script_exists()
    inference_script_exists = primary_script_exists or fallback_script_exists
    checks.append(
        {
            "key": "inference_script",
            "label": "推理脚本存在（主/兜底至少一套）",
            "passed": inference_script_exists,
            "detail": (
                f"primary={Path(runner.primary_model_dir) / runner.primary_script_name} exists={primary_script_exists}; "
                f"fallback={Path(runner.fallback_model_dir) / runner.fallback_script_name} exists={fallback_script_exists}"
            ),
        }
    )

    expected_feature_dim = _resolve_expected_feature_dim(production_dir)
    checks.append(
        {
            "key": "expected_feature_dim",
            "label": "生产模型期望特征维度",
            "passed": True,
            "detail": str(expected_feature_dim),
        }
    )

    # 业务门禁：检查当日数据是否已落库
    data_stats: dict[str, Any] = {}
    dim_ready_rows = 0
    feature_cols_count = 0
    has_features_json = False
    dim_source = "none"
    try:
        async with get_session(read_only=True) as session:
            stat_sql = text("""
                SELECT
                    MAX(trade_date) AS latest_trade_date,
                    MAX(updated_at) AS latest_updated_at,
                    COUNT(*) FILTER (WHERE trade_date = :trade_date) AS today_rows
                FROM stock_daily_latest
                """)
            row = (
                (
                    await session.execute(
                        stat_sql,
                        {
                            "trade_date": trade_date_obj,
                        },
                    )
                )
                .mappings()
                .first()
            )
            data_stats = dict(row or {})

            schema_columns = (
                (
                    await session.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'stock_daily_latest'
                            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            column_names = {
                str((row or {}).get("column_name") or "") for row in schema_columns
            }
            has_features_json = "features" in column_names
            feature_columns = sorted(
                [c for c in column_names if re.fullmatch(r"feature_\d+", c)],
                key=lambda c: int(c.split("_", 1)[1]),
            )
            feature_cols_count = len(feature_columns)

            dim_expr_candidates: list[str] = []
            if has_features_json:
                dim_expr_candidates.append(
                    "CASE WHEN jsonb_typeof(features) = 'array' THEN jsonb_array_length(features) ELSE 0 END"
                )
            if feature_columns:
                cols_dim_expr = " + ".join(
                    [
                        f"(CASE WHEN {col} IS NULL THEN 0 ELSE 1 END)"
                        for col in feature_columns
                    ]
                )
                dim_expr_candidates.append(f"({cols_dim_expr})")

            if len(dim_expr_candidates) >= 2:
                dim_source = "features_json+feature_columns"
                dim_expr = f"GREATEST({', '.join(dim_expr_candidates)})"
            elif len(dim_expr_candidates) == 1:
                dim_source = "features_json" if has_features_json else "feature_columns"
                dim_expr = dim_expr_candidates[0]
            else:
                # 表中既没有 features 也没有 feature_* 时，维度门禁必然不通过（但不应报 SQL 错）
                dim_source = "none"
                dim_expr = "0"

            dim_condition = f"({dim_expr}) >= :expected_feature_dim"

            dim_row = (
                (
                    await session.execute(
                        text(
                            f"""
                            SELECT COUNT(*) FILTER (
                                WHERE trade_date = :trade_date AND ({dim_condition})
                            ) AS dim_ready_rows
                            FROM stock_daily_latest
                            """
                        ),
                        {
                            "trade_date": trade_date_obj,
                            "expected_feature_dim": expected_feature_dim,
                        },
                    )
                )
                .mappings()
                .first()
            )
            dim_ready_rows = int((dim_row or {}).get("dim_ready_rows") or 0)
    except Exception as e:
        checks.append(
            {
                "key": "market_data_daily_query",
                "label": "market_data_daily 可查询",
                "passed": False,
                "detail": f"query_error={e}",
            }
        )

    if data_stats:
        latest_trade_date = data_stats.get("latest_trade_date")
        today_rows = int(data_stats.get("today_rows") or 0)
        required_ready_symbols, min_ready_symbols, min_ready_ratio, min_ready_floor = (
            _resolve_ready_threshold(today_rows)
        )

        checks.append(
            {
                "key": "latest_trade_date_today",
                "label": "最新特征交易日已就绪",
                "passed": str(latest_trade_date) >= data_trade_date_str,
                "detail": f"latest_trade_date={latest_trade_date} expected={data_trade_date_str}",
            }
        )
        checks.append(
            {
                "key": "today_rows_exists",
                "label": f"目标日({data_trade_date_str})数据已入库",
                "passed": today_rows > 0,
                "detail": (
                    f"rows={today_rows}"
                    if today_rows > 0
                    else f"stock_daily_latest 未发现 {data_trade_date_str} 数据"
                ),
            }
        )
        checks.append(
            {
                "key": "ready_symbols_threshold",
                "label": f"今日数据覆盖数 >= {required_ready_symbols}（自适应）",
                "passed": today_rows >= required_ready_symbols,
                "detail": (
                    f"actual={today_rows}, threshold={required_ready_symbols}, "
                    f"min_symbols={min_ready_symbols}, ratio={min_ready_ratio:.2f}, floor={min_ready_floor}"
                ),
            }
        )
        checks.append(
            {
                "key": "feature_dim_ready_threshold",
                "label": f"今日满足模型维度({expected_feature_dim})覆盖数 >= {required_ready_symbols}（自适应）",
                "passed": dim_ready_rows >= required_ready_symbols,
                "detail": (
                    f"dim_ready_rows={dim_ready_rows}, threshold={required_ready_symbols}, "
                    f"feature_columns={feature_cols_count}, features_json={has_features_json}, "
                    f"dim_source={dim_source}, min_symbols={min_ready_symbols}, "
                    f"ratio={min_ready_ratio:.2f}, floor={min_ready_floor}"
                ),
            }
        )

    return {
        "passed": all(bool(item.get("passed")) for item in checks),
        "checked_at": datetime.now().isoformat(),
        "requested_inference_date": requested_data_trade_date_str,
        "calendar_adjusted": calendar_adjusted,
        "data_trade_date": data_trade_date_str,
        "prediction_trade_date": prediction_trade_date_str,
        "items": checks,
    }


# ── 滚动回测（模型预测质量评估） ─────────────────────────────────────────


class BacktestRequest(BaseModel):
    model_id: str = Field(..., description="模型ID（目录名）")
    start_date: str = Field(..., description="回测起始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="回测结束日期 YYYY-MM-DD")
    horizon: int = Field(default=10, description="预测周期 T+N（天）")
    sample_interval: int = Field(default=3, description="每隔 N 个交易日采样一次")
    model_config = {"protected_namespaces": ()}


@router.post("/backtest", summary="滚动回测评估模型预测质量")
async def run_model_backtest(
    request: BacktestRequest,
    current_user: dict = Depends(require_admin),
):
    """
    对指定模型在历史日期范围内进行滚动回测。
    每隔 sample_interval 个交易日执行一次推理，对比预测分数与实际 mom_ret_{horizon}d，
    计算 IC、IC_IR、十分位收益、命中率等指标。
    """
    import asyncio

    from backend.services.engine.inference.backtest_service import BacktestService
    from backend.services.engine.inference.data_loader import get_available_dates

    # 1. Resolve model directory
    model_id = request.model_id
    model_dir = None

    # Search in user models
    user_models_root = Path(MODELS_ROOT) / "users"
    for d in user_models_root.rglob(model_id):
        if (d / "metadata.json").exists():
            model_dir = d
            break

    # Search in production
    if model_dir is None:
        prod_dir = Path(MODELS_PRODUCTION)
        for d in prod_dir.rglob(model_id):
            if (d / "metadata.json").exists():
                model_dir = d
                break

    if model_dir is None:
        raise HTTPException(status_code=404, detail=f"模型 {model_id} 未找到")

    # 2. Get available trading dates in range
    data_dir = os.path.join(os.getcwd(), "db", "feature_snapshots")
    available_dates = get_available_dates(
        data_dir=data_dir,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not available_dates:
        raise HTTPException(
            status_code=400,
            detail=f"日期范围 {request.start_date} ~ {request.end_date} 内无可用数据",
        )

    # 3. Sample dates
    interval = max(1, request.sample_interval)
    sampled_dates = available_dates[::interval]

    # Ensure last date is included
    if available_dates[-1] not in sampled_dates:
        sampled_dates.append(available_dates[-1])

    if len(sampled_dates) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"采样后日期不足（仅 {len(sampled_dates)} 天），请扩大日期范围或减小采样间隔",
        )

    # 4. Run backtest
    try:
        backtest_service = BacktestService()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: backtest_service.run_backtest(
                model_id=model_id,
                dates=sampled_dates,
                horizon=request.horizon,
                model_dir=model_dir,
                data_dir=data_dir,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {e}")

    return result


class MultiHorizonBacktestRequest(BaseModel):
    model_id: str = Field(..., description="模型ID（目录名）")
    start_date: str = Field(..., description="回测起始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="回测结束日期 YYYY-MM-DD")
    horizons: list[int] = Field(default=[1, 5, 10, 20], description="预测周期列表")
    sample_interval: int = Field(default=3, description="每隔 N 个交易日采样一次")
    model_config = {"protected_namespaces": ()}


@router.post("/backtest/multi-horizon", summary="多周期对比回测")
async def run_multi_horizon_backtest(
    request: MultiHorizonBacktestRequest,
    current_user: dict = Depends(require_admin),
):
    """对同一模型在多个预测周期（T+1, T+5, T+10, T+20）上进行回测比较。"""
    import asyncio

    from backend.services.engine.inference.backtest_service import BacktestService
    from backend.services.engine.inference.data_loader import get_available_dates

    model_id = request.model_id
    model_dir = None

    user_models_root = Path(MODELS_ROOT) / "users"
    for d in user_models_root.rglob(model_id):
        if (d / "metadata.json").exists():
            model_dir = d
            break

    if model_dir is None:
        prod_dir = Path(MODELS_PRODUCTION)
        for d in prod_dir.rglob(model_id):
            if (d / "metadata.json").exists():
                model_dir = d
                break

    if model_dir is None:
        raise HTTPException(status_code=404, detail=f"模型 {model_id} 未找到")

    data_dir = os.path.join(os.getcwd(), "db", "feature_snapshots")
    available_dates = get_available_dates(
        data_dir=data_dir,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not available_dates:
        raise HTTPException(
            status_code=400,
            detail=f"日期范围 {request.start_date} ~ {request.end_date} 内无可用数据",
        )

    interval = max(1, request.sample_interval)
    sampled_dates = available_dates[::interval]
    if available_dates[-1] not in sampled_dates:
        sampled_dates.append(available_dates[-1])

    if len(sampled_dates) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"采样后日期不足（仅 {len(sampled_dates)} 天）",
        )

    try:
        backtest_service = BacktestService()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: backtest_service.run_multi_horizon_backtest(
                model_id=model_id,
                dates=sampled_dates,
                horizons=request.horizons,
                model_dir=model_dir,
                data_dir=data_dir,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"多周期回测失败: {e}")

    return result


@router.get("/backtest/trading-dates", summary="获取可用回测日期列表")
async def get_backtest_trading_dates(
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    current_user: dict = Depends(require_admin),
):
    """返回指定日期范围内的所有可用交易日。"""
    from backend.services.engine.inference.data_loader import get_available_dates

    data_dir = os.path.join(os.getcwd(), "db", "feature_snapshots")
    dates = get_available_dates(data_dir=data_dir, start_date=start, end_date=end)
    return {"status": "success", "dates": dates, "count": len(dates)}


@router.get("/list-for-backtest", summary="获取可用于回测的模型列表")
async def list_models_for_backtest(
    current_user: dict = Depends(require_admin),
):
    """列出所有已训练完成的模型（含 user 和 system 模型），用于回测选择。"""
    models = []

    # User models
    user_root = Path(MODELS_ROOT) / "users"
    if user_root.exists():
        for meta_file in user_root.rglob("metadata.json"):
            model_dir = meta_file.parent
            try:
                with open(meta_file, encoding="utf-8") as f:
                    meta = json.load(f)
                model_id = model_dir.name
                models.append({
                    "model_id": model_id,
                    "model_dir": str(model_dir),
                    "framework": meta.get("framework", "unknown"),
                    "feature_count": len(meta.get("feature_columns") or meta.get("features", [])),
                    "target_horizon_days": meta.get("target_horizon_days", 1),
                    "metrics": meta.get("metrics", {}),
                    "type": "user",
                })
            except Exception:
                continue

    # Production models
    prod_root = Path(MODELS_PRODUCTION)
    if prod_root.exists():
        for meta_file in prod_root.rglob("metadata.json"):
            model_dir = meta_file.parent
            model_id = model_dir.name
            if any(m["model_id"] == model_id for m in models):
                continue
            try:
                with open(meta_file, encoding="utf-8") as f:
                    meta = json.load(f)
                models.append({
                    "model_id": model_id,
                    "model_dir": str(model_dir),
                    "framework": meta.get("framework", "unknown"),
                    "feature_count": len(meta.get("feature_columns") or meta.get("features", [])),
                    "target_horizon_days": meta.get("target_horizon_days", 1),
                    "metrics": meta.get("metrics", {}),
                    "type": "production",
                })
            except Exception:
                continue

    return {"status": "success", "models": models, "count": len(models)}


@router.get("/backtest/history/{model_id}", summary="获取模型回测历史")
async def get_backtest_history(
    model_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    """返回指定模型的回测历史记录列表（最新在前）。"""
    from backend.services.engine.inference.backtest_service import BacktestService
    svc = BacktestService()
    records = svc.list_history(model_id, limit=limit)
    return {"status": "success", "records": records, "count": len(records)}


@router.get("/backtest/history/{model_id}/{run_id}", summary="获取回测详情")
async def get_backtest_detail(
    model_id: str,
    run_id: str,
    current_user: dict = Depends(require_admin),
):
    """返回指定回测运行的完整详情（含逐日数据）。"""
    from backend.services.engine.inference.backtest_service import BacktestService
    svc = BacktestService()
    detail = svc.get_history_detail(model_id, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"回测记录 {run_id} 未找到")
    return detail


@router.delete("/backtest/history/{model_id}/{run_id}", summary="删除回测记录")
async def delete_backtest_history(
    model_id: str,
    run_id: str,
    current_user: dict = Depends(require_admin),
):
    """删除指定回测记录。"""
    from backend.services.engine.inference.backtest_service import BacktestService
    svc = BacktestService()
    deleted = svc.delete_history(model_id, run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"回测记录 {run_id} 未找到")
    return {"status": "ok", "deleted": run_id}
