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
        # 设置数据文件路径环境变量
        data_file = "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_all.h5"
        if os.path.exists(data_file):
            env["FACTOR_DATA_PATH"] = data_file
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
        # 回测数据从 2016 年开始 (默认 2008 太慢)
        env.setdefault("QLIB_FACTOR_TRAIN_START", os.getenv("QLIB_FACTOR_TRAIN_START", "2016-01-01"))
        env.setdefault("QLIB_FACTOR_VALID_START", os.getenv("QLIB_FACTOR_VALID_START", "2021-01-01"))
        env.setdefault("QLIB_FACTOR_VALID_END", os.getenv("QLIB_FACTOR_VALID_END", "2022-12-31"))
        env.setdefault("QLIB_FACTOR_TEST_START", os.getenv("QLIB_FACTOR_TEST_START", "2023-01-01"))
        env.setdefault("QLIB_FACTOR_TEST_END", os.getenv("QLIB_FACTOR_TEST_END", "2025-12-31"))
        # 因子处理并行数
        env.setdefault("MULTI_PROC_N", os.getenv("MULTI_PROC_N", "4"))
        return env

    def _patch_prompts_for_chinese(self):
        """注入中文指令到 RD-Agent 提示词模板，使因子描述使用中文"""
        try:
            from jinja2 import Template
            from rdagent.scenarios.qlib.experiment import prompts as qlib_prompts
            from rdagent.components.coder.factor_coder import prompts as coder_prompts

            # 1. 因子背景提示 — 要求中文描述
            zh_suffix = (
                "\n\n====== 语言要求 / Language Requirement ======\n"
                "所有因子的 description 字段必须使用中文撰写。"
                "hypothesis 和 reason 也请用中文。\n"
                "All factor descriptions MUST be written in Chinese (中文). "
                "Hypothesis and reason should also be in Chinese.\n"
            )
            if hasattr(qlib_prompts, 'qlib_factor_background'):
                original = qlib_prompts.qlib_factor_background
                if '中文' not in original:
                    qlib_prompts.qlib_factor_background = original + zh_suffix
                    logger.info("Patched qlib_factor_background with Chinese instruction")

            # 2. 因子输出格式 — 要求中文 description
            if hasattr(qlib_prompts, 'factor_hypothesis_output_format'):
                original = qlib_prompts.factor_hypothesis_output_format
                if '中文' not in original:
                    qlib_prompts.factor_hypothesis_output_format = original.replace(
                        '"reason": "The reason',
                        '"reason": "用中文撰写。The reason'
                    )
                    logger.info("Patched factor_hypothesis_output_format with Chinese instruction")

        except Exception as e:
            logger.warning("Failed to patch prompts for Chinese: %s", e)

    def _create_loop(self):
        """创建 FactorRDLoop 实例"""
        from rdagent.app.qlib_rd_loop.conf import FactorBasePropSetting
        from rdagent.app.qlib_rd_loop.factor import FactorRDLoop
        from rdagent.core.utils import import_class

        # 注入中文指令
        self._patch_prompts_for_chinese()

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

            # 确保 daily_pv.h5 数据文件可用
            self._ensure_data_file(task_log_dir)

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

    def _ensure_data_file(self, task_log_dir: str = ""):
        """确保 daily_pv.h5 数据文件和 Qlib 数据目录在 RD-Agent 期望的位置可用

        RD-Agent 的 subprocess 以 task_log_dir 为 cwd 运行，
        FACTOR_COSTEER_SETTINGS.data_folder (git_ignore_folder/factor_implementation_source_data)
        相对于 cwd 解析。需要在 task_log_dir 下创建该目录并复制数据文件。

        同时确保对应的 Qlib provider_uri 目录可用。
        """
        import shutil

        # 根据市场选择数据源
        market_data_map = {
            "crypto": {
                "source_all": "/app/db/crypto_data/daily_pv.h5",
                "source_debug": "/app/db/crypto_data/daily_pv.h5",
                "qlib_source": "/app/db/qlib_data/crypto_data",
                "qlib_target_name": "crypto_data",
            },
            "hong_kong": {
                "source_all": "/app/db/hk_data/daily_pv.h5",
                "source_debug": "/app/db/hk_data/daily_pv.h5",
                "qlib_source": "/app/db/qlib_data/hk_data",
                "qlib_target_name": "hk_data",
            },
            "us_stock": {
                "source_all": "/app/db/us_data/daily_pv.h5",
                "source_debug": "/app/db/us_data/daily_pv.h5",
                "qlib_source": "/app/db/qlib_data/us_data",
                "qlib_target_name": "us_data",
            },
        }

        # 默认 A 股
        market_cfg = market_data_map.get(self.market, {
            "source_all": "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_all.h5",
            "source_debug": "/app/alphaagent/scenarios/qlib/experiment/factor_data_template/daily_pv_debug.h5",
            "qlib_source": "/app/db/qlib_data/cn_data",
            "qlib_target_name": "cn_data",
        })

        source_all = market_cfg["source_all"]
        source_debug = market_cfg["source_debug"]

        # base_dir: RD-Agent subprocess cwd (task log dir)
        base_dir = task_log_dir if task_log_dir else os.getcwd()

        # RD-Agent data folders (relative to subprocess cwd)
        targets = [
            (os.path.join(base_dir, "git_ignore_folder/factor_implementation_source_data/daily_pv.h5"), source_all),
            (os.path.join(base_dir, "git_ignore_folder/factor_implementation_source_data_debug/daily_pv.h5"), source_debug),
        ]

        for target, source in targets:
            if not os.path.exists(source):
                logger.warning("[%s] Source data file not found: %s", self.market, source)
                continue
            target_dir = os.path.dirname(target)
            os.makedirs(target_dir, exist_ok=True)
            if not os.path.exists(target) or os.path.getmtime(source) > os.path.getmtime(target):
                try:
                    shutil.copy2(source, target)
                    logger.info("[%s] Copied data file: %s -> %s", self.market, source, target)
                except Exception as e:
                    logger.warning("[%s] Failed to copy data file to %s: %s", self.market, target, e)

        # Ensure Qlib provider_uri data is available at ~/.qlib/qlib_data/<market>
        qlib_source = market_cfg["qlib_source"]
        qlib_target_name = market_cfg["qlib_target_name"]
        qlib_target = os.path.expanduser(f"~/.qlib/qlib_data/{qlib_target_name}")
        if os.path.isdir(qlib_source) and not os.path.exists(qlib_target):
            try:
                os.makedirs(os.path.dirname(qlib_target), exist_ok=True)
                os.symlink(qlib_source, qlib_target)
                logger.info("[%s] Created symlink: %s -> %s", self.market, qlib_target, qlib_source)
            except Exception as e:
                logger.warning("[%s] Failed to create Qlib symlink: %s", self.market, e)

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
