#!/usr/bin/env python3
"""
QuantMind服务依赖管理器
提供服务依赖分析、启动顺序计算和批量管理功能
"""

from config_manager import ConfigManager
import logging
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

# 添加配置管理器路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ServiceInfo:
    """服务信息"""

    name: str
    display_name: str
    description: str
    port: int
    dependencies: List[str]
    health_check: Dict
    startup_order: int


@dataclass
class StartupPlan:
    """启动计划"""

    steps: List[List[str]]
    total_services: int
    estimated_time: int  # 预估启动时间（秒）


class DependencyManager:
    """服务依赖管理器"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = self._setup_logger()
        self.services: Dict[str, ServiceInfo] = {}
        self.startup_groups: Dict[str, Dict] = {}
        self.load_dependencies()

    def _setup_logger(self) -> logging.Logger:
        """设置日志器"""
        logger = logging.getLogger("dependency_manager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def load_dependencies(self):
        """加载服务依赖配置"""
        try:
            dependencies_file = (
                Path(__file__).parent.parent / "services" /
                "service_dependencies.yaml"
            )

            if dependencies_file.exists():
                with open(dependencies_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                # 加载服务信息
                for name, info in config.get("services", {}).items():
                    self.services[name] = ServiceInfo(
                        name=name,
                        display_name=info.get("display_name", name),
                        description=info.get("description", ""),
                        port=info.get("port", 0),
                        dependencies=info.get("dependencies", []),
                        health_check=info.get("health_check", {}),
                        startup_order=info.get("startup_order", 999),
                    )

                # 加载启动组
                self.startup_groups = config.get("startup_groups", {})

                self.logger.info(
                    f"Loaded {len(self.services)} services and {len(self.startup_groups)} startup groups"
                )
            else:
                self.logger.warning(
                    f"Dependencies file not found: {dependencies_file}")

        except Exception as e:
            self.logger.error(f"Failed to load dependencies: {e}")

    def get_startup_order(self, services: Optional[List[str]] = None) -> StartupPlan:
        """计算服务启动顺序"""
        if services is None:
            services = list(self.services.keys())

        # 构建依赖图
        dependency_graph = self._build_dependency_graph(services)

        # 拓扑排序
        sorted_services = self._topological_sort(dependency_graph)

        # 分组启动步骤
        steps = self._group_startup_steps(sorted_services, dependency_graph)

        # 计算预估时间
        environment = self.config_manager.environment
        startup_delay = self._get_startup_delay(environment)
        estimated_time = (
            len(steps) * startup_delay + len(services) * 2
        )  # 每个服务2秒启动时间

        return StartupPlan(
            steps=steps, total_services=len(services), estimated_time=estimated_time
        )

    def _build_dependency_graph(self, services: List[str]) -> Dict[str, Set[str]]:
        """构建依赖图"""
        graph = defaultdict(set)

        for service in services:
            if service in self.services:
                for dep in self.services[service].dependencies:
                    if dep in services:  # 只考虑指定范围内的依赖
                        graph[service].add(dep)

        return dict(graph)

    def _topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """拓扑排序"""
        in_degree = defaultdict(int)
        all_nodes = set(graph.keys())

        # 计算入度
        for node, deps in graph.items():
            for dep in deps:
                in_degree[dep] += 1
                all_nodes.add(dep)

        # 找到入度为0的节点
        queue = deque([node for node in all_nodes if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # 更新依赖该节点的其他节点的入度
            if node in graph:
                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # 检查是否有循环依赖
        if len(result) != len(all_nodes):
            remaining = all_nodes - set(result)
            raise ValueError(
                f"Circular dependency detected among services: {remaining}"
            )

        return result

    def _group_startup_steps(
        self, sorted_services: List[str], graph: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """将服务分组为启动步骤"""
        steps = []
        remaining_services = set(sorted_services)

        while remaining_services:
            # 找到当前可以启动的服务（依赖已满足）
            current_step = []
            for service in sorted_services:
                if service in remaining_services:
                    deps = graph.get(service, set())
                    if not deps.intersection(remaining_services):
                        current_step.append(service)

            if not current_step:
                # 如果没有可启动的服务，说明存在循环依赖
                remaining_list = list(remaining_services)
                current_step = [remaining_list[0]]  # 强制启动一个服务
                self.logger.warning(
                    f"Forcing startup of service {current_step[0]} to break potential deadlock"
                )

            steps.append(current_step)
            remaining_services -= set(current_step)

        return steps

    def _get_startup_delay(self, environment: str) -> int:
        """获取环境特定的启动延迟"""
        try:
            dependencies_file = (
                Path(__file__).parent.parent / "services" /
                "service_dependencies.yaml"
            )
            with open(dependencies_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            env_config = config.get("environments", {}).get(environment, {})
            return env_config.get("startup_delay", 3)
        except Exception:
            return 3  # 默认延迟

    def get_startup_plan(self, group_name: Optional[str] = None) -> StartupPlan:
        """获取启动计划"""
        if group_name and group_name in self.startup_groups:
            group_config = self.startup_groups[group_name]
            services = group_config["services"]

            # 递归处理依赖组
            all_services = set(services)
            for dep_group in group_config.get("dependencies", []):
                dep_plan = self.get_startup_plan(dep_group)
                all_services.update(dep_plan.steps[0])  # 依赖组的所有服务

            return self.get_startup_order(list(all_services))
        else:
            return self.get_startup_order()

    def check_dependencies(self, service_name: str) -> Dict[str, bool]:
        """检查服务依赖是否满足"""
        if service_name not in self.services:
            return {}

        service_info = self.services[service_name]
        dependency_status = {}

        for dep in service_info.dependencies:
            # 这里应该检查服务是否实际在运行
            # 简化版本，假设配置中的服务都是可用的
            dependency_status[dep] = dep in self.services

        return dependency_status

    def get_dependency_tree(self, service_name: str) -> Dict:
        """获取服务的依赖树"""

        def build_tree(name: str, visited: Set[str]) -> Dict:
            if name in visited:
                return {"name": name, "circular": True}

            if name not in self.services:
                return {"name": name, "missing": True}

            visited.add(name)
            service_info = self.services[name]

            return {
                "name": name,
                "display_name": service_info.display_name,
                "dependencies": [
                    build_tree(dep, visited.copy()) for dep in service_info.dependencies
                ],
                "port": service_info.port,
            }

        return build_tree(service_name, set())

    def validate_dependencies(self) -> List[str]:
        """验证所有服务依赖的有效性"""
        errors = []

        for service_name, service_info in self.services.items():
            # 检查依赖服务是否存在
            for dep in service_info.dependencies:
                if dep not in self.services:
                    errors.append(
                        f"Service '{service_name}' depends on missing service '{dep}'"
                    )

        # 检查循环依赖
        try:
            self.get_startup_order()
        except ValueError as e:
            errors.append(str(e))

        return errors

    def get_service_groups(self) -> Dict[str, List[str]]:
        """获取服务分组信息"""
        groups = {}

        for group_name, group_config in self.startup_groups.items():
            groups[group_name] = group_config["services"]

        return groups

    def analyze_impact(self, service_name: str) -> Dict[str, List[str]]:
        """分析服务变更的影响范围"""
        # 找到所有依赖该服务的其他服务
        dependents = []

        for name, service_info in self.services.items():
            if service_name in service_info.dependencies:
                dependents.append(name)

        # 递归分析传递依赖
        all_affected = set(dependents)
        for dependent in dependents:
            affected = self.analyze_impact(dependent)
            all_affected.update(affected.get("direct", []))
            all_affected.update(affected.get("indirect", []))

        return {
            "direct": dependents,
            "indirect": list(all_affected - set(dependents)),
            "all": list(all_affected),
        }


def main():
    """命令行工具入口"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="QuantMind服务依赖管理工具")
    parser.add_argument(
        "action",
        choices=["plan", "tree", "check", "validate", "groups", "impact"],
        help="要执行的操作",
    )
    parser.add_argument("--service", "-s", help="服务名称")
    parser.add_argument("--group", "-g", help="启动组名称")
    parser.add_argument(
        "--format",
        "-",
        choices=["yaml", "json", "table"],
        default="table",
        help="输出格式",
    )
    parser.add_argument("--environment", "-e", help="环境名称")

    args = parser.parse_args()

    # 设置环境
    if args.environment:
        import os

        os.environ["ENVIRONMENT"] = args.environment

    # 创建依赖管理器
    manager = DependencyManager()

    # 执行操作
    if args.action == "plan":
        plan = (
            manager.get_startup_plan(args.group)
            if args.group
            else manager.get_startup_plan()
        )

        if args.format == "json":
            print(
                json.dumps(
                    {
                        "steps": plan.steps,
                        "total_services": plan.total_services,
                        "estimated_time": plan.estimated_time,
                    },
                    indent=2,
                )
            )
        elif args.format == "yaml":
            print(
                yaml.dump(
                    {
                        "steps": plan.steps,
                        "total_services": plan.total_services,
                        "estimated_time": plan.estimated_time,
                    }
                )
            )
        else:
            print(
                f"启动计划（共{plan.total_services}个服务，预计{plan.estimated_time}秒）："
            )
            print("-" * 60)
            for i, step in enumerate(plan.steps, 1):
                print(f"步骤{i}: {', '.join(step)}")

    elif args.action == "tree":
        if not args.service:
            print("错误：需要指定服务名称")
            return 1

        tree = manager.get_dependency_tree(args.service)

        if args.format == "json":
            print(json.dumps(tree, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(tree))
        else:

            def print_tree(node, level=0):
                indent = "  " * level
                name = node["name"]
                display_name = node.get("display_name", name)
                port = node.get("port", "")

                if node.get("circular"):
                    print(f"{indent}{name} (循环依赖)")
                elif node.get("missing"):
                    print(f"{indent}{name} (缺失)")
                else:
                    print(f"{indent}{display_name} ({name}:{port})")

                for child in node.get("dependencies", []):
                    print_tree(child, level + 1)

            print_tree(tree)

    elif args.action == "check":
        if not args.service:
            print("错误：需要指定服务名称")
            return 1

        status = manager.check_dependencies(args.service)

        if args.format == "json":
            print(json.dumps(status, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(status))
        else:
            print(f"服务 '{args.service}' 依赖状态：")
            for dep, available in status.items():
                status_str = "✓" if available else "✗"
                print(f"  {status_str} {dep}")

    elif args.action == "validate":
        errors = manager.validate_dependencies()

        if errors:
            print("依赖验证失败：")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("所有服务依赖验证通过")

    elif args.action == "groups":
        groups = manager.get_service_groups()

        if args.format == "json":
            print(json.dumps(groups, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(groups))
        else:
            print("服务启动组：")
            for group_name, services in groups.items():
                print(f"  {group_name}: {', '.join(services)}")

    elif args.action == "impact":
        if not args.service:
            print("错误：需要指定服务名称")
            return 1

        impact = manager.analyze_impact(args.service)

        if args.format == "json":
            print(json.dumps(impact, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(impact))
        else:
            print(f"服务 '{args.service}' 影响分析：")
            print(f"  直接依赖: {', '.join(impact['direct'])}")
            print(f"  间接依赖: {', '.join(impact['indirect'])}")
            print(f"  总计影响: {len(impact['all'])} 个服务")

    return 0


if __name__ == "__main__":
    exit(main())
