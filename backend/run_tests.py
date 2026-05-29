#!/usr/bin/env python3
"""
测试运行脚本
提供便捷的测试运行命令
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """运行命令"""
    print(f"🚀 运行命令: {' '.join(cmd)}")

    try:
        # 统一补齐 PYTHONPATH，避免在 backend 目录执行时无法导入 `backend.*`
        workdir = Path(cwd or os.getcwd()).resolve()
        project_root = workdir.parent if workdir.name == "backend" else workdir
        pythonpath_entries = [str(project_root), str(project_root / "backend")]
        existing_pythonpath = os.getenv("PYTHONPATH", "")
        if existing_pythonpath:
            pythonpath_entries.append(existing_pythonpath)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return result.returncode

    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {e}")
        if e.stdout:
            print(f"标准输出: {e.stdout}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        return e.returncode


def install_dependencies():
    """安装测试依赖"""
    print("📦 安装测试依赖...")

    dependencies = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-xdist",
        "pytest-mock",
        "httpx",
        "fastapi[all]",
    ]

    for dep in dependencies:
        print(f"  安装 {dep}...")
        run_command([sys.executable, "-m", "pip", "install", dep])


def run_unit_tests():
    """运行单元测试"""
    print("🧪 运行单元测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--ignore=tests/manual",
            "-v",
            "--tb=short",
        ]
    )


def run_integration_tests():
    """运行集成测试"""
    print("🔗 运行集成测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "integration",
            "-v",
            "--tb=short",
        ]
    )


def run_e2e_tests():
    """运行端到端测试"""
    print("🌐 运行端到端测试...")
    return run_command([sys.executable, "-m", "pytest", "tests/", "-m", "e2e", "-v", "--tb=short"])


def run_api_service_tests():
    """运行API服务测试（兼容旧 marker: api_gateway）"""
    print("🌐 运行API服务测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "api_service or api_gateway",
            "-v",
            "--tb=short",
        ]
    )


def run_service_communication_tests():
    """运行服务通信测试"""
    print("📡 运行服务通信测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "service_communication",
            "-v",
            "--tb=short",
        ]
    )


def run_all_tests():
    """运行所有测试"""
    print("🎯 运行所有测试...")
    return run_command([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"])


def run_coverage_tests():
    """运行测试覆盖率检查"""
    print("📊 运行测试覆盖率检查...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=backend",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=80",
        ]
    )


def run_performance_tests():
    """运行性能测试"""
    print("⚡ 运行性能测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "performance",
            "-v",
            "--tb=short",
        ]
    )


def run_parallel_tests():
    """并行运行测试"""
    print("🚀 并行运行测试...")
    return run_command([sys.executable, "-m", "pytest", "tests/", "-n", "auto", "-v", "--tb=short"])


def run_trade_long_short_mvp_tests():
    """运行 QMT 多空 MVP 关键链路测试（CI 必跑）"""
    print("📌 运行 QMT 多空 MVP 关键链路测试...")
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "services/tests/test_qmt_agent_async_reconcile.py",
            "services/tests/test_trade_long_short_risk_and_bridge.py",
            "services/tests/test_trade_long_short_integration_chain.py",
            "services/tests/test_trade_trading_precheck.py",
            "-q",
            "--no-cov",
        ]
    )


def generate_test_report():
    """生成测试报告"""
    print("📄 生成测试报告...")

    # 确保报告目录存在
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 生成HTML报告
    run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--html=tests/reports/report.html",
            "--self-contained-html",
        ]
    )

    # 生成覆盖率报告
    run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=backend",
            "--cov-report=html:tests/reports/coverage",
            "--cov-report=xml:tests/reports/coverage.xml",
        ]
    )


def check_test_environment():
    """检查测试环境"""
    print("🔍 检查测试环境...")

    # 检查Python版本
    python_version = sys.version_info
    print(f"  Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version < (3, 8):
        print("❌ Python版本过低，需要3.8或更高版本")
        return False

    # 检查pytest
    try:
        import pytest

        print(f"  pytest版本: {pytest.__version__}")
    except ImportError:
        print("❌ pytest未安装")
        return False

    # 检查测试文件
    test_files = list(Path("tests").glob("**/test_*.py"))
    if not test_files:
        print("❌ 未找到测试文件")
        return False

    print(f"  找到 {len(test_files)} 个测试文件")

    # 检查配置文件
    config_files = ["../pyproject.toml", "pyproject.toml", "pytest.ini", "conftest.py", "tests/conftest.py"]

    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            print(f"  配置文件: {config_file} ✓")
        else:
            # 记录失败但不一定要中断
            pass

    print("✅ 测试环境检查完成")
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="QuantMind 测试运行器")

    parser.add_argument(
        "command",
        choices=[
            "check",
            "install",
            "unit",
            "integration",
            "e2e",
            "api-service",
            "api-gateway",
            "service-comm",
            "trade-long-short",
            "all",
            "coverage",
            "performance",
            "parallel",
            "report",
        ],
        help="测试命令",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    parser.add_argument("--no-deps", action="store_true", help="跳过依赖安装")

    args = parser.parse_args()

    # 设置项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # 显示欢迎信息
    print("🧪 QuantMind 测试运行器")
    print("=" * 50)

    # 检查测试环境
    if not check_test_environment():
        print("\n❌ 测试环境检查失败")
        return 1

    # 安装依赖
    if not args.no_deps and args.command != "check":
        print("\n")
        install_dependencies()

    # 执行命令
    print("\n")
    exit_code = 0

    if args.command == "check":
        exit_code = check_test_environment()
    elif args.command == "install":
        exit_code = 0  # install_dependencies already handled
    elif args.command == "unit":
        exit_code = run_unit_tests()
    elif args.command == "integration":
        exit_code = run_integration_tests()
    elif args.command == "e2e":
        exit_code = run_e2e_tests()
    elif args.command == "api-service":
        exit_code = run_api_service_tests()
    elif args.command == "api-gateway":
        print("⚠️ 命令 `api-gateway` 已废弃，请改用 `api-service`")
        exit_code = run_api_service_tests()
    elif args.command == "service-comm":
        exit_code = run_service_communication_tests()
    elif args.command == "trade-long-short":
        exit_code = run_trade_long_short_mvp_tests()
    elif args.command == "all":
        exit_code = run_all_tests()
    elif args.command == "coverage":
        exit_code = run_coverage_tests()
    elif args.command == "performance":
        exit_code = run_performance_tests()
    elif args.command == "parallel":
        exit_code = run_parallel_tests()
    elif args.command == "report":
        exit_code = generate_test_report()
    else:
        print(f"❌ 未知命令: {args.command}")
        exit_code = 1

    # 显示结果
    print("\n" + "=" * 50)
    if exit_code == 0:
        print("✅ 测试运行完成")
    else:
        print("❌ 测试运行失败")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
