"""RD-Agent 多市场因子挖掘 runner 脚本

由 launcher 作为子进程调用。使用 RDLoopWrapper 运行 RD-Agent 因子挖掘，
提取发现的因子并持久化到 QuantMind 数据库。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rd_agent_run")


async def persist_factors(factors: list[dict], task_id: str, user_id: str, market: str) -> int:
    """持久化因子到数据库"""
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
            raw_id = f"{task_id}:{f['name']}"
            factor_id = hashlib.md5(raw_id.encode()).hexdigest()

            metadata = {
                "source": "rd_agent",
                "market": market,
                "task_id": task_id,
                "category": f.get("category", market),
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
                user_id=user_id,
                metadata=metadata,
            )
            count += 1
            logger.info("Persisted factor: %s (market=%s, id=%s)", f["name"], market, factor_id)
        except Exception as e:
            logger.warning("Failed to persist factor %s: %s", f["name"], e)

    return count


def compute_factor_ic(factor_code: str, data_path: str) -> dict:
    """执行因子代码并计算 IC 指标

    Returns dict with: ic, rank_ic, icir, rank_icir (or empty dict on failure)
    """
    import tempfile
    import subprocess
    import sys

    if not factor_code or not Path(data_path).exists():
        return {}

    # Create a temporary script that executes the factor code and computes IC
    script = f"""
import pandas as pd
import numpy as np
import sys, os, tempfile, traceback

os.chdir(tempfile.gettempdir())

try:
    # Execute factor code
    {factor_code}

    # Find the result H5 file
    result_files = [f for f in os.listdir('.') if f.endswith('.h5') and 'result' in f.lower()]
    if not result_files:
        # Try to find any .h5 file that's not the input
        result_files = [f for f in os.listdir('.') if f.endswith('.h5') and f != 'daily_pv.h5']

    if not result_files:
        print("NO_RESULT_FILE")
        sys.exit(1)

    factor_df = pd.read_hdf(result_files[0])
    if factor_df.empty:
        print("EMPTY_FACTOR")
        sys.exit(1)

    # Load price data for returns
    price_df = pd.read_hdf("{data_path}")
    if 'close' in price_df.columns.get_level_values(0):
        close = price_df['close']
    elif '$close' in price_df.columns.get_level_values(0):
        close = price_df['$close']
    else:
        close = price_df.iloc[:, 0]

    # Compute forward returns
    returns = close.groupby(level=1).pct_change().shift(-1)

    # Align factor and returns
    factor_values = factor_df.stack()
    factor_values.index.names = ['datetime', 'instrument']
    returns.index.names = ['datetime', 'instrument']

    common_idx = factor_values.index.intersection(returns.index)
    if len(common_idx) < 100:
        print("INSUFFICIENT_DATA")
        sys.exit(1)

    f = factor_values.loc[common_idx]
    r = returns.loc[common_idx]

    # Remove NaN and inf
    mask = np.isfinite(f) & np.isfinite(r)
    f = f[mask]
    r = r[mask]

    if len(f) < 100:
        print("INSUFFICIENT_CLEAN_DATA")
        sys.exit(1)

    # Compute IC (Spearman rank correlation)
    from scipy import stats
    ic_values = []
    for dt in f.index.get_level_values(0).unique():
        f_dt = f.loc[dt] if dt in f.index.get_level_values(0) else None
        r_dt = r.loc[dt] if dt in r.index.get_level_values(0) else None
        if f_dt is not None and r_dt is not None and len(f_dt) > 5:
            common = f_dt.index.intersection(r_dt.index)
            if len(common) > 5:
                corr, _ = stats.spearmanr(f_dt.loc[common], r_dt.loc[common])
                if np.isfinite(corr):
                    ic_values.append(corr)

    if not ic_values:
        print("NO_IC_VALUES")
        sys.exit(1)

    ic = np.mean(ic_values)
    rank_ic = np.median(ic_values)
    icir = np.mean(ic_values) / (np.std(ic_values) + 1e-8)
    rank_icir = rank_ic / (np.std(ic_values) + 1e-8)

    print(f"IC={{ic:.4f}}")
    print(f"RANK_IC={{rank_ic:.4f}}")
    print(f"ICIR={{icir:.4f}}")
    print(f"RANK_ICIR={{rank_icir:.4f}}")
    print(f"OBSERVATIONS={{len(f)}}")
    print(f"IC_DATES={{len(ic_values)}}")

except Exception as e:
    print(f"ERROR: {{e}}")
    traceback.print_exc()
    sys.exit(1)
"""

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
            f.write(script)
            script_path = f.name

        # Copy data file to /tmp for the script (factor code expects 'daily_pv.h5')
        import shutil
        tmp_data = '/tmp/daily_pv.h5'
        if not os.path.exists(tmp_data):
            shutil.copy2(data_path, tmp_data)
        elif os.path.getmtime(data_path) > os.path.getmtime(tmp_data):
            shutil.copy2(data_path, tmp_data)

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=120, cwd='/tmp'
        )

        os.unlink(script_path)

        output = result.stdout + result.stderr
        metrics = {}
        for line in output.strip().split('\n'):
            if line.startswith('IC='):
                metrics['ic'] = float(line.split('=')[1])
            elif line.startswith('RANK_IC='):
                metrics['rank_ic'] = float(line.split('=')[1])
            elif line.startswith('ICIR='):
                metrics['icir'] = float(line.split('=')[1])
            elif line.startswith('RANK_ICIR='):
                metrics['rank_icir'] = float(line.split('=')[1])

        return metrics

    except Exception as e:
        logger.warning("IC computation failed: %s", e)
        return {}


def main():
    parser = argparse.ArgumentParser(description="QuantMind RD-Agent Multi-Market Runner")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--market", default="a_share", help="Market: a_share, crypto, hong_kong, us_stock")
    parser.add_argument("--loop-n", type=int, default=3)
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--direction", default="")
    args = parser.parse_args()

    log_dir = args.log_dir or os.getenv("LOG_TRACE_PATH", "/tmp/rd_agent_logs")
    log_dir = str(Path(log_dir).resolve())
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("RD-Agent Runner starting")
    logger.info("  Task ID: %s", args.task_id)
    logger.info("  User ID: %s", args.user_id)
    logger.info("  Market:  %s", args.market)
    logger.info("  Loops:   %d", args.loop_n)
    logger.info("  Log dir: %s", log_dir)
    logger.info("  Direction: %s", args.direction or "(default)")
    logger.info("=" * 60)

    try:
        os.environ["LOG_TRACE_PATH"] = log_dir

        from backend.services.engine.rd_agent.rd_loop_wrapper import RDLoopWrapper

        wrapper = RDLoopWrapper(market=args.market)
        logger.info("[%s] Market adapter: %s (%s)", args.market, wrapper.market_name, args.market)

        t0 = time.time()
        result = asyncio.run(wrapper.run(
            loop_n=args.loop_n,
            task_log_dir=log_dir,
            direction=args.direction,
        ))
        elapsed = time.time() - t0

        factors = result.get("factors", [])
        logger.info("Factor mining completed in %.1fs, found %d factors", elapsed, len(factors))

        for i, f in enumerate(factors, 1):
            logger.info("  Factor %d: %s (expr: %s)", i, f["name"],
                         f.get("formulation", "")[:80] or "N/A")

        # Persist
        count = asyncio.run(persist_factors(factors, args.task_id, args.user_id, args.market))
        logger.info("Persisted %d factors to database", count)

        # Compute IC metrics for persisted factors
        data_path = "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_all.h5"
        if Path(data_path).exists():
            logger.info("Computing IC metrics for %d factors...", len(factors))
            from backend.services.engine.qlib_app.services.rd_agent_persistence import RDAgentFactorPersistence
            persistence = RDAgentFactorPersistence()

            async def update_metrics():
                for f in factors:
                    code = f.get("code", "")
                    if not code:
                        continue
                    try:
                        import hashlib
                        raw_id = f"{args.task_id}:{f['name']}"
                        factor_id = hashlib.md5(raw_id.encode()).hexdigest()

                        metrics = compute_factor_ic(code, data_path)
                        if metrics:
                            ic = metrics.get("ic", 0)
                            await persistence.update_factor_metrics(
                                factor_id=factor_id,
                                ic_value=ic,
                                status="completed",
                                metadata={
                                    "rank_ic": metrics.get("rank_ic", 0),
                                    "icir": metrics.get("icir", 0),
                                    "rank_icir": metrics.get("rank_icir", 0),
                                },
                            )
                            logger.info("  %s: IC=%.4f, RankIC=%.4f, ICIR=%.4f",
                                        f["name"], ic, metrics.get("rank_ic", 0), metrics.get("icir", 0))
                        else:
                            logger.info("  %s: IC computation skipped (no code or data)", f["name"])
                    except Exception as e:
                        logger.warning("  %s: IC computation failed: %s", f["name"], e)

            asyncio.run(update_metrics())

        # Write result JSON for launcher to read
        result_file = Path(log_dir) / "result.json"
        result_file.write_text(json.dumps({
            "task_id": args.task_id,
            "market": args.market,
            "total_factors": len(factors),
            "persisted_factors": count,
            "elapsed_seconds": elapsed,
        }, indent=2))

        logger.info("=" * 60)
        logger.info("RD-Agent task complete! task_id=%s, market=%s", args.task_id, args.market)
        logger.info("  Found: %d factors, Persisted: %d", len(factors), count)
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("RD-Agent runner failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
