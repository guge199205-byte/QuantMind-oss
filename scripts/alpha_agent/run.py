"""AlphaAgent factor evolution runner script.

Invoked by the launcher as a subprocess. Runs AlphaAgent's factor mining
loop, extracts discovered factors from pickle output, and persists them
to the QuantMind database.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import re
import sys
import time
from pathlib import Path

# Ensure QuantMind project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alpha_agent_run")


# ======================================================================
# Factor discovery from AlphaAgent pickle output
# ======================================================================


def discover_factors_from_logs(log_dir: str, task_id: str) -> list[dict]:
    """Extract factors from AlphaAgent's pickle-based log output.

    AlphaAgent stores results in pickle files:
    - ``experiment generation/**/*.pkl`` → FactorTask objects (name, formulation, description)
    - ``coder result/**/*.pkl`` → FactorFBWorkspace objects (file_dict with factor.py code)
    - ``summarized_cycle_feedback/**/*.pkl`` → Text feedback (IC and performance metrics)
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        logger.warning("日志目录不存在: %s", log_dir)
        return []

    pkl_count = len(list(log_path.glob("**/*.pkl")))
    logger.info("  扫描日志目录: %s (共 %d 个 pkl 文件)", log_dir, pkl_count)

    # ── 1. Extract FactorTask metadata ──
    logger.info("  [1/3] 提取因子元数据 (experiment generation)...")
    factor_meta: dict[str, dict] = {}
    for pkl_path in sorted(log_path.glob("**/experiment generation/**/*.pkl")):
        try:
            with open(pkl_path, "rb") as f:
                tasks = pickle.load(f)
            if not isinstance(tasks, list):
                tasks = [tasks]
            for t in tasks:
                name = getattr(t, "factor_name", None) or getattr(t, "name", None)
                if not name:
                    continue
                factor_meta[name] = {
                    "name": name,
                    "formulation": getattr(t, "factor_formulation", "") or "",
                    "description": getattr(t, "description", "") or "",
                    "category": getattr(t, "category", "") or "",
                }
        except Exception as e:
            logger.debug("Failed to read %s: %s", pkl_path, e)

    logger.info("    发现 %d 个因子元数据", len(factor_meta))

    # ── 2. Extract CodedFactor code ──
    logger.info("  [2/3] 提取因子代码 (coder result)...")
    factor_code: dict[str, str] = {}
    for pkl_path in sorted(log_path.glob("**/coder result/**/*.pkl")):
        try:
            with open(pkl_path, "rb") as f:
                workspaces = pickle.load(f)
            if not isinstance(workspaces, list):
                workspaces = [workspaces]
            for ws in workspaces:
                file_dict = getattr(ws, "file_dict", None) or {}
                code = file_dict.get("factor.py", "")
                if not code:
                    for v in file_dict.values():
                        if isinstance(v, str) and "def " in v and "alpha" in v.lower():
                            code = v
                            break
                if code:
                    fn_match = re.search(r"def\s+(\w+)\s*\(", code)
                    fname = fn_match.group(1) if fn_match else f"factor_{len(factor_code)}"
                    factor_code[fname] = code
        except Exception as e:
            logger.debug("Failed to read coder result %s: %s", pkl_path, e)

    logger.info("    发现 %d 个因子代码", len(factor_code))

    # ── 3. Extract feedback summary (IC metrics) ──
    logger.info("  [3/3] 提取反馈摘要 (summarized_cycle_feedback)...")
    feedback_text = ""
    for pkl_path in sorted(log_path.glob("**/summarized_cycle_feedback/**/*.pkl")):
        try:
            with open(pkl_path, "rb") as f:
                fb = pickle.load(f)
            if isinstance(fb, str):
                feedback_text += fb + "\n"
            elif isinstance(fb, (list, tuple)):
                for item in fb:
                    if isinstance(item, str):
                        feedback_text += item + "\n"
        except Exception as e:
            logger.debug("Failed to read feedback %s: %s", pkl_path, e)

    # ── 4. Merge results ──
    factors: list[dict] = []
    all_names = set(factor_meta.keys()) | set(factor_code.keys())
    for name in sorted(all_names):
        meta = factor_meta.get(name, {})
        code = factor_code.get(name, "")
        if not meta and name in factor_code:
            meta = {"name": name, "formulation": "", "description": ""}

        factors.append({
            "name": meta.get("name", name),
            "formulation": meta.get("formulation", ""),
            "description": meta.get("description", ""),
            "category": meta.get("category", ""),
            "code": code,
            "task_id": task_id,
            "feedback": feedback_text[:5000] if feedback_text else "",
        })

    if feedback_text:
        logger.info("    反馈摘要: %s", feedback_text[:200].replace("\n", " "))

    if not factors:
        logger.warning(
            "未发现因子! pkl 文件: %d, 元数据: %d, 代码: %d",
            len(list(log_path.glob("**/*.pkl"))),
            len(factor_meta),
            len(factor_code),
        )
    else:
        logger.info("  合并结果: %d 个因子 (元数据 %d + 代码 %d)",
                     len(factors), len(factor_meta), len(factor_code))

    return factors


# ======================================================================
# Factor persistence
# ======================================================================


async def persist_factors(factors: list[dict], task_id: str) -> int:
    """Persist discovered factors to the QuantMind database."""
    if not factors:
        return 0

    import hashlib
    from backend.services.engine.qlib_app.services.rd_agent_persistence import (
        RDAgentFactorPersistence,
    )

    persistence = RDAgentFactorPersistence()
    await persistence.ensure_tables()

    count = 0
    for f in factors:
        try:
            # 生成稳定的 factor_id（基于 name + task_id），避免重复插入
            raw_id = f"{task_id}:{f['name']}"
            factor_id = hashlib.md5(raw_id.encode()).hexdigest()

            # 将 formulation（Qlib 表达式）存入 metadata
            metadata = {
                "source": "alpha_agent",
                "task_id": task_id,
                "category": f.get("category", "alpha_agent"),
            }
            if f.get("formulation"):
                metadata["formulation"] = f["formulation"]
            if f.get("description"):
                metadata["description"] = f["description"]
            if f.get("feedback"):
                metadata["feedback"] = f["feedback"][:2000]

            await persistence.save_factor(
                factor_id=factor_id,
                factor_name=f["name"],
                factor_code=f.get("code", ""),
                user_id=f.get("user_id", "alpha_agent"),
                metadata=metadata,
            )
            count += 1
            logger.info("Persisted factor: %s (id=%s)", f["name"], factor_id)
        except Exception as e:
            logger.warning("Failed to persist factor %s: %s", f["name"], e)

    return count


# ======================================================================
# Main
# ======================================================================


def main():
    parser = argparse.ArgumentParser(description="QuantMind AlphaAgent Runner")
    parser.add_argument("--task-id", required=True, help="Task ID for tracking")
    parser.add_argument("--user-id", required=True, help="User ID")
    parser.add_argument("--seed", default="", help="Path to seed/factor data template")
    parser.add_argument("--loop-n", type=int, default=3, help="Number of evolution loops")
    parser.add_argument("--provider-uri", default="", help="Qlib data provider URI")
    parser.add_argument("--log-dir", default="", help="Log output directory")
    parser.add_argument("--direction", default="", help="Initial hypothesis/direction for factor mining")

    args = parser.parse_args()
    log_dir = args.log_dir or os.getenv("LOG_TRACE_PATH", "/tmp/alpha_agent_logs")

    logger.info("AlphaAgent runner starting: task_id=%s, user=%s, loops=%d", args.task_id, args.user_id, args.loop_n)
    logger.info("Log dir: %s", log_dir)
    logger.info("Provider URI: %s", args.provider_uri)

    try:
        # ── Configure AlphaAgent environment ──
        os.environ["LOG_TRACE_PATH"] = log_dir
        if args.provider_uri:
            os.environ["QLIB_PROVIDER_URI"] = args.provider_uri

        logger.info("[Phase 1/4] 配置环境变量...")
        logger.info("  LOG_TRACE_PATH=%s", log_dir)
        logger.info("  QLIB_PROVIDER_URI=%s", args.provider_uri)
        logger.info("  OPENAI_BASE_URL=%s", os.getenv("OPENAI_BASE_URL", "(未设置)"))
        logger.info("  CHAT_MODEL=%s", os.getenv("CHAT_MODEL", "(未设置)"))

        # ── Set up data directory for factor execution ──
        logger.info("[Phase 2/4] 设置因子数据目录...")
        _setup_factor_data(args.seed, log_dir)

        # ── Run AlphaAgent factor mining ──
        logger.info("[Phase 3/4] 开始因子挖掘 (共 %d 轮)...", args.loop_n)
        _run_factor_mining(
            loop_n=args.loop_n,
            direction=args.direction,
        )

        # ── Discover and persist factors ──
        logger.info("[Phase 4/4] 提取并持久化因子...")
        factors = discover_factors_from_logs(log_dir, args.task_id)
        logger.info("  从日志中发现 %d 个因子", len(factors))
        for i, f in enumerate(factors, 1):
            logger.info("  因子 %d: %s (表达式: %s)", i, f["name"],
                         f.get("formulation", "N/A")[:80] if f.get("formulation") else "无")

        # Add user_id to factor data
        for f in factors:
            f["user_id"] = args.user_id

        # Persist factors (sync wrapper for async)
        import asyncio
        count = asyncio.run(persist_factors(factors, args.task_id))
        logger.info("  成功持久化 %d 个因子到数据库", count)

        logger.info("=" * 60)
        logger.info("AlphaAgent 任务完成! task_id=%s", args.task_id)
        logger.info("  发现因子: %d", len(factors))
        logger.info("  持久化因子: %d", count)
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("AlphaAgent runner failed: %s", e)
        sys.exit(1)


def _setup_factor_data(seed_path: str, log_dir: str) -> None:
    """Set up factor data files so AlphaAgent's factor code can find daily_pv.h5."""
    work_dir = Path(log_dir)
    data_dir = work_dir / "git_ignore_folder" / "factor_implementation_source_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    target = data_dir / "daily_pv.h5"
    if target.exists():
        logger.info("daily_pv.h5 already exists at %s", target)
        return

    # Try to copy from seed path
    if seed_path:
        seed = Path(seed_path)
        for candidate in [
            seed / "daily_pv_all.h5",
            seed / "daily_pv.h5",
        ]:
            if candidate.exists():
                import shutil
                shutil.copy2(str(candidate), str(target))
                logger.info("Copied %s → %s", candidate, target)
                return

    # Fallback: try standard locations
    project = Path(_project_root)
    for candidate in [
        project / "alphaagent" / "scenarios" / "qlib" / "experiment" / "factor_data_template" / "daily_pv_all.h5",
        project / "rd-agent" / "rdagent" / "scenarios" / "qlib" / "experiment" / "factor_data_template" / "daily_pv_all.h5",
    ]:
        if candidate.exists():
            import shutil
            shutil.copy2(str(candidate), str(target))
            logger.info("Copied %s → %s", candidate, target)
            return

    logger.warning("daily_pv.h5 not found — factor execution may fail")


def _run_factor_mining(*, loop_n: int, direction: str = "") -> None:
    """Run AlphaAgent's factor mining loop via its Python API."""
    from alphaagent.app.qlib_rd_loop.factor_mining import main as factor_mining_main
    from alphaagent.components.workflow.alphaagent_loop import AlphaAgentLoop
    from alphaagent.app.qlib_rd_loop.factor_mining import ALPHA_AGENT_FACTOR_PROP_SETTING

    # step_n is *step count*, not loop count.  One loop has 5 steps
    # (factor_propose → factor_construct → factor_calculate →
    #  factor_backtest → feedback).  Multiply loop_n by step count so
    # the user's "3 loops" request actually runs 3 full cycles.
    loop = AlphaAgentLoop(
        ALPHA_AGENT_FACTOR_PROP_SETTING,
        potential_direction=None,
        stop_event=None,
    )
    num_steps = len(loop.steps)
    total_steps = loop_n * num_steps

    # Log step names for visibility
    step_names = [getattr(s, '__name__', getattr(s, '__class__', type(s)).__name__) for s in loop.steps]
    logger.info("=" * 60)
    logger.info("AlphaAgent 因子挖掘配置:")
    logger.info("  轮数: %d", loop_n)
    logger.info("  每轮步骤数: %d", num_steps)
    logger.info("  总步骤数: %d", total_steps)
    logger.info("  步骤流程: %s", " → ".join(step_names))
    logger.info("  挖掘方向: %s", direction or "(默认)")
    logger.info("=" * 60)

    # Monkey-patch the loop's run_step to add per-step logging
    _original_run_step = loop.run_step if hasattr(loop, 'run_step') else None

    step_counter = {"n": 0, "loop": 0}

    def _logged_run_step(step, *args, **kwargs):
        step_counter["n"] += 1
        step_name = getattr(step, '__name__', getattr(step, '__class__', type(step)).__name__)
        current_loop = (step_counter["n"] - 1) // num_steps + 1
        step_in_loop = (step_counter["n"] - 1) % num_steps + 1
        logger.info("─" * 50)
        logger.info("▶ 步骤 %d/%d (轮次 %d/%d): %s",
                     step_in_loop, num_steps, current_loop, loop_n, step_name)
        t0 = time.time()
        try:
            result = _original_run_step(step, *args, **kwargs)
            elapsed = time.time() - t0
            logger.info("✓ 步骤 %s 完成 (%.1f 秒)", step_name, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("✗ 步骤 %s 失败 (%.1f 秒): %s", step_name, elapsed, e)
            raise

    if _original_run_step:
        loop.run_step = _logged_run_step

    logger.info("开始执行因子挖掘...")
    t_start = time.time()

    factor_mining_main(step_n=total_steps, direction=direction or None)

    elapsed_total = time.time() - t_start
    logger.info("=" * 60)
    logger.info("因子挖掘执行完成! 总耗时: %.1f 秒 (%.1f 分钟)", elapsed_total, elapsed_total / 60)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
