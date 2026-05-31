"""补跑因子 IC 指标 v2 — 使用真实日收益率 (pct_change)

注意: daily_pv.h5 中的 $return 不是日收益率，需要用 $close.pct_change() 计算。
"""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_all.h5"


def run_factor_code(factor_code: str) -> pd.Series | None:
    """Execute factor code in a temp dir with daily_pv.h5 symlinked."""
    work_dir = tempfile.mkdtemp(prefix="factor_eval_")
    try:
        os.symlink(DATA_PATH, os.path.join(work_dir, "daily_pv.h5"))
        debug_src = "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_debug.h5"
        if os.path.exists(debug_src):
            os.symlink(debug_src, os.path.join(work_dir, "daily_pv_debug.h5"))

        code_path = os.path.join(work_dir, "run.py")
        with open(code_path, "w") as f:
            f.write(factor_code)

        r = subprocess.run(
            [sys.executable, code_path],
            capture_output=True, text=True, timeout=180,
            cwd=work_dir,
        )

        result_h5 = os.path.join(work_dir, "result.h5")
        if os.path.exists(result_h5):
            fv = pd.read_hdf(result_h5)
            if isinstance(fv, pd.DataFrame):
                fv = fv.iloc[:, 0]
            return fv

        result_csv = os.path.join(work_dir, "result.csv")
        if os.path.exists(result_csv):
            fv = pd.read_csv(result_csv, index_col=0)
            if isinstance(fv, pd.DataFrame):
                fv = fv.iloc[:, 0]
            return fv

        return None
    except subprocess.TimeoutExpired:
        logger.warning("Factor code timed out")
        return None
    except Exception as e:
        logger.debug("Failed: %s", e)
        return None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def compute_metrics(fv: pd.Series, market_data: pd.DataFrame) -> dict | None:
    """Compute IC, RankIC, Sharpe, ARR, MDD using REAL daily returns."""
    if not isinstance(fv.index, pd.MultiIndex) or len(fv) < 100:
        return None

    # Use $close.pct_change() for real daily returns, NOT $return
    real_ret = market_data.groupby("instrument")["$close"].transform(lambda x: x.pct_change())
    # Forward 5-day return = sum of next 5 days' daily returns
    fwd = real_ret.groupby(level="instrument").transform(lambda x: x.rolling(5).sum().shift(-5))

    common = fv.dropna().index.intersection(fwd.dropna().index)
    if len(common) < 100:
        return None

    fv_arr = fv.loc[common].values.astype(np.float64)
    fwd_arr = fwd.loc[common].values.astype(np.float64)

    mask = np.isfinite(fv_arr) & np.isfinite(fwd_arr)
    fv_arr, fwd_arr = fv_arr[mask], fwd_arr[mask]
    if len(fv_arr) < 100:
        return None

    # Per-date IC for proper ICIR
    dates = common[mask]
    if hasattr(dates, 'get_level_values'):
        unique_dates = dates.get_level_values("datetime").unique()
        ic_per_date = []
        for d in unique_dates[-200:]:  # last 200 dates
            dmask = dates.get_level_values("datetime") == d
            fv_d = fv_arr[dmask] if hasattr(dmask, '__len__') else None
            fwd_d = fwd_arr[dmask] if hasattr(dmask, '__len__') else None
            if fv_d is not None and len(fv_d) > 50:
                ic_d = np.corrcoef(fv_d, fwd_d)[0, 1]
                if np.isfinite(ic_d):
                    ic_per_date.append(ic_d)
        mean_ic = np.mean(ic_per_date) if ic_per_date else 0.0
        std_ic = np.std(ic_per_date) if ic_per_date else 1.0
        icir = mean_ic / (std_ic + 1e-8)
    else:
        mean_ic = float(np.corrcoef(fv_arr, fwd_arr)[0, 1])
        icir = 0.0

    from scipy.stats import spearmanr
    rank_ic, _ = spearmanr(fv_arr, fwd_arr)

    # Long top 20% strategy
    cutoff = np.percentile(fv_arr, 80)
    long_ret = fwd_arr[fv_arr >= cutoff]
    if len(long_ret) > 10:
        # Daily returns → annualize
        arr = float(np.mean(long_ret) * 252)
        sharpe = float(np.mean(long_ret) / (np.std(long_ret) + 1e-8) * np.sqrt(252))
        cumret = np.cumsum(long_ret)
        mdd = float(np.min(cumret - np.maximum.accumulate(cumret)))
    else:
        arr = sharpe = mdd = 0.0

    return {
        "ic": mean_ic,
        "rank_ic": float(rank_ic),
        "icir": icir,
        "arr": arr,
        "sharpe": sharpe,
        "mdd": mdd,
        "samples": len(fv_arr),
    }


async def main():
    sys.path.insert(0, "/opt/quantmind")
    from backend.services.engine.qlib_app.services.rd_agent_persistence import RDAgentFactorPersistence

    persistence = RDAgentFactorPersistence()
    factors = await persistence.list_factors(limit=100)
    with_code = [f for f in factors if f.get("factor_code") and len(f["factor_code"].strip()) > 30]
    logger.info("Total: %d, with code: %d", len(factors), len(with_code))

    market_data = pd.read_hdf(DATA_PATH)
    market_data = market_data.loc[market_data.index.get_level_values("datetime") >= "2020-01-01"]
    logger.info("Market data loaded: %s rows", len(market_data))

    ok = fail = 0
    for f in with_code:
        fid, name, code = f["factor_id"], f["factor_name"], f["factor_code"]
        logger.info("[%s] %s", fid[:8], name)

        try:
            fv = run_factor_code(code)
            if fv is None:
                logger.warning("  No result")
                fail += 1
                continue

            m = compute_metrics(fv, market_data)
            if m is None:
                logger.warning("  Insufficient data (%d points)", len(fv))
                fail += 1
                continue

            logger.info(
                "  IC=%.4f RankIC=%.4f ICIR=%.3f ARR=%.1f%% Sharpe=%.2f MDD=%.3f",
                m["ic"], m["rank_ic"], m["icir"], m["arr"]*100, m["sharpe"], m["mdd"],
            )

            await persistence.update_factor_metrics(
                fid, status="completed",
                ic_value=round(m["ic"], 6),
                sharpe_ratio=round(m["sharpe"], 4),
                annual_return=round(m["arr"], 4),
                max_drawdown=round(m["mdd"], 4),
                metadata={
                    "rank_ic": round(m["rank_ic"], 6),
                    "icir": round(m["icir"], 4),
                    "sample_count": m["samples"],
                },
            )
            ok += 1
        except Exception:
            logger.error("  Error: %s", traceback.format_exc()[:200])
            fail += 1

    logger.info("Done: %d success, %d failed", ok, fail)


if __name__ == "__main__":
    asyncio.run(main())
