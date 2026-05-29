#!/usr/bin/env python3
"""
AlertManager 系统管理脚本
启动、停止、重启告警系统
"""

import subprocess
import sys
import time
from pathlib import Path

import requests


class AlertManagerManager:
    """AlertManager 管理器"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.compose_file = self.project_root / "docker-compose.monitoring.yml"

    def start_monitoring_stack(self):
        """启动完整监控栈"""
        print("=" * 60)
        print("启动监控系统...")
        print("=" * 60)

        try:
            # 启动监控服务
            subprocess.run(
                ["docker-compose", "-", str(self.compose_file), "up", "-d"], check=True
            )

            print("\n✅ 监控服务启动中...")
            print("\n等待服务就绪...")
            time.sleep(10)

            self.check_services()

        except subprocess.CalledProcessError as e:
            print(f"\n❌ 启动失败: {e}")
            sys.exit(1)

    def stop_monitoring_stack(self):
        """停止监控栈"""
        print("=" * 60)
        print("停止监控系统...")
        print("=" * 60)

        try:
            subprocess.run(
                ["docker-compose", "-", str(self.compose_file), "down"], check=True
            )

            print("\n✅ 监控服务已停止")

        except subprocess.CalledProcessError as e:
            print(f"\n❌ 停止失败: {e}")
            sys.exit(1)

    def restart_monitoring_stack(self):
        """重启监控栈"""
        print("=" * 60)
        print("重启监控系统...")
        print("=" * 60)

        self.stop_monitoring_stack()
        time.sleep(3)
        self.start_monitoring_stack()

    def start_webhook_service(self):
        """启动 Webhook 服务"""
        print("=" * 60)
        print("启动 Webhook 服务...")
        print("=" * 60)

        webhook_script = self.project_root / "backend" / "alertmanager_webhook.py"

        try:
            subprocess.Popen([sys.executable, str(webhook_script)])

            print("\n✅ Webhook 服务启动中...")
            print("   监听端口: 8016")
            print("   日志文件: logs/alertmanager-webhook.log")

        except Exception as e:
            print(f"\n❌ 启动 Webhook 失败: {e}")

    def check_services(self):
        """检查服务状态"""
        print("\n" + "=" * 60)
        print("检查服务状态...")
        print("=" * 60 + "\n")

        services = {
            "Prometheus": "http://localhost:9090/-/healthy",
            "AlertManager": "http://localhost:9093/-/healthy",
            "Grafana": "http://localhost:3001/api/health",
            "Node Exporter": "http://localhost:9100/metrics",
            "Postgres Exporter": "http://localhost:9187/metrics",
            "Redis Exporter": "http://localhost:9121/metrics",
        }

        all_healthy = True

        for name, url in services.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {name:20} 运行正常")
                else:
                    print(f"⚠️  {name:20} 状态异常 ({response.status_code})")
                    all_healthy = False
            except Exception:
                print(f"❌ {name:20} 无法连接")
                all_healthy = False

        if all_healthy:
            print("\n✅ 所有服务运行正常")
            self.print_access_info()
        else:
            print("\n⚠️  部分服务异常，请检查日志")

    def print_access_info(self):
        """打印访问信息"""
        print("\n" + "=" * 60)
        print("访问地址")
        print("=" * 60)
        print("Prometheus:    http://localhost:9090")
        print("AlertManager:  http://localhost:9093")
        print("Grafana:       http://localhost:3001")
        print("  - 用户名: admin")
        print("  - 密码: admin_pass_2025")
        print("\nWebhook API:   http://localhost:8016")
        print("  - 健康检查: /health")
        print("  - 统计信息: /stats")
        print("=" * 60)

    def view_logs(self, service: str):
        """查看服务日志"""
        print(f"查看 {service} 日志...")

        try:
            subprocess.run(
                [
                    "docker-compose",
                    "-",
                    str(self.compose_file),
                    "logs",
                    "-",
                    "--tail=100",
                    service,
                ]
            )
        except KeyboardInterrupt:
            print("\n已停止查看日志")

    def reload_prometheus_config(self):
        """重载 Prometheus 配置"""
        print("重载 Prometheus 配置...")

        try:
            response = requests.post("http://localhost:9090/-/reload")
            if response.status_code == 200:
                print("✅ Prometheus 配置已重载")
            else:
                print(f"❌ 重载失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 重载失败: {e}")

    def reload_alertmanager_config(self):
        """重载 AlertManager 配置"""
        print("重载 AlertManager 配置...")

        try:
            response = requests.post("http://localhost:9093/-/reload")
            if response.status_code == 200:
                print("✅ AlertManager 配置已重载")
            else:
                print(f"❌ 重载失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 重载失败: {e}")


def print_usage():
    """打印使用说明"""
    print("""
AlertManager 管理脚本

使用方法:
    python manage_alertmanager.py [command]

命令:
    start       - 启动监控系统
    stop        - 停止监控系统
    restart     - 重启监控系统
    status      - 检查服务状态
    webhook     - 启动 Webhook 服务
    logs        - 查看服务日志 (需要指定服务名)
    reload-prom - 重载 Prometheus 配置
    reload-am   - 重载 AlertManager 配置
    help        - 显示此帮助信息

示例:
    python manage_alertmanager.py start
    python manage_alertmanager.py logs prometheus
    python manage_alertmanager.py reload-prom
    """)


def main():
    manager = AlertManagerManager()

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        manager.start_monitoring_stack()
    elif command == "stop":
        manager.stop_monitoring_stack()
    elif command == "restart":
        manager.restart_monitoring_stack()
    elif command == "status":
        manager.check_services()
    elif command == "webhook":
        manager.start_webhook_service()
    elif command == "logs":
        if len(sys.argv) < 3:
            print("❌ 请指定服务名，例如: logs prometheus")
            sys.exit(1)
        manager.view_logs(sys.argv[2])
    elif command == "reload-prom":
        manager.reload_prometheus_config()
    elif command == "reload-am":
        manager.reload_alertmanager_config()
    elif command == "help":
        print_usage()
    else:
        print(f"❌ 未知命令: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
