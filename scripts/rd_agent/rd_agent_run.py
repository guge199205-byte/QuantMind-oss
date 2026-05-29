#!/usr/bin/env python3
"""RD-Agent thin wrapper — 给 quantbot launcher 调用

设计：
- 该脚本可在主 quantmind 容器内运行，也可作为独立 quantmind-rdagent 镜像入口
- 接受 seed.py、loop_n、task_id、user_id、provider_uri，统一注入 qlib 配置
- 调用 rdagent.app.qlib_rd_loop.factor.main(...) 跑演化循环
- 结束后扫描 rdagent log 目录，把每个候选因子写回 rd_agent_factors 表，
  metadata_json.task_id 标记本次任务，方便 launcher._collect_results 精准过滤

环境变量优先 (容器化场景)：
  RD_AGENT_TASK_ID
  RD_AGENT_USER_ID
  RD_AGENT_SEED_PATH
  RD_AGENT_LOOP_N
  QLIB_PROVIDER_URI
  OPENAI_API_KEY
  DATABASE_URL
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rd_agent_run")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QuantMind RD-Agent runner")
    p.add_argument("--seed", default=os.getenv("RD_AGENT_SEED_PATH"))
    p.add_argument("--loop-n", type=int, default=int(os.getenv("RD_AGENT_LOOP_N", "3")))
    p.add_argument("--task-id", default=os.getenv("RD_AGENT_TASK_ID") or f"task_{uuid.uuid4().hex[:12]}")
    p.add_argument("--user-id", default=os.getenv("RD_AGENT_USER_ID", "system"))
    p.add_argument("--provider-uri", default=os.getenv("QLIB_PROVIDER_URI", "/app/db/qlib_data/cn_data"))
    p.add_argument("--log-dir", default=os.getenv("RD_AGENT_LOG_DIR", "/tmp/rdagent_logs"))
    p.add_argument("--dry-run", action="store_true", help="只校验环境，不真正调用 rdagent")
    return p.parse_args()


def configure_qlib_env(args: argparse.Namespace) -> None:
    """注入 Qlib + rdagent 必要的环境变量"""
    os.environ.setdefault("QLIB_PROVIDER_URI", args.provider_uri)
    os.environ.setdefault("QLIB_CONFIG_PATH", "")
    # rdagent 内部使用 dotenv，相关参数走 ENV 覆盖
    os.environ.setdefault("LOG_TRACE_PATH", args.log_dir)
    os.environ.setdefault("QLIB_LOCAL_DATA_PATH", args.provider_uri)
    Path(args.log_dir).mkdir(parents=True, exist_ok=True)


async def persist_factors(task_id: str, user_id: str, factors: list[dict]) -> int:
    """把候选因子写入 rd_agent_factors 表"""
    # 延迟导入，避免脚本独立运行时强制依赖 quantmind backend
    try:
        from backend.services.engine.qlib_app.services.rd_agent_persistence import (
            RDAgentFactorPersistence,
        )
    except ImportError as exc:
        logger.warning(
            "无法导入 RDAgentFactorPersistence (%s)，跳过 PG 写入；"
            "请确保 PYTHONPATH=/app 且 backend 代码已挂载",
            exc,
        )
        return 0

    persistence = RDAgentFactorPersistence()
    saved = 0
    for f in factors:
        try:
            await persistence.save_factor(
                factor_id=f["factor_id"],
                factor_name=f.get("factor_name") or f["factor_id"],
                factor_code=f.get("factor_code", ""),
                user_id=user_id,
                metadata={
                    "task_id": task_id,
                    "loop_iteration": f.get("loop_iteration"),
                    "ic": f.get("ic"),
                    "ir": f.get("ir"),
                    "log_path": f.get("log_path"),
                },
            )
            saved += 1
        except Exception as exc:
            logger.error("save_factor 失败 factor_id=%s: %s", f.get("factor_id"), exc)
    return saved


def discover_factors_from_logs(log_dir: str, task_id: str) -> list[dict]:
    """从 rdagent log 目录扫描候选因子。

    rdagent FactorRDLoop 会把每轮结果写到 $LOG_TRACE_PATH/__session__/<sid>/<step>/<class>.pkl
    或在 mlflow 里。我们这里采用最简策略：扫 .py / factor.json 抽取代码片段。
    实际产物结构因 rdagent 版本而异，所以采用宽松扫描。
    """
    root = Path(log_dir)
    factors: list[dict] = []
    if not root.exists():
        return factors

    # 扫描所有 factor.py / factor.json / factor_code.txt
    candidates = []
    for pattern in ("**/factor.py", "**/factor.json", "**/factor_code.*", "**/*.py"):
        for p in root.glob(pattern):
            if p.is_file() and p.stat().st_size > 0 and p.stat().st_size < 64_000:
                candidates.append(p)

    # 去重保留前 20 个
    seen: set[str] = set()
    for p in candidates[:200]:
        try:
            code = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        digest = code[:200]
        if digest in seen:
            continue
        seen.add(digest)

        factor_id = f"{task_id}_{p.parent.name}_{p.stem}_{len(factors):03d}"
        factors.append({
            "factor_id": factor_id,
            "factor_name": p.stem,
            "factor_code": code,
            "loop_iteration": p.parent.name,
            "log_path": str(p),
        })
        if len(factors) >= 20:
            break

    return factors


async def main_async() -> int:
    args = parse_args()
    logger.info("RD-Agent runner start task_id=%s user=%s loop_n=%s seed=%s",
                args.task_id, args.user_id, args.loop_n, args.seed)

    configure_qlib_env(args)

    if args.dry_run:
        logger.info("dry-run 模式，仅校验环境变量")
        logger.info("env=%s", {k: os.environ.get(k) for k in (
            "QLIB_PROVIDER_URI", "LOG_TRACE_PATH", "OPENAI_API_KEY", "PYTHONPATH"
        )})
        return 0

    seed_path = args.seed
    if seed_path and not Path(seed_path).exists():
        logger.error("seed 文件不存在: %s", seed_path)
        return 2

    # 调用 rdagent
    try:
        from rdagent.app.qlib_rd_loop.factor import main as rdagent_main
    except ImportError as exc:
        logger.error("rdagent 未安装: %s", exc)
        return 3

    try:
        # rdagent_main 内部用 asyncio.run()，不能在已有 event loop 中直接调用
        # 放进 executor 里在独立线程跑（线程内可自由 asyncio.run）
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: rdagent_main(
                loop_n=args.loop_n,
                base_features_path=seed_path,
                checkout_path=args.log_dir,
            ),
        )
    except SystemExit as e:
        logger.info("rdagent 主函数 SystemExit(%s)，视为正常终止", e.code)
    except Exception as exc:
        logger.error("rdagent 主函数异常: %s\n%s", exc, traceback.format_exc())
        # 不直接 return — 仍尝试从 log_dir 抓已生成的因子

    # 收集结果
    factors = discover_factors_from_logs(args.log_dir, args.task_id)
    logger.info("从 %s 扫描到 %d 个候选因子", args.log_dir, len(factors))

    saved = await persist_factors(args.task_id, args.user_id, factors)
    logger.info("写入 rd_agent_factors %d 条 (task_id=%s)", saved, args.task_id)

    # 标准输出 JSON 供 launcher 解析
    print("\n=== RD_AGENT_RESULT_JSON ===")
    print(json.dumps({
        "task_id": args.task_id,
        "factors_generated": len(factors),
        "factors_persisted": saved,
        "log_dir": args.log_dir,
    }, ensure_ascii=False))

    return 0 if saved >= 0 else 4


def main() -> None:
    try:
        sys.exit(asyncio.run(main_async()))
    except KeyboardInterrupt:
        logger.warning("被中断")
        sys.exit(130)


if __name__ == "__main__":
    main()
