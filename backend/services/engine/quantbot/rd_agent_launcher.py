"""QuantBot RD-Agent 演化循环启动器

修复内容（vs 历史版本）：
1. 删除 ALPHA191_SEED_TEMPLATE 死引用 (NameError)
2. 把 SEED_FACTOR_TEMPLATES 模板里 {window} / {long_window} 占位符全部对齐
3. 不再 subprocess 直跑 python -m rdagent，改为通过 wrapper script
   scripts/rd_agent/rd_agent_run.py，参数固定可控
4. 优先使用 Docker 模式：通过 docker SDK 启动 quantmind-rdagent 容器执行单次任务
   - 注入 QLIB_PROVIDER_URI / OPENAI_API_KEY / RD_AGENT_TASK_ID 等环境
   - 失败时 fallback 到 in-process subprocess (开发环境)
5. _collect_results 仅按 metadata_json->>'task_id' 过滤本次任务因子，
   避免拿历史脏数据
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.services.engine.quantbot.task_store import QuantBotTaskStore

logger = logging.getLogger(__name__)


# Alpha191 seed factor 模板（多类型支持，所有占位符在 .format 时统一注入）
SEED_FACTOR_TEMPLATES = {
    "value": '''
import pandas as pd
import numpy as np

class SeedValueFactor:
    """Seed value factor: 低估值因子 (window={window})"""
    name = "seed_value"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        high = df.get("$high", df["$close"]).rolling({window}).max()
        low  = df.get("$low",  df["$close"]).rolling({window}).min()
        result["value"] = 1.0 / ((df["$close"] / df["$factor"]) / (high - low + 1e-8) + 1e-8)
        return result
''',
    "momentum": '''
import pandas as pd
import numpy as np

class SeedMomentumFactor:
    """Seed momentum factor: 动量因子 (window={window}/{long_window})"""
    name = "seed_momentum"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        result["momentum"] = df["$close"].rolling({window}).mean() / df["$close"].rolling({long_window}).mean() - 1
        return result
''',
    "volatility": '''
import pandas as pd
import numpy as np

class SeedVolatilityFactor:
    """Seed volatility factor: 低波动因子 (window={window})"""
    name = "seed_volatility"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        returns = df["$close"].pct_change()
        result["vol"] = -returns.rolling({window}).std()
        return result
''',
    "technical": '''
import pandas as pd
import numpy as np

class SeedTechnicalFactor:
    """Seed technical factor: 技术指标因子 (window={window}/{long_window})"""
    name = "seed_technical"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        ma_short = df["$close"].rolling({window}).mean()
        ma_long  = df["$close"].rolling({long_window}).mean()
        result["tech"] = (ma_short - ma_long) / (ma_long + 1e-8)
        return result
''',
    "quality": '''
import pandas as pd
import numpy as np

class SeedQualityFactor:
    """Seed quality factor: 质量因子 (window={window}/{long_window})"""
    name = "seed_quality"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        returns = df["$close"].pct_change()
        vol = returns.rolling({long_window}).std()
        mean_ret = returns.rolling({long_window}).mean()
        result["quality"] = mean_ret / (vol + 1e-8)
        return result
''',
    "growth": '''
import pandas as pd
import numpy as np

class SeedGrowthFactor:
    """Seed growth factor: 成长因子 (window={window})"""
    name = "seed_growth"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        ret_n = df["$close"].pct_change(periods={window})
        result["growth"] = ret_n
        return result
''',
    "综合": '''
import pandas as pd
import numpy as np

class SeedCompositeFactor:
    """Seed composite factor: 综合因子 (window={window}/{long_window})"""
    name = "seed_composite"
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        ret = df["$close"].pct_change()
        ma = df["$close"].rolling({window}).mean()
        vol = ret.rolling({long_window}).std()
        result["composite"] = (ma / df["$close"] - 1) / (vol + 1e-8)
        return result
''',
}


_WINDOW_MAP = {
    "value":      {"window": 20,  "long_window": 60},
    "momentum":   {"window": 20,  "long_window": 60},
    "volatility": {"window": 20,  "long_window": 60},
    "technical":  {"window": 10,  "long_window": 60},
    "quality":    {"window": 60,  "long_window": 252},
    "growth":     {"window": 60,  "long_window": 252},
    "综合":       {"window": 20,  "long_window": 60},
}


class RDAgentLauncher:
    """启动 RD-Agent 因子演化循环 (Docker 模式优先)"""

    DOCKER_IMAGE = os.getenv("RD_AGENT_DOCKER_IMAGE", "quantmind-rdagent:latest")
    DOCKER_NETWORK = os.getenv("RD_AGENT_DOCKER_NETWORK", "quantmind_quantmind-net")
    HOST_PROJECT_PATH = os.getenv("HOST_PROJECT_PATH", "/opt/quantmind")
    QLIB_PROVIDER_URI = os.getenv("QLIB_PROVIDER_URI", "/app/db/qlib_data/cn_data")

    # RD-Agent 因子数据模板路径（daily_pv_all.h5 / daily_pv_debug.h5 所在目录）
    _FACTOR_DATA_TEMPLATE_DIR = (
        Path(HOST_PROJECT_PATH)
        / "rd-agent"
        / "rdagent"
        / "scenarios"
        / "qlib"
        / "experiment"
        / "factor_data_template"
    )

    def __init__(self):
        self.task_store = QuantBotTaskStore()
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def launch_evolution(
        self,
        task_id: str,
        user_id: str,
        request: dict[str, Any],
    ) -> None:
        """异步启动 RD-Agent 演化循环 (Docker 优先，subprocess 兜底)"""

        async def _run():
            try:
                await self.task_store.update_status(
                    task_id, "running", progress="正在初始化 RD-Agent..."
                )

                # 1. 生成 seed factors
                seed_path = await self._generate_seed_factors(request)
                logger.info("Generated seed factors at %s", seed_path)

                loop_n = int(request.get("constraints", {}).get("loop_n", 3))

                await self.task_store.update_status(
                    task_id, "running",
                    progress=f"演化循环进行中 (Docker={self._can_use_docker()}, loop_n={loop_n})...",
                )

                # 2. 选择执行后端
                if self._can_use_docker():
                    rc, log_tail = await self._run_in_docker(task_id, user_id, seed_path, loop_n)
                else:
                    rc, log_tail = await self._run_in_subprocess(task_id, user_id, seed_path, loop_n)

                if rc != 0:
                    raise RuntimeError(f"RD-Agent 退出码={rc}，最后日志:\n{log_tail}")

                # 3. 仅取本次 task_id 的因子 (避免脏数据)
                await self.task_store.update_status(task_id, "running", progress="正在汇总结果...")
                factors = await self._collect_results(task_id)
                factor_ids = [f["factor_id"] for f in factors]

                result = {
                    "factors": factors,
                    "total_factors": len(factors),
                    "summary": self._build_summary(factors),
                }
                await self.task_store.update_status(
                    task_id, "completed",
                    progress=f"完成，本次生成 {len(factors)} 个因子",
                    result=result,
                    factor_ids=factor_ids,
                )
                logger.info("Task %s completed with %d factors", task_id, len(factors))

            except Exception as exc:
                logger.exception("Task %s failed", task_id)
                await self.task_store.update_status(
                    task_id, "failed", error_message=str(exc)
                )

        task = asyncio.create_task(_run(), name=f"quantbot-{task_id}")
        self._running_tasks[task_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(task_id, None))

    # ------------------------------------------------------------------
    # seed factor 生成
    # ------------------------------------------------------------------

    async def _generate_seed_factors(self, request: dict[str, Any]) -> Path:
        factor_type = (
            request.get("factor_type")
            or (request.get("intent", {}) or {}).get("factor_type")
            or "综合"
        )
        if factor_type not in SEED_FACTOR_TEMPLATES:
            logger.warning("未知 factor_type=%s，回落到 综合", factor_type)
            factor_type = "综合"

        template = SEED_FACTOR_TEMPLATES[factor_type]
        windows = _WINDOW_MAP.get(factor_type, _WINDOW_MAP["综合"])
        seed_code = template.format(**windows)

        tmp_dir = Path(tempfile.mkdtemp(prefix="quantbot_seed_"))
        seed_path = tmp_dir / "seed_factor.py"
        seed_path.write_text(seed_code, encoding="utf-8")
        return seed_path

    # ------------------------------------------------------------------
    # 后端 1：Docker
    # ------------------------------------------------------------------

    def _can_use_docker(self) -> bool:
        if os.getenv("RD_AGENT_DISABLE_DOCKER", "").lower() in ("1", "true", "yes"):
            return False
        try:
            import docker  # noqa: F401
        except ImportError:
            return False
        return Path("/var/run/docker.sock").exists()

    async def _run_in_docker(
        self, task_id: str, user_id: str, seed_path: Path, loop_n: int,
    ) -> tuple[int, str]:
        """通过 docker SDK 启动 quantmind-rdagent 单次容器"""
        import docker
        from docker.errors import ImageNotFound

        client = docker.from_env()
        try:
            client.images.get(self.DOCKER_IMAGE)
        except ImageNotFound:
            return 127, (
                f"镜像 {self.DOCKER_IMAGE} 未构建。请先执行: "
                f"docker compose --profile rdagent build rdagent"
            )

        # 把宿主路径映射给子容器；seed 走宿主 /tmp（Linux 共享）
        seed_host = str(seed_path)
        seed_mount = "/tmp/seed_factor.py"

        chat_model = os.getenv("CHAT_MODEL") or os.getenv("AI_IDE_LLM_MODEL") or "deepseek-chat"
        # LiteLLM 要求 provider 前缀；DeepSeek 必须写成 "deepseek/deepseek-chat"
        if "/" not in chat_model:
            if chat_model.startswith("deepseek"):
                chat_model = f"deepseek/{chat_model}"
            elif chat_model.startswith(("qwen", "Qwen")):
                chat_model = f"dashscope/{chat_model}"
            elif chat_model.startswith(("gpt-", "o1-", "o3-")):
                chat_model = f"openai/{chat_model}"

        env = {
            "PYTHONPATH": "/app",
            "RD_AGENT_TASK_ID": task_id,
            "RD_AGENT_USER_ID": user_id,
            "RD_AGENT_SEED_PATH": seed_mount,
            "RD_AGENT_LOOP_N": str(loop_n),
            "QLIB_PROVIDER_URI": self.QLIB_PROVIDER_URI,
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY") or os.getenv("AI_IDE_LLM_API_KEY", ""),
            "OPENAI_API_BASE": os.getenv("OPENAI_API_BASE") or os.getenv("AI_IDE_LLM_BASE_URL", ""),
            "CHAT_MODEL": chat_model,
            # rdagent 直接读 DEEPSEEK_API_KEY 给 litellm
            "DEEPSEEK_API_KEY": os.getenv("OPENAI_API_KEY") or os.getenv("AI_IDE_LLM_API_KEY", ""),
            "DATABASE_URL": os.getenv("DATABASE_URL", ""),
        }

        host = self.HOST_PROJECT_PATH.rstrip("/")
        # 共享日志目录：rdagent 容器写入，quantmind 容器读取
        log_dir_host = f"{host}/data/rdagent_logs"
        log_dir_container = "/tmp/rdagent_logs"
        volumes = {
            f"{host}/backend": {"bind": "/app/backend", "mode": "ro"},
            f"{host}/scripts": {"bind": "/app/scripts", "mode": "ro"},
            f"{host}/config":  {"bind": "/app/config",  "mode": "ro"},
            f"{host}/db":      {"bind": "/app/db",      "mode": "ro"},
            log_dir_host:      {"bind": log_dir_container, "mode": "rw"},
            seed_host: {"bind": seed_mount, "mode": "ro"},
        }

        # daily_pv.h5 已在镜像构建时预置到 git_ignore_folder/factor_implementation_source_data/
        # 如果镜像没有预置数据（旧镜像），从宿主机挂载并复制
        template_dir = self._FACTOR_DATA_TEMPLATE_DIR
        if template_dir.exists():
            volumes[str(template_dir / "daily_pv_all.h5")] = {
                "bind": "/app/rdagent_factor_data_fallback/daily_pv.h5", "mode": "ro",
            }

        # 确保数据文件在因子执行工作目录下
        data_setup_cmd = (
            "if [ ! -f git_ignore_folder/factor_implementation_source_data/daily_pv.h5 ]; then "
            "  mkdir -p git_ignore_folder/factor_implementation_source_data; "
            "  if [ -f /app/rdagent_factor_data_fallback/daily_pv.h5 ]; then "
            "    cp /app/rdagent_factor_data_fallback/daily_pv.h5 "
            "       git_ignore_folder/factor_implementation_source_data/daily_pv.h5; "
            "  fi; "
            "fi; "
        )

        cmd = [
            "sh", "-c",
            data_setup_cmd
            + f"python /app/scripts/rd_agent/rd_agent_run.py "
            + f"--task-id '{task_id}' "
            + f"--user-id '{user_id}' "
            + f"--seed '{seed_mount}' "
            + f"--loop-n {loop_n} "
            + f"--provider-uri '{self.QLIB_PROVIDER_URI}'",
        ]

        loop = asyncio.get_running_loop()
        container = await loop.run_in_executor(
            None,
            lambda: client.containers.run(
                self.DOCKER_IMAGE,
                command=cmd,
                entrypoint="",  # override ENTRYPOINT to prevent "python rd_agent_run.py sh -c ..."
                environment=env,
                volumes=volumes,
                network=self.DOCKER_NETWORK,
                detach=True,
                name=f"rdagent-{task_id[:16]}",
                remove=False,
            ),
        )

        log_tail = ""
        rc = -1
        try:
            rc = await self._wait_with_progress(container, task_id, loop_n)
            logs = await loop.run_in_executor(
                None, lambda: container.logs(stdout=True, stderr=True, tail=200)
            )
            log_tail = logs.decode("utf-8", errors="replace")[-4000:]
            logger.info("[rdagent-docker] task=%s rc=%s", task_id, rc)
        finally:
            try:
                await loop.run_in_executor(None, container.remove)
            except Exception:
                pass

        return rc, log_tail

    async def _wait_with_progress(
        self, container, task_id: str, loop_n: int,
    ) -> int:
        """等待容器结束，同时每 10s 轮询日志并把最新一行写入 task progress。"""
        loop = asyncio.get_running_loop()
        wait_task = loop.run_in_executor(None, container.wait)

        start = time.time()
        last_progress = ""
        poll_interval = 10.0
        # 当前 loop 进度（从日志里抓 "Loop X/Y" 模式）
        loop_re = re.compile(r"[Ll]oop[\s_]?(\d+)\s*/\s*(\d+)")
        # 噪音过滤
        noise_re = re.compile(
            r"(DEBUG|^\s*$|warning|deprecat|^\s*at\s|Traceback)", re.IGNORECASE,
        )

        while not wait_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=poll_interval)
                break
            except asyncio.TimeoutError:
                pass

            try:
                raw = await loop.run_in_executor(
                    None,
                    lambda: container.logs(stdout=True, stderr=True, tail=80, timestamps=False),
                )
                text_logs = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.debug("logs poll failed: %s", exc)
                continue

            lines = [ln.rstrip() for ln in text_logs.splitlines() if ln.strip()]
            last_meaningful = ""
            current_loop = None
            for ln in reversed(lines):
                if not last_meaningful and not noise_re.search(ln):
                    last_meaningful = ln
                m = loop_re.search(ln)
                if m and current_loop is None:
                    current_loop = (int(m.group(1)), int(m.group(2)))
                if last_meaningful and current_loop:
                    break

            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            elapsed_str = f"{mins}分{secs:02d}秒" if mins else f"{secs}秒"

            loop_str = (
                f"第 {current_loop[0]}/{current_loop[1]} 轮"
                if current_loop else f"演化中 (共 {loop_n} 轮)"
            )
            snippet = (last_meaningful or "等待 Docker 输出...")[:140]
            progress = f"{loop_str} · 已运行 {elapsed_str} · {snippet}"

            if progress != last_progress:
                try:
                    await self.task_store.update_status(
                        task_id, "running", progress=progress,
                    )
                    last_progress = progress
                except Exception as exc:
                    logger.debug("progress update failed: %s", exc)

        result = await wait_task
        return int(result.get("StatusCode", -1))

    # ------------------------------------------------------------------
    # 后端 2：subprocess (开发兜底)
    # ------------------------------------------------------------------

    async def _run_in_subprocess(
        self, task_id: str, user_id: str, seed_path: Path, loop_n: int,
    ) -> tuple[int, str]:
        wrapper = "/app/scripts/rd_agent/rd_agent_run.py"
        if not Path(wrapper).exists():
            # 开发环境可能在仓库根
            alt = Path(__file__).resolve().parents[4] / "scripts/rd_agent/rd_agent_run.py"
            wrapper = str(alt) if alt.exists() else wrapper

        # 确保因子数据文件在工作目录下可达
        data_dir = Path("/tmp/git_ignore_folder/factor_implementation_source_data")
        data_dir.mkdir(parents=True, exist_ok=True)
        dst = data_dir / "daily_pv.h5"
        src = self._FACTOR_DATA_TEMPLATE_DIR / "daily_pv_all.h5"
        if src.exists() and not dst.exists():
            shutil.copy(str(src), str(dst))

        cmd = [
            "python", wrapper,
            "--task-id", task_id,
            "--user-id", user_id,
            "--seed", str(seed_path),
            "--loop-n", str(loop_n),
            "--provider-uri", self.QLIB_PROVIDER_URI,
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = env.get("PYTHONPATH", "/app")
        env.setdefault("QLIB_PROVIDER_URI", self.QLIB_PROVIDER_URI)
        env["FACTOR_CoSTEER_data_folder"] = "/tmp/git_ignore_folder/factor_implementation_source_data"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd="/tmp",
            env=env,
        )
        tail_buf: list[str] = []
        async for line in proc.stdout:
            decoded = line.decode("utf-8", errors="replace").rstrip()
            logger.info("[rdagent-subproc] %s", decoded)
            tail_buf.append(decoded)
            if len(tail_buf) > 200:
                tail_buf.pop(0)
        await proc.wait()
        return proc.returncode or 0, "\n".join(tail_buf)

    # ------------------------------------------------------------------
    # 结果聚合
    # ------------------------------------------------------------------

    async def _collect_results(self, task_id: str) -> list[dict[str, Any]]:
        """从 rd_agent_factors 表收集本次 task_id 的因子"""
        from backend.shared.database_manager_v2 import get_session
        from sqlalchemy import text

        async with get_session(read_only=True) as session:
            rows = await session.execute(
                text("""
                    SELECT factor_id, factor_name, status, ic_value, sharpe_ratio,
                           annual_return, max_drawdown, metadata_json, created_at
                    FROM rd_agent_factors
                    WHERE metadata_json::jsonb ->> 'task_id' = :task_id
                    ORDER BY created_at DESC
                    LIMIT 50
                """),
                {"task_id": task_id},
            )
            data = rows.mappings().all()
            results = []
            for r in data:
                item = dict(r)
                meta = item.pop("metadata_json", None)
                if isinstance(meta, str):
                    try:
                        item["metadata"] = json.loads(meta)
                    except Exception:
                        item["metadata"] = {}
                else:
                    item["metadata"] = meta or {}
                results.append(item)
            return results

    def _build_summary(self, factors: list[dict]) -> dict:
        if not factors:
            return {"message": "本次任务未生成任何因子"}

        completed = [f for f in factors if f.get("status") == "completed"]
        ic_values = [f["ic_value"] for f in completed if f.get("ic_value") is not None]
        sharpes = [f["sharpe_ratio"] for f in completed if f.get("sharpe_ratio") is not None]

        return {
            "total": len(factors),
            "completed": len(completed),
            "avg_ic": round(sum(ic_values) / len(ic_values), 4) if ic_values else None,
            "best_ic": round(max(ic_values), 4) if ic_values else None,
            "avg_sharpe": round(sum(sharpes) / len(sharpes), 4) if sharpes else None,
            "best_sharpe": round(max(sharpes), 4) if sharpes else None,
        }
