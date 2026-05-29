"""
标准化数据脚本运行器

提供统一的数据脚本执行和调度功能。
"""

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseDataOperation
from .data_validator import DataValidator
from .stock_data_updater import StockDataUpdater

# 添加路径以便导入共享模块
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app/backend/shared")


@dataclass
class TaskConfig:
    """任务配置数据类"""

    name: str
    operation_type: str
    parameters: dict[str, Any]
    enabled: bool = True
    depends_on: list[str] | None = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int | None = None


@dataclass
class TaskResult:
    """任务结果数据类"""

    task_name: str
    success: bool
    start_time: datetime
    end_time: datetime
    execution_time: float
    result: dict[str, Any]
    error: str | None = None


class DataScriptRunner(BaseDataOperation):
    """
    数据脚本运行器
    功能：
    - 任务调度和执行
    - 依赖关系管理
    - 错误处理和重试
    - 执行结果汇总
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("data-script-runner", config)
        # 操作类型映射
        self.operation_map = {
            "stock_data_update": StockDataUpdater,
            "data_validation": DataValidator,
        }
        # 任务执行状态
        self.tasks: dict[str, TaskConfig] = {}
        self.task_results: dict[str, TaskResult] = {}
        self.execution_order: list[str] = []

    def _execute_operation(self, **kwargs) -> dict[str, Any]:
        """
        执行数据脚本运行器
        Args:
            **kwargs: 操作参数
                - tasks: 任务配置列表
                - config_file: 配置文件路径（可选）
                - parallel: 是否并行执行（默认False）
        Returns:
            执行结果
        """
        # 加载任务配置
        if "config_file" in kwargs:
            self._load_tasks_from_file(kwargs["config_file"])
        elif "tasks" in kwargs:
            self._load_tasks_from_list(kwargs["tasks"])
        else:
            return {"success": False, "error": "No tasks provided"}
        parallel = kwargs.get("parallel", False)
        try:
            # 计算执行顺序
            self._calculate_execution_order()
            # 执行任务
            if parallel:
                self._execute_tasks_parallel()
            else:
                self._execute_tasks_sequential()
            # 汇总结果
            summary = self._generate_execution_summary()
            return {
                "success": summary["success_rate"] == 100.0,
                "execution_summary": summary,
                "task_results": {name: asdict(result) for name, result in self.task_results.items()},
                "execution_order": self.execution_order,
            }
        except Exception as e:
            self.logger.error(
                "Data script runner execution failed",
                extra={"operation_id": self.operation_id, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
                "task_results": {name: asdict(result) for name, result in self.task_results.items()},
            }

    def _load_tasks_from_file(self, config_file: str) -> None:
        """从文件加载任务配置"""
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        with open(config_path, encoding="utf-8") as f:
            config_data = json.load(f)
        self._load_tasks_from_list(config_data.get("tasks", []))
        self.logger.info(
            "Tasks loaded from config file",
            extra={
                "operation_id": self.operation_id,
                "config_file": config_file,
                "tasks_count": len(self.tasks),
            },
        )

    def _load_tasks_from_list(self, tasks_config: list[dict[str, Any]]) -> None:
        """从列表加载任务配置"""
        self.tasks.clear()
        for task_config in tasks_config:
            task = TaskConfig(
                name=task_config["name"],
                operation_type=task_config["operation_type"],
                parameters=task_config.get("parameters", {}),
                enabled=task_config.get("enabled", True),
                depends_on=task_config.get("depends_on"),
                retry_count=0,
                max_retries=task_config.get("max_retries", 3),
                timeout=task_config.get("timeout"),
            )
            self.tasks[task.name] = task
        self.logger.info(
            "Tasks loaded from list",
            extra={"operation_id": self.operation_id, "tasks_count": len(self.tasks)},
        )

    def _calculate_execution_order(self) -> None:
        """计算任务执行顺序（拓扑排序）"""
        # 简单的拓扑排序实现
        visited = set()
        temp_visited = set()
        order = []

        def visit(task_name: str):
            if task_name in temp_visited:
                raise ValueError(f"Circular dependency detected: {task_name}")
            if task_name in visited:
                return
            temp_visited.add(task_name)
            if task_name in self.tasks:
                task = self.tasks[task_name]
                if task.depends_on:
                    for dep in task.depends_on:
                        visit(dep)
            temp_visited.remove(task_name)
            visited.add(task_name)
            order.append(task_name)

        for task_name in self.tasks:
            if task_name not in visited:
                visit(task_name)
        self.execution_order = order
        self.logger.info(
            "Execution order calculated",
            extra={"operation_id": self.operation_id, "execution_order": order},
        )

    def _execute_tasks_sequential(self) -> dict[str, TaskResult]:
        """顺序执行任务"""
        self.logger.info(
            "Starting sequential task execution",
            extra={
                "operation_id": self.operation_id,
                "tasks_count": len(self.execution_order),
            },
        )
        for task_name in self.execution_order:
            if task_name not in self.tasks:
                continue
            task = self.tasks[task_name]
            if not task.enabled:
                self.logger.info(
                    "Skipping disabled task",
                    extra={"operation_id": self.operation_id, "task_name": task_name},
                )
                continue
            # 检查依赖任务是否成功
            if task.depends_on:
                dependencies_failed = False
                for dep in task.depends_on:
                    if dep in self.task_results and not self.task_results[dep].success:
                        dependencies_failed = True
                        break
                if dependencies_failed:
                    self.logger.warning(
                        "Skipping task due to failed dependencies",
                        extra={
                            "operation_id": self.operation_id,
                            "task_name": task_name,
                            "dependencies": task.depends_on,
                        },
                    )
                    continue
            # 执行任务
            result = self._execute_single_task(task)
            self.task_results[task_name] = result
        return self.task_results

    def _execute_tasks_parallel(self) -> dict[str, TaskResult]:
        """并行执行任务（简化实现）"""
        self.logger.info(
            "Parallel execution not fully implemented, falling back to sequential",
            extra={"operation_id": self.operation_id},
        )
        return self._execute_tasks_sequential()

    def _execute_single_task(self, task: TaskConfig) -> TaskResult:
        """执行单个任务"""
        start_time = datetime.now()
        self.logger.info(
            "Executing task",
            extra={
                "operation_id": self.operation_id,
                "task_name": task.name,
                "operation_type": task.operation_type,
            },
        )
        try:
            # 获取操作实例
            if task.operation_type not in self.operation_map:
                raise ValueError(f"Unknown operation type: {task.operation_type}")
            operation_class = self.operation_map[task.operation_type]
            operation = operation_class(self.config)
            # 执行操作
            result = operation.execute(**task.parameters)
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            task_result = TaskResult(
                task_name=task.name,
                success=result.get("success", True),
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time,
                result=result,
            )
            self.logger.info(
                "Task completed successfully",
                extra={
                    "operation_id": self.operation_id,
                    "task_name": task.name,
                    "execution_time": execution_time,
                },
            )
            return task_result
        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            self.logger.error(
                "Task execution failed",
                extra={
                    "operation_id": self.operation_id,
                    "task_name": task.name,
                    "error": str(e),
                    "execution_time": execution_time,
                },
            )
            return TaskResult(
                task_name=task.name,
                success=False,
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time,
                result={},
                error=str(e),
            )

    def _generate_execution_summary(self) -> dict[str, Any]:
        """生成执行摘要"""
        total_tasks = len(self.task_results)
        successful_tasks = sum(1 for result in self.task_results.values() if result.success)
        failed_tasks = total_tasks - successful_tasks
        total_execution_time = sum(result.execution_time for result in self.task_results.values())
        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": ((successful_tasks / total_tasks * 100) if total_tasks > 0 else 0),
            "total_execution_time": total_execution_time,
            "average_execution_time": (total_execution_time / total_tasks if total_tasks > 0 else 0),
        }


# 便捷函数
def run_data_scripts(
    tasks: list[dict[str, Any]],
    parallel: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    便捷的数据脚本执行函数
    Args:
        tasks: 任务配置列表
        parallel: 是否并行执行
        config: 配置字典
    Returns:
        执行结果
    """
    runner = DataScriptRunner(config)
    return runner.execute(tasks=tasks, parallel=parallel)


def create_sample_config() -> dict[str, Any]:
    """创建示例配置"""
    return {
        "tasks": [
            {
                "name": "update_stock_basic_info",
                "operation_type": "stock_data_update",
                "parameters": {
                    "update_type": "basic_info",
                    "symbols": ["000001", "600519"],
                },
                "enabled": True,
                "max_retries": 3,
            },
            {
                "name": "update_stock_historical_data",
                "operation_type": "stock_data_update",
                "parameters": {
                    "update_type": "historical_data",
                    "symbols": ["000001", "600519"],
                    "start_date": "2025-10-01",
                    "end_date": "2025-10-12",
                },
                "enabled": True,
                "depends_on": ["update_stock_basic_info"],
                "max_retries": 3,
            },
            {
                "name": "validate_data_quality",
                "operation_type": "data_validation",
                "parameters": {"validation_types": ["completeness", "consistency", "quality"]},
                "enabled": True,
                "depends_on": ["update_stock_historical_data"],
                "max_retries": 1,
            },
        ]
    }


if __name__ == "__main__":
    # 示例用法
    sample_config = create_sample_config()
    result = run_data_scripts(tasks=sample_config["tasks"], parallel=False)
    print("Data script execution result:")
    print(json.dumps(result, indent=2, default=str))
