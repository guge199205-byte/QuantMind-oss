#!/usr/bin/env python3
"""
统一路径管理模块
提供项目路径管理和导入配置功能
"""

import os
import sys
from pathlib import Path
from typing import List, Optional


class PathManager:
    """项目路径管理器"""

    def __init__(self):
        """初始化路径管理器"""
        self.project_root = self._detect_project_root()
        self.backend_root = self.project_root / "backend"
        self.shared_root = self.project_root / "backend" / "shared"
        self.initialized = False

    def _detect_project_root(self) -> Path:
        """检测项目根目录"""
        current = Path(__file__).parent

        # 向上查找包含特定文件的目录
        indicators = [
            "package.json",
            "docker-compose.yml",
            ".git",
            "backend",
            "electron",
        ]

        while current.parent != current:
            if any((current / indicator).exists() for indicator in indicators):
                return current
            current = current.parent

        # 如果没有找到，返回当前文件的上级目录
        return Path(__file__).parent.parent.parent

    def initialize_python_path(self, force: bool = False) -> None:
        """初始化Python路径

        Args:
            force: 是否强制重新初始化
        """
        if self.initialized and not force:
            return

        # 清理之前可能添加的路径
        self._cleanup_python_path()

        # 添加项目根目录到路径
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        # 添加backend目录到路径
        backend_root_str = str(self.backend_root)
        if backend_root_str not in sys.path:
            sys.path.insert(0, backend_root_str)

        # 添加shared目录到路径
        shared_root_str = str(self.shared_root)
        if shared_root_str not in sys.path:
            sys.path.insert(0, shared_root_str)

        self.initialized = True

    def _cleanup_python_path(self) -> None:
        """清理之前添加的路径"""
        paths_to_remove = [
            str(self.project_root),
            str(self.backend_root),
            str(self.shared_root),
        ]

        for path in paths_to_remove:
            if path in sys.path:
                sys.path.remove(path)

    def get_module_path(self, module_name: str) -> Path:
        """获取模块路径

        Args:
            module_name: 模块名称

        Returns:
            模块路径
        """
        # 支持不同类型的模块路径
        if module_name.startswith("backend."):
            # backend模块
            module_parts = module_name.split(".")
            return self.backend_root.joinpath(*module_parts[1:])
        elif module_name.startswith("shared."):
            # shared模块
            module_parts = module_name.split(".")
            return self.shared_root.joinpath(*module_parts[1:])
        else:
            # 相对路径或绝对路径
            return self.project_root / module_name

    def resolve_import_path(self, import_path: str, from_module: str = None) -> str:
        """解析导入路径

        Args:
            import_path: 导入路径
            from_module: 来源模块

        Returns:
            解析后的导入路径
        """
        # 如果是相对导入
        if import_path.startswith("."):
            if from_module:
                from_path = self.get_module_path(from_module)
                target_path = (from_path.parent / import_path).resolve()

                # 转换为相对于project_root的路径
                try:
                    relative_path = target_path.relative_to(self.project_root)
                    return str(relative_path).replace(os.sep, ".")
                except ValueError:
                    # 如果无法转换为相对路径，返回绝对路径
                    return str(target_path)

        # 如果是绝对导入，直接返回
        return import_path

    def get_service_import_path(self, service_name: str) -> str:
        """获取服务模块的导入路径

        Args:
            service_name: 服务名称

        Returns:
            导入路径
        """
        service_path = self.backend_root / service_name
        if service_path.exists():
            return f"backend.{service_name}"
        else:
            raise ValueError(f"Service {service_name} not found at {service_path}")

    def validate_module_import(self, module_name: str) -> bool:
        """验证模块是否可以导入

        Args:
            module_name: 模块名称

        Returns:
            是否可以导入
        """
        try:
            import importlib

            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def get_available_services(self) -> list[str]:
        """获取可用的服务列表

        Returns:
            服务名称列表
        """
        services = []
        if self.backend_root.exists():
            for item in self.backend_root.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    # 检查是否包含main.py
                    if (item / "main.py").exists():
                        services.append(item.name)
        return sorted(services)

    def create_import_config(self) -> dict:
        """创建导入配置

        Returns:
            导入配置字典
        """
        return {
            "project_root": str(self.project_root),
            "backend_root": str(self.backend_root),
            "shared_root": str(self.shared_root),
            "python_path": sys.path[:5],  # 只显示前5个路径
            "available_services": self.get_available_services(),
            "initialized": self.initialized,
        }

    def setup_environment_variables(self) -> None:
        """设置环境变量"""
        os.environ["PROJECT_ROOT"] = str(self.project_root)
        os.environ["BACKEND_ROOT"] = str(self.backend_root)
        os.environ["SHARED_ROOT"] = str(self.shared_root)


# 全局路径管理器实例
_path_manager: PathManager | None = None


def get_path_manager() -> PathManager:
    """获取全局路径管理器实例

    Returns:
        路径管理器实例
    """
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


def initialize_project_paths(force: bool = False) -> None:
    """初始化项目路径

    Args:
        force: 是否强制重新初始化
    """
    path_manager = get_path_manager()
    path_manager.initialize_python_path(force)
    path_manager.setup_environment_variables()


def auto_import(module_name: str, fallback=None):
    """自动导入模块的装饰器

    Args:
        module_name: 模块名称
        fallback: 导入失败时的回退值
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                __import__(module_name, fromlist=[func.__name__])
                return func(*args, **kwargs)
            except ImportError as e:
                if fallback is not None:
                    return fallback
                raise ImportError(f"Cannot import {module_name}: {e}")

        return wrapper

    return decorator


# 模块级别的便捷导入函数
def import_backend_module(service_name: str, module_name: str = "main"):
    """导入后端模块

    Args:
        service_name: 服务名称
        module_name: 模块名称

    Returns:
        导入的模块
    """
    full_module_name = f"backend.{service_name}.{module_name}"
    try:
        return __import__(full_module_name, fromlist=[module_name])
    except ImportError as e:
        raise ImportError(f"Cannot import backend module {full_module_name}: {e}")


def import_shared_module(module_name: str):
    """导入共享模块

    Args:
        module_name: 模块名称

    Returns:
        导入的模块
    """
    full_module_name = f"backend.shared.{module_name}"
    try:
        return __import__(full_module_name, fromlist=[module_name])
    except ImportError as e:
        raise ImportError(f"Cannot import shared module {full_module_name}: {e}")


# 初始化路径（在模块导入时自动执行）
initialize_project_paths()
