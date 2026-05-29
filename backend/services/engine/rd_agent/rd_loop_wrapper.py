"""RDLoop 包装器 — 将 RD-Agent 的 FactorRDLoop 适配到 QuantMind

提供统一接口:
- 接收 MarketAdapter 配置市场参数
- 启动/监控/取消 RDLoop
- 从日志中提取因子结果
"""

from __future__ import annotations

import asyncio
import logging
import os
import pickle
import re
import time
from pathlib import Path
from typing import Any

from .market_adapters import get_adapter, list_markets
from .market_adapters.base import MarketAdapter

logger = logging.getLogger(__name__)


class RDLoopWrapper:
    """封装 RD-Agent FactorRDLoop，提供 QuantMind 兼容接口"""

    def __init__(self, market: str = "a_share") -> None:
        self.adapter: MarketAdapter = get_adapter(market)
        if self.adapter is None:
            raise ValueError(f"Unknown market: {market}. Available: {[m['market_id'] for m in list_markets()]}")
        self.market = market
        self._loop = None
        self._running = False
        self._cancelled = False

    @property
    def market_name(self) -> str:
        return self.adapter.market_name

    def _configure_env(self, task_log_dir: str) -> dict[str, str]:
        """从 MarketAdapter 构建环境变量"""
        env_overrides = self.adapter.get_env_overrides()
        env = {
            **os.environ,
            **env_overrides,
            "LOG_TRACE_PATH": task_log_dir,
            "PYTHONPATH": os.getenv("PYTHONPATH") or "/app",
        }
        # Ensure critical LLM settings are present
        if not env.get("OPENAI_BASE_URL"):
            env["OPENAI_BASE_URL"] = os.getenv("OPENAI_BASE_URL", "")
        if not env.get("OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = os.getenv("AI_IDE_LLM_API_KEY", "")
        if not env.get("CHAT_MODEL"):
            env["CHAT_MODEL"] = os.getenv("CHAT_MODEL", "")
        # litellm needs provider prefix for non-OpenAI models
        model = env.get("CHAT_MODEL", "")
        if model and not model.startswith(("openai/", "azure/", "anthropic/", "huggingface/")):
            env["CHAT_MODEL"] = f"openai/{model}"
        env["REASONING_MODEL"] = env.get("CHAT_MODEL", "")
        env["CHAT_STREAM"] = "false"
        return env

    def _create_loop(self):
        """创建 FactorRDLoop 实例"""
        from rdagent.app.qlib_rd_loop.conf import FactorBasePropSetting
        from rdagent.app.qlib_rd_loop.factor import FactorRDLoop
        from rdagent.core.utils import import_class

        prop_setting_path = self.adapter.get_prop_setting_class()
        prop_cls = import_class(prop_setting_path)
        prop_setting = prop_cls()

        loop = FactorRDLoop(prop_setting)
        return loop

    async def run(
        self,
        loop_n: int = 3,
        task_log_dir: str = "",
        direction: str = "",
    ) -> dict[str, Any]:
        """执行因子挖掘循环

        Args:
            loop_n: 循环轮数
            task_log_dir: 日志输出目录
            direction: 挖掘方向/假设

        Returns:
            包含 factors 和 metadata 的结果字典
        """
        self._running = True
        self._cancelled = False

        try:
            # 配置环境变量
            env = self._configure_env(task_log_dir)
            for k, v in env.items():
                os.environ[k] = v

            logger.info("[%s] RDLoop starting: market=%s, loops=%d, log_dir=%s",
                        self.market, self.adapter.market_name, loop_n, task_log_dir)

            # 创建 RDLoop
            self._loop = self._create_loop()
            step_count = len(self._loop.steps)
            total_steps = loop_n * step_count

            logger.info("[%s] Steps per loop: %d, total steps: %d", self.market, step_count, total_steps)
            logger.info("[%s] Step flow: %s", self.market,
                        " → ".join(getattr(s, '__name__', s.__class__.__name__) for s in self._loop.steps))

            # 运行循环
            t0 = time.time()
            await self._loop.run(step_n=total_steps)
            elapsed = time.time() - t0

            logger.info("[%s] RDLoop completed in %.1fs", self.market, elapsed)

            # 提取结果
            factors = self._extract_factors(task_log_dir)

            return {
                "market": self.market,
                "market_name": self.adapter.market_name,
                "loop_n": loop_n,
                "elapsed_seconds": elapsed,
                "factors": factors,
                "total_factors": len(factors),
                "log_dir": task_log_dir,
            }

        except asyncio.CancelledError:
            self._cancelled = True
            logger.info("[%s] RDLoop cancelled", self.market)
            return {"market": self.market, "cancelled": True, "factors": []}

        except Exception as e:
            logger.exception("[%s] RDLoop failed: %s", self.market, e)
            return {"market": self.market, "error": str(e), "factors": []}

        finally:
            self._running = False

    def cancel(self):
        """请求取消运行"""
        self._cancelled = True
        logger.info("[%s] Cancellation requested", self.market)

    @property
    def is_running(self) -> bool:
        return self._running

    def _extract_factors(self, log_dir: str) -> list[dict[str, Any]]:
        """从 RD-Agent 日志目录提取因子

        RDLoop 输出结构 (pickle):
        - experiment generation/**/*.pkl → 实验任务 (因子名 + 表达式)
        - coder result/**/*.pkl → 编码结果 (因子代码)
        - feedback/**/*.pkl → 反馈 (IC 等指标)
        """
        log_path = Path(log_dir)
        if not log_path.exists():
            logger.warning("[%s] Log dir not found: %s", self.market, log_dir)
            return []

        pkl_count = len(list(log_path.glob("**/*.pkl")))
        logger.info("[%s] Scanning log dir: %s (%d pkl files)", self.market, log_dir, pkl_count)

        # 1. Factor metadata
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

        # 2. Factor code
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
                            if isinstance(v, str) and "def " in v:
                                code = v
                                break
                    if code:
                        fn_match = re.search(r"def\s+(\w+)\s*\(", code)
                        fname = fn_match.group(1) if fn_match else f"factor_{len(factor_code)}"
                        factor_code[fname] = code
            except Exception as e:
                logger.debug("Failed to read coder result %s: %s", pkl_path, e)

        # 3. Feedback
        feedback_text = ""
        for pkl_path in sorted(log_path.glob("**/feedback/**/*.pkl")):
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

        # 4. Merge — match factor_meta names to factor_code names
        #    Code names may have "calculate_" prefix (e.g. calculate_MOM_10D vs MOM_10D)
        code_by_base: dict[str, str] = {}
        for fname, code in factor_code.items():
            base = fname.removeprefix("calculate_")
            code_by_base[base] = code

        factors: list[dict] = []
        all_names = set(factor_meta.keys()) | set(code_by_base.keys())
        for name in sorted(all_names):
            meta = factor_meta.get(name, {})
            code = code_by_base.get(name, "")
            factors.append({
                "name": meta.get("name", name),
                "formulation": meta.get("formulation", ""),
                "description": meta.get("description", ""),
                "category": meta.get("category", ""),
                "code": code,
                "market": self.market,
                "feedback": feedback_text[:5000] if feedback_text else "",
            })

        logger.info("[%s] Extracted %d factors", self.market, len(factors))
        return factors


# ── Runner script entry point (subprocess) ──


def run_factor_mining_subprocess(
    market: str,
    task_id: str,
    user_id: str,
    loop_n: int,
    log_dir: str,
    direction: str = "",
) -> dict[str, Any]:
    """在子进程中执行因子挖掘（用于 launcher 调用）

    这是同步入口点，由 launcher 的 subprocess 调用。
    """
    wrapper = RDLoopWrapper(market=market)
    logger.info("Starting factor mining: market=%s, task=%s, loops=%d", market, task_id, loop_n)
    result = asyncio.run(wrapper.run(
        loop_n=loop_n,
        task_log_dir=log_dir,
        direction=direction,
    ))
    result["task_id"] = task_id
    result["user_id"] = user_id
    return result
