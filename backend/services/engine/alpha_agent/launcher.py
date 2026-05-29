"""AlphaAgent / RD-Agent 因子挖掘任务启动器

支持两种模式:
1. Legacy AlphaAgent (market=a_share, 使用 alphaagent/)
2. RD-Agent 多市场 (market=a_share|crypto|hong_kong|us_stock, 使用 rdagent/ + market_adapters/)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EvolutionTask:
    task_id: str
    user_id: str
    market: str = "a_share"
    status: TaskStatus = TaskStatus.PENDING
    progress: str = ""
    phase: str = "pending"
    progress_pct: int = 0
    loop_n: int = 3
    current_loop: int = 0
    created_at: float = field(default_factory=time.time)
    error_message: str | None = None
    result: dict[str, Any] | None = None
    process: subprocess.Popen | None = None
    _cancel_requested: bool = False


class AlphaAgentLauncher:
    """Launches factor evolution tasks (AlphaAgent or RD-Agent)."""

    _RUNNER_SCRIPT = str(
        Path(__file__).resolve().parent.parent.parent.parent.parent / "scripts" / "alpha_agent" / "run.py"
    )
    _RD_AGENT_RUNNER_SCRIPT = str(
        Path(__file__).resolve().parent.parent.parent.parent.parent / "scripts" / "alpha_agent" / "run_rd_agent.py"
    )

    def __init__(self) -> None:
        self._tasks: dict[str, EvolutionTask] = {}
        self._log_dir = Path(os.getenv("LOG_TRACE_PATH", "/tmp/alpha_agent_logs"))
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_evolution(
        self,
        user_id: str,
        *,
        market: str = "a_share",
        loop_n: int = 3,
        seed: str | None = None,
        provider_uri: str | None = None,
        direction: str | None = None,
    ) -> str:
        """Start a factor evolution task. Returns task_id."""
        task_id = uuid.uuid4().hex[:16]
        task = EvolutionTask(task_id=task_id, user_id=user_id, market=market, loop_n=loop_n)
        self._tasks[task_id] = task

        # Determine provider URI from market adapter if not specified
        if not provider_uri:
            try:
                from backend.services.engine.rd_agent.market_adapters import get_adapter
                adapter = get_adapter(market)
                provider_uri = adapter.get_qlib_provider_uri()
            except Exception:
                provider_uri = os.getenv("QLIB_PROVIDER_URI", "/app/db/qlib_data/cn_data")

        seed_path = seed or self._default_seed_path()

        asyncio.ensure_future(
            self._run_evolution(
                task,
                loop_n=loop_n,
                seed=seed_path,
                provider_uri=provider_uri,
                direction=direction or "",
            )
        )
        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": task.progress,
            "phase": task.phase,
            "progress_pct": task.progress_pct,
            "current_loop": task.current_loop,
            "loop_n": task.loop_n,
            "market": task.market,
            "error_message": task.error_message,
            "result": task.result,
        }

    async def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        task._cancel_requested = True
        if task.process and task.process.poll() is None:
            task.process.terminate()
        task.status = TaskStatus.FAILED
        task.error_message = "Cancelled by user"
        return True

    async def get_task_log(self, task_id: str, tail: int = 200) -> str | None:
        """Get subprocess stdout log for a task (for real-time monitoring)."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        log_file = self._log_dir / task_id / "subprocess_stdout.log"
        if not log_file.exists():
            return None
        try:
            with open(log_file, errors="replace") as f:
                lines = f.readlines()
            return "".join(lines[-tail:])
        except Exception:
            return None

    async def list_tasks(self, user_id: str | None = None) -> list[dict[str, Any]]:
        results = []
        for task in self._tasks.values():
            if user_id and task.user_id != user_id:
                continue
            results.append(await self.get_task_status(task.task_id))
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _default_seed_path(self) -> str:
        in_container = Path("/app/alphaagent/scenarios/qlib/experiment/factor_data_template")
        if in_container.exists():
            return str(in_container)
        project = os.getenv("HOST_PROJECT_PATH", "/opt/quantmind")
        template = Path(project) / "alphaagent" / "scenarios" / "qlib" / "experiment" / "factor_data_template"
        return str(template)

    async def _run_evolution(
        self,
        task: EvolutionTask,
        *,
        loop_n: int,
        seed: str,
        provider_uri: str,
        direction: str = "",
    ) -> None:
        task.status = TaskStatus.RUNNING
        task.phase = "starting"
        task.progress_pct = 2
        task.progress = "正在启动因子挖掘..."

        task_log_dir = self._log_dir / task.task_id
        task_log_dir.mkdir(parents=True, exist_ok=True)

        # Build environment
        openai_base = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or ""
        )
        openai_api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("AI_IDE_LLM_API_KEY")
            or ""
        )
        chat_model = os.getenv("CHAT_MODEL", "")
        system_prompt = os.getenv("ALPHA_AGENT_SYSTEM_PROMPT", "")

        env = {
            **os.environ,
            "PYTHONPATH": os.getenv("PYTHONPATH") or "/app",
            "LOG_TRACE_PATH": str(task_log_dir),
            "QLIB_PROVIDER_URI": provider_uri,
            "REASONING_MODEL": chat_model,
            "CHAT_STREAM": "false",
        }
        if system_prompt:
            env["DEFAULT_SYSTEM_PROMPT"] = system_prompt
        if openai_base:
            env["OPENAI_BASE_URL"] = openai_base
        if openai_api_key:
            env["OPENAI_API_KEY"] = openai_api_key
        if chat_model:
            env["CHAT_MODEL"] = chat_model

        # Add market adapter env overrides
        if task.market != "a_share" or True:  # Always use RD-Agent runner for all markets
            try:
                from backend.services.engine.rd_agent.market_adapters import get_adapter
                adapter = get_adapter(task.market)
                adapter_env = adapter.get_env_overrides()
                env.update(adapter_env)
            except Exception as e:
                logger.warning("Failed to get market adapter env: %s", e)

        # Select runner script: RD-Agent for all markets, legacy AlphaAgent as fallback
        use_rd_agent = True
        runner_script = self._RD_AGENT_RUNNER_SCRIPT if use_rd_agent else self._RUNNER_SCRIPT

        cmd = [
            sys.executable,
            runner_script,
            "--task-id", task.task_id,
            "--user-id", task.user_id,
            "--loop-n", str(loop_n),
            "--log-dir", str(task_log_dir),
            "--direction", direction,
        ]
        if use_rd_agent:
            cmd.extend(["--market", task.market])
        else:
            cmd.extend(["--seed", seed, "--provider-uri", provider_uri])

        logger.info("Starting factor mining: market=%s, script=%s", task.market, runner_script)
        logger.info("Command: %s", " ".join(cmd))

        stdout_log = task_log_dir / "subprocess_stdout.log"

        try:
            log_fh = open(stdout_log, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(task_log_dir),
            )
            task.process = process

            while process.poll() is None:
                if task._cancel_requested:
                    process.terminate()
                    break
                self._update_progress(task, task_log_dir)
                await asyncio.sleep(3)

            if process.poll() is None:
                process.wait(timeout=30)

            try:
                log_fh.close()
            except Exception:
                pass

            if process.returncode == 0:
                task.status = TaskStatus.COMPLETED
                task.phase = "completed"
                task.progress_pct = 100
                task.progress = "因子挖掘完成"
                task.result = self._collect_results(task, task_log_dir)
            else:
                task.status = TaskStatus.FAILED
                error_output = self._tail_error_log(task_log_dir)
                task.error_message = f"Process exited with code {process.returncode}: {error_output}"
                logger.error("Factor mining failed for task %s: %s", task.task_id, task.error_message)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.exception("Factor mining exception for task %s", task.task_id)

    _PHASE_ORDER = [
        ("scenario", "scenario", "初始化场景"),
        ("hypothesis generation", "hypothesis", "生成假设"),
        ("hypothesis generator", "hypothesis", "生成假设"),
        ("experiment generation", "experiment", "设计实验"),
        ("evolving code", "coder", "进化编写代码"),
        ("coder", "coder", "编写因子代码"),
        ("runner", "runner", "回测运行因子"),
        ("summarizer", "summarizer", "总结结果"),
    ]

    @staticmethod
    def _find_active_phase(root: Path) -> tuple[str, str, str] | None:
        best: tuple[float, tuple[str, str, str]] = (-1.0, ("", "", ""))
        for sub_name, key, label in AlphaAgentLauncher._PHASE_ORDER:
            sub = root / sub_name
            if not sub.is_dir():
                continue
            newest = -1.0
            try:
                for f in sub.rglob("*"):
                    if f.is_file():
                        try:
                            mt = f.stat().st_mtime
                        except OSError:
                            continue
                        if mt > newest:
                            newest = mt
            except OSError:
                continue
            if newest > best[0]:
                best = (newest, (sub_name, key, label))
        return best[1] if best[0] > 0 else None

    def _update_progress(self, task: EvolutionTask, log_dir: Path) -> None:
        r_dir = log_dir / "r"
        d_dir = log_dir / "d"
        loop_dirs = sorted(
            [p for p in log_dir.glob("Loop_*") if p.is_dir()],
            key=lambda p: int(p.name.split("_", 1)[1]) if p.name.split("_", 1)[1].isdigit() else 0,
        )

        candidates: list[tuple[int, Path]] = []
        if r_dir.is_dir():
            candidates.append((0, r_dir))
        if d_dir.is_dir():
            candidates.append((1, d_dir))
        for ld in loop_dirs:
            try:
                idx = int(ld.name.split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            candidates.append((idx, ld))

        if not candidates:
            task.phase = "starting"
            task.progress_pct = 2
            task.progress = "正在启动因子挖掘..."
            return

        best_candidate = candidates[0]
        best_mtime = -1.0
        for loop_idx, cpath in candidates:
            newest = -1.0
            try:
                for f in cpath.rglob("*"):
                    if f.is_file():
                        try:
                            mt = f.stat().st_mtime
                        except OSError:
                            continue
                        if mt > newest:
                            newest = mt
            except OSError:
                continue
            if newest > best_mtime:
                best_mtime = newest
                best_candidate = (loop_idx, cpath)

        task.current_loop = best_candidate[0]
        phase_root = best_candidate[1]

        result = self._find_active_phase(phase_root)
        if result is None:
            task.phase = "starting"
            task.progress_pct = 5
            task.progress = (
                f"Loop {task.current_loop}/{task.loop_n} — 准备中..."
                if task.current_loop
                else "首轮启动中..."
            )
            return

        sub_name, key, label = result
        task.phase = key
        try:
            phase_idx = [p[0] for p in self._PHASE_ORDER].index(sub_name)
        except ValueError:
            phase_idx = 0
        phase_frac = (phase_idx + 1) / len(self._PHASE_ORDER)

        total_units = max(task.loop_n + 1, 1)
        loop_frac = (task.current_loop + phase_frac) / total_units
        task.progress_pct = max(5, min(99, int(loop_frac * 100)))

        loop_tag = (
            "首轮"
            if task.current_loop == 0
            else f"Loop {task.current_loop}/{task.loop_n}"
        )
        task.progress = f"{loop_tag} — {label}"

    def _collect_results(self, task: EvolutionTask, log_dir: Path) -> dict[str, Any]:
        """Collect results from result.json or log dir."""
        result_file = log_dir / "result.json"
        if result_file.exists():
            try:
                return json.loads(result_file.read_text())
            except Exception:
                pass
        return {
            "total_factors": 0,
            "log_dir": str(log_dir),
            "task_id": task.task_id,
            "market": task.market,
            "message": "Factors persisted to DB by runner script",
        }

    @staticmethod
    def _tail_error_log(log_dir: Path, max_chars: int = 2000) -> str:
        try:
            logs = sorted(log_dir.rglob("common_logs.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not logs:
                return ""
            with open(logs[0], errors="replace") as f:
                return f.read()[-max_chars:]
        except Exception:
            return ""


# Singleton
_launcher: AlphaAgentLauncher | None = None


def get_launcher() -> AlphaAgentLauncher:
    global _launcher
    if _launcher is None:
        _launcher = AlphaAgentLauncher()
    return _launcher
