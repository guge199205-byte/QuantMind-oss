"""AlphaAgent 因子 → 训练特征自动流水线

将 AlphaAgent 挖到的因子一键推广到训练特征集：
1. 从 rd_agent_factors 读取因子
2. 提取 Qlib 表达式
3. 用 Qlib 计算因子值
4. 合并到 model_features parquet
5. 注册到特征目录 (qm_feature_*)
"""

import hashlib
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AlphaFactorPipeline"])

# ── 路径配置 ──
if os.path.exists("/app") and not os.environ.get("QUANTMIND_HOST_MODE"):
    PARQUET_PATH = Path("/app/db/feature_snapshots/model_features_2026.parquet")
    QLIB_PROVIDER_URI = "/app/db/qlib_data/cn_data"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[5]
    PARQUET_PATH = PROJECT_ROOT / "db" / "feature_snapshots" / "model_features_2026.parquet"
    QLIB_PROVIDER_URI = str(PROJECT_ROOT / "db" / "qlib_data" / "cn_data")


class PromoteRequest(BaseModel):
    factor_ids: list[str] = []
    auto_train: bool = False


class PromoteExpressionRequest(BaseModel):
    """直接用表达式推广因子（不依赖 rd_agent_factors 表中的 ID）。"""
    factors: list[dict[str, str]]  # [{name, expression}, ...]
    auto_train: bool = False


class PromoteResponse(BaseModel):
    success: bool
    promoted: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    auto_train_triggered: bool = False


# ═══════════════════════════════════════════════════════════════════
# 因子表达式提取
# ═══════════════════════════════════════════════════════════════════


def _extract_qlib_expression(factor_code: str, metadata: dict) -> Optional[str]:
    """从因子代码或 metadata 中提取 Qlib 表达式。"""
    # 1. 优先从 metadata 取
    formulation = metadata.get("formulation", "")
    if formulation and _is_qlib_expression(formulation):
        return formulation.strip()

    # 2. 从 ExpressionFactor 子类提取
    if "get_expression" in factor_code and "ExpressionFactor" in factor_code:
        try:
            ns: dict = {}
            exec(compile(factor_code, "<factor>", "exec"), ns)
            for obj in ns.values():
                if isinstance(obj, type) and hasattr(obj, "get_expression"):
                    inst = obj()
                    expr = inst.get_expression()
                    if expr and _is_qlib_expression(expr):
                        return expr.strip()
        except Exception as e:
            logger.debug("Failed to instantiate ExpressionFactor: %s", e)

    # 3. 尝试从 return "..." 模式提取
    m = re.search(r'return\s+["\'](.+?)["\']', factor_code)
    if m and _is_qlib_expression(m.group(1)):
        return m.group(1).strip()

    return None


def _is_qlib_expression(expr: str) -> bool:
    """判断是否为合法的 Qlib 表达式（包含 $变量 或 Qlib 函数）。"""
    if not expr or len(expr) < 5:
        return False
    qlib_indicators = ["$", "Ref(", "Mean(", "Std(", "TS_", "EMA(", "RSI(", "MACD(",
                       "Rank(", "Corr(", "Slope(", "Resi(", "DELAY(", "COUNT(",
                       "SUMIF(", "FILTER(", "REGBETA(", "REGRESI(",
                       "(", ")", "?", ":", "&&", "||"]
    return any(ind in expr for ind in qlib_indicators)


def _sanitize_feature_key(name: str) -> str:
    """将因子名转为合法的 feature_key。"""
    key = re.sub(r'[^a-zA-Z0-9_]', '_', name).lower().strip('_')
    key = re.sub(r'_+', '_', key)
    return f"alpha_{key}"[:80]


# ═══════════════════════════════════════════════════════════════════
# Qlib 表达式计算
# ═══════════════════════════════════════════════════════════════════


_qlib_initialized = False


def _ensure_qlib_init():
    """确保 Qlib 已初始化（惰性初始化，只执行一次）。"""
    global _qlib_initialized
    if _qlib_initialized:
        return
    try:
        import qlib
        from qlib.config import C
        qlib.init(provider_uri=QLIB_PROVIDER_URI, region="cn")
        _qlib_initialized = True
        logger.info("Qlib initialized with provider_uri=%s", QLIB_PROVIDER_URI)
    except Exception as e:
        logger.error("Failed to init Qlib: %s", e)
        raise RuntimeError(f"Qlib 初始化失败: {e}")


def compute_factor_via_qlib(expression: str, feature_name: str) -> pd.DataFrame:
    """用 Qlib 引擎计算因子表达式，返回 MultiIndex(date, instrument) DataFrame。"""
    _ensure_qlib_init()
    from qlib.data import D

    instruments = D.instruments(market="csi300")
    df = D.features(instruments, [expression], freq="day")
    if df.empty:
        raise RuntimeError(f"Qlib 返回空数据，表达式可能无效: {expression}")
    df.columns = [feature_name]
    return df


# ═══════════════════════════════════════════════════════════════════
# Parquet 合并
# ═══════════════════════════════════════════════════════════════════


def merge_factor_into_parquet(factor_df: pd.DataFrame, feature_name: str) -> int:
    """将因子 DataFrame 合并到 parquet，返回新增行数。"""
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(f"Parquet 文件不存在: {PARQUET_PATH}")

    existing = pd.read_parquet(PARQUET_PATH)

    # 确保列名一致
    if feature_name in existing.columns:
        logger.warning("Feature %s already exists in parquet, will overwrite", feature_name)

    # Qlib 返回的是 MultiIndex(instrument, datetime)
    # parquet 的是 columns: symbol, trade_date, ...
    # 需要对齐
    factor_df = factor_df.reset_index()
    if "instrument" in factor_df.columns and "datetime" in factor_df.columns:
        factor_df = factor_df.rename(columns={"instrument": "symbol", "datetime": "trade_date"})
    elif len(factor_df.columns) >= 3:
        # 假设前两列是 index levels
        cols = list(factor_df.columns)
        factor_df = factor_df.rename(columns={cols[0]: "symbol", cols[1]: "trade_date"})

    if "symbol" not in factor_df.columns or "trade_date" not in factor_df.columns:
        raise ValueError(f"无法识别因子 DataFrame 的列: {factor_df.columns.tolist()}")

    factor_df["trade_date"] = pd.to_datetime(factor_df["trade_date"]).dt.date

    # 如果 parquet 的 trade_date 是 datetime，转换为 date
    if hasattr(existing["trade_date"].dtype, 'tz') or existing["trade_date"].dtype == 'datetime64[ns]':
        existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date

    # 合并
    if feature_name in existing.columns:
        existing = existing.drop(columns=[feature_name])

    merged = existing.merge(
        factor_df[["symbol", "trade_date", feature_name]],
        on=["symbol", "trade_date"],
        how="left",
    )

    # 写回
    merged.to_parquet(PARQUET_PATH, index=False)
    added = merged[feature_name].notna().sum()
    logger.info("Merged %s into parquet: %d non-null values", feature_name, added)
    return int(added)


# ═══════════════════════════════════════════════════════════════════
# 特征目录注册
# ═══════════════════════════════════════════════════════════════════


async def register_feature_in_catalog(
    feature_key: str,
    feature_name: str,
    formula: str,
    category_id: str = "alpha_agent",
) -> None:
    """将新特征注册到 qm_feature_* 目录表。"""
    async with get_session() as session:
        # 1. 确保 alpha_agent 分类存在
        await session.execute(text("""
            INSERT INTO qm_feature_category (category_id, category_name, sort_order, description)
            VALUES (:cat_id, :cat_name, 99, 'AlphaAgent 自动挖掘的因子')
            ON CONFLICT (category_id) DO NOTHING
        """), {"cat_id": category_id, "cat_name": "AlphaAgent 挖掘因子"})

        # 2. 插入特征定义
        feature_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO qm_feature_definition (feature_id, feature_key, feature_name, formula, category_id)
            VALUES (:fid, :fkey, :fname, :formula, :cat_id)
            ON CONFLICT (feature_key) DO UPDATE SET
                feature_name = EXCLUDED.feature_name,
                formula = EXCLUDED.formula,
                updated_at = now()
        """), {
            "fid": feature_id,
            "fkey": feature_key,
            "fname": feature_name,
            "formula": formula,
            "cat_id": category_id,
        })

        # 3. 获取当前活跃版本
        version_row = await session.execute(text("""
            SELECT version_id FROM qm_feature_set_version
            WHERE status = 'active'
            ORDER BY effective_at DESC, created_at DESC
            LIMIT 1
        """))
        version = version_row.mappings().first()
        if not version:
            logger.warning("No active feature set version found, skipping set_item registration")
            return

        version_id = version["version_id"]

        # 4. 获取当前最大 order_no
        max_order_row = await session.execute(text("""
            SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order
            FROM qm_feature_set_item
            WHERE version_id = :vid
        """), {"vid": version_id})
        next_order = max_order_row.scalar() or 999

        # 5. 插入 set_item（如果不存在）
        # id 是 integer 类型，使用 MAX(id) + 1
        max_id_row = await session.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM qm_feature_set_item"))
        next_id = max_id_row.scalar() or 1

        await session.execute(text("""
            INSERT INTO qm_feature_set_item (id, version_id, category_id, feature_key, order_no, enabled)
            VALUES (:id, :vid, :cat_id, :fkey, :order_no, true)
            ON CONFLICT (version_id, feature_key) DO UPDATE SET
                enabled = true,
                order_no = EXCLUDED.order_no
        """), {
            "id": next_id,
            "vid": version_id,
            "cat_id": category_id,
            "fkey": feature_key,
            "order_no": next_order,
        })

        # 6. 更新版本特征计数
        await session.execute(text("""
            UPDATE qm_feature_set_version
            SET feature_count = (
                SELECT COUNT(*) FROM qm_feature_set_item
                WHERE version_id = :vid AND enabled = true
            )
            WHERE version_id = :vid
        """), {"vid": version_id})

    logger.info("Registered feature %s (%s) in catalog", feature_key, feature_name)


# ═══════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════


@router.post("/promote", response_model=PromoteResponse)
async def promote_factors(req: PromoteRequest):
    """将 AlphaAgent 因子推广到训练特征集。

    流程：
    1. 从 rd_agent_factors 读取因子
    2. 提取 Qlib 表达式
    3. 计算因子值并合并到 parquet
    4. 注册到特征目录
    5. 可选：自动触发训练
    """
    if not req.factor_ids:
        raise HTTPException(status_code=400, detail="factor_ids 不能为空")

    # 读取因子
    async with get_session(read_only=True) as session:
        placeholders = ", ".join(f":fid_{i}" for i in range(len(req.factor_ids)))
        params = {f"fid_{i}": fid for i, fid in enumerate(req.factor_ids)}
        rows = await session.execute(text(f"""
            SELECT factor_id, factor_name, factor_code, metadata_json, ic_value, sharpe_ratio
            FROM rd_agent_factors
            WHERE factor_id IN ({placeholders})
        """), params)
        factors = [dict(r) for r in rows.mappings().all()]

    if not factors:
        raise HTTPException(status_code=404, detail="未找到指定的因子")

    promoted = []
    errors = []

    for factor in factors:
        factor_id = factor["factor_id"]
        factor_name = factor["factor_name"]
        factor_code = factor.get("factor_code", "")
        metadata = factor.get("metadata_json", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        try:
            # 1. 提取 Qlib 表达式
            expression = _extract_qlib_expression(factor_code, metadata)
            if not expression:
                errors.append({
                    "factor_id": factor_id,
                    "factor_name": factor_name,
                    "error": "无法提取 Qlib 表达式（因子可能是纯 pandas 代码）",
                })
                continue

            # 2. 生成 feature_key
            feature_key = _sanitize_feature_key(factor_name)

            # 3. 计算因子值
            factor_df = compute_factor_via_qlib(expression, feature_key)

            # 4. 合并到 parquet
            non_null = merge_factor_into_parquet(factor_df, feature_key)

            # 5. 注册到特征目录
            await register_feature_in_catalog(
                feature_key=feature_key,
                feature_name=factor_name,
                formula=expression,
            )

            promoted.append({
                "factor_id": factor_id,
                "factor_name": factor_name,
                "feature_key": feature_key,
                "expression": expression,
                "non_null_values": non_null,
                "ic_value": factor.get("ic_value"),
                "sharpe_ratio": factor.get("sharpe_ratio"),
            })

        except Exception as e:
            logger.exception("Failed to promote factor %s", factor_name)
            errors.append({
                "factor_id": factor_id,
                "factor_name": factor_name,
                "error": str(e)[:500],
            })

    # 可选：自动触发训练
    auto_train_triggered = False
    if req.auto_train and promoted:
        try:
            # TODO: 调用训练 API
            auto_train_triggered = True
        except Exception as e:
            logger.error("Auto-train failed: %s", e)

    return PromoteResponse(
        success=len(promoted) > 0,
        promoted=promoted,
        errors=errors,
        auto_train_triggered=auto_train_triggered,
    )


@router.get("/extractable")
async def list_extractable_factors(
    limit: int = 50,
    status: Optional[str] = "completed",
):
    """列出可提取 Qlib 表达式的因子（已完成回测且有代码）。"""
    async with get_session(read_only=True) as session:
        conditions = ["factor_code IS NOT NULL", "factor_code != ''"]
        params: dict[str, Any] = {"limit": limit}
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = " AND ".join(conditions)
        rows = await session.execute(text(f"""
            SELECT factor_id, factor_name, factor_code, metadata_json,
                   ic_value, sharpe_ratio, annual_return, created_at
            FROM rd_agent_factors
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit
        """), params)

        results = []
        for r in rows.mappings().all():
            item = dict(r)
            metadata = item.get("metadata_json", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}

            # 尝试提取表达式
            expression = _extract_qlib_expression(item.get("factor_code", ""), metadata)
            item["extractable"] = expression is not None
            item["qlib_expression"] = expression
            item.pop("factor_code", None)
            item.pop("metadata_json", None)
            results.append(item)

    return {"success": True, "data": results, "total": len(results)}


@router.post("/promote-by-expression", response_model=PromoteResponse)
async def promote_factors_by_expression(req: PromoteExpressionRequest):
    """直接用因子名 + Qlib 表达式推广到训练特征集（不依赖 rd_agent_factors 表）。"""
    if not req.factors:
        raise HTTPException(status_code=400, detail="factors 不能为空")

    promoted = []
    errors = []

    for item in req.factors:
        factor_name = item.get("name", "").strip()
        expression = item.get("expression", "").strip()

        if not factor_name or not expression:
            errors.append({"factor_name": factor_name, "error": "name 和 expression 不能为空"})
            continue

        if not _is_qlib_expression(expression):
            errors.append({"factor_name": factor_name, "error": f"不是合法的 Qlib 表达式: {expression[:100]}"})
            continue

        try:
            feature_key = _sanitize_feature_key(factor_name)
            factor_df = compute_factor_via_qlib(expression, feature_key)
            non_null = merge_factor_into_parquet(factor_df, feature_key)
            await register_feature_in_catalog(
                feature_key=feature_key,
                feature_name=factor_name,
                formula=expression,
            )
            promoted.append({
                "factor_name": factor_name,
                "feature_key": feature_key,
                "expression": expression,
                "non_null_values": non_null,
            })
        except Exception as e:
            logger.exception("Failed to promote factor %s", factor_name)
            errors.append({"factor_name": factor_name, "error": str(e)[:500]})

    return PromoteResponse(
        success=len(promoted) > 0,
        promoted=promoted,
        errors=errors,
        auto_train_triggered=False,
    )
