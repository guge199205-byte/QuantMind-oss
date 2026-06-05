import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from rdagent.components.coder.model_coder.conf import MODEL_COSTEER_SETTINGS
from rdagent.core.experiment import FBWorkspace
from rdagent.log import rdagent_logger as logger
from rdagent.utils.env import QlibCondaConf, QlibCondaEnv, QTDockerEnv


def _run_cmd_in_current_env(entry: str, local_path: str, env: dict = None) -> str:
    """Run command directly in the current environment (no conda/docker)."""
    extra_env = env or {}
    full_env = {**__import__('os').environ, **extra_env}
    result = subprocess.run(
        entry,
        shell=True,
        cwd=local_path,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        output = result.stderr if result.stderr else result.stdout
        raise RuntimeError(f"Command failed (exit {result.returncode}): {entry}\n{output[-2000:]}")
    return result.stdout if result.stdout else result.stderr


class QlibFBWorkspace(FBWorkspace):
    def __init__(self, template_folder_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.inject_code_from_folder(template_folder_path)

    def execute(self, qlib_config_name: str = "conf.yaml", run_env: dict = {}, *args, **kwargs) -> str:
        # 优先使用当前环境直接运行（避免 conda/docker 依赖）
        # qlib 和 qrun 已全局安装，直接在当前环境运行即可
        try:
            execute_qlib_log = _run_cmd_in_current_env(
                f"qrun {qlib_config_name}",
                local_path=str(self.workspace_path),
                env=run_env,
            )
            logger.log_object(execute_qlib_log, tag="Qlib_execute_log")

            execute_log = _run_cmd_in_current_env(
                "python read_exp_res.py",
                local_path=str(self.workspace_path),
                env=run_env,
            )
        except Exception as e:
            logger.error(f"Qlib execution failed: {e}")
            return None, str(e)[-2000:]

        quantitative_backtesting_chart_path = self.workspace_path / "ret.pkl"
        if quantitative_backtesting_chart_path.exists():
            ret_df = pd.read_pickle(quantitative_backtesting_chart_path)
            logger.log_object(ret_df, tag="Quantitative Backtesting Chart")
        else:
            logger.error("No result file found.")
            return None, execute_qlib_log

        qlib_res_path = self.workspace_path / "qlib_res.csv"
        if qlib_res_path.exists():
            # Here, we ensure that the qlib experiment has run successfully before extracting information from execute_qlib_log using regex; otherwise, we keep the original experiment stdout.
            pattern = r"(Epoch\d+: train -[0-9\.]+, valid -[0-9\.]+|best score: -[0-9\.]+ @ \d+ epoch)"
            matches = re.findall(pattern, execute_qlib_log)
            execute_qlib_log = "\n".join(matches)
            return pd.read_csv(qlib_res_path, index_col=0).iloc[:, 0], execute_qlib_log
        else:
            logger.error(f"File {qlib_res_path} does not exist.")
            return None, execute_qlib_log
