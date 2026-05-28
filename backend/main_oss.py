"""
QuantMind OSS Edition - Unified Service Entry Point
单镜像运行所有后端服务

服务端口分配:
- API Gateway: 8000 (主入口)
- Engine: 8001 (回测引擎)
- Trade: 8002 (交易服务)
- Stream: 8003 (实时行情)
"""

import asyncio
import logging
import multiprocessing as mp
import os
import sys
from typing import Optional

try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass

from backend.shared.logging_config import setup_logging

setup_logging(service_name="quantmind-oss")
logger = logging.getLogger(__name__)

# ── Qlib 数据目录修复 ──
# features_real 是实际数据目录，Qlib 期望 features/
_qlib_cn = "/app/db/qlib_data/cn_data"
if os.path.isdir(_qlib_cn):
    _features = os.path.join(_qlib_cn, "features")
    _features_real = os.path.join(_qlib_cn, "features_real")
    if os.path.isdir(_features_real) and not os.path.isdir(_features):
        os.symlink(_features_real, _features)
        logger.info("Created symlink: %s -> %s", _features, _features_real)


def get_workers_config() -> dict:
    """获取各服务的 worker 数量配置"""
    import os
    # OSS 默认保持 engine 单 worker。
    # 原因：AI-IDE 执行任务状态保存在进程内存中，多 worker 会导致
    # /start 与 /execute/logs/{job_id} 命中不同进程，返回 404 Job not found。
    default_workers = {
        "api": 1,
        "engine": 1,
        "trade": 1,
        "stream": 1,
    }
    # 支持环境变量覆盖
    return {
        "api": int(os.getenv("API_WORKERS", default_workers["api"])),
        "engine": int(os.getenv("ENGINE_WORKERS", default_workers["engine"])),
        "trade": int(os.getenv("TRADE_WORKERS", default_workers["trade"])),
        "stream": int(os.getenv("STREAM_WORKERS", default_workers["stream"])),
    }


def get_service_ports() -> dict:
    """获取服务端口配置"""
    return {
        "api": int(os.getenv("API_PORT", "8000")),
        "engine": int(os.getenv("ENGINE_PORT", "8001")),
        "trade": int(os.getenv("TRADE_PORT", "8002")),
        "stream": int(os.getenv("STREAM_PORT", "8003")),
    }


def run_api_service(port: int, workers: int = 1):
    """运行 API 服务"""
    import uvicorn

    logger.info(f"Starting API service on port {port} with {workers} workers")
    uvicorn.run(
        "backend.services.api.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        access_log=False,
    )


def run_engine_service(port: int, workers: int = 4):
    """运行 Engine 服务"""
    import uvicorn

    logger.info(f"Starting Engine service on port {port} with {workers} workers")
    uvicorn.run(
        "backend.services.engine.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        access_log=False,
    )


def run_trade_service(port: int, workers: int = 1):
    """运行 Trade 服务"""
    import uvicorn

    logger.info(f"Starting Trade service on port {port} with {workers} workers")
    uvicorn.run(
        "backend.services.trade.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        access_log=False,
    )


def run_stream_service(port: int, workers: int = 1):
    """运行 Stream 服务"""
    import uvicorn

    logger.info(f"Starting Stream service on port {port} with {workers} workers")
    uvicorn.run(
        "backend.services.stream.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        access_log=False,
    )


def run_single_service(service_name: str, port: int, workers: int = 1):
    """运行单个服务（用于调试或按需启动）"""
    service_runners = {
        "api": run_api_service,
        "engine": run_engine_service,
        "trade": run_trade_service,
        "stream": run_stream_service,
    }

    if service_name not in service_runners:
        raise ValueError(
            f"Unknown service: {service_name}. Available: {list(service_runners.keys())}"
        )

    service_runners[service_name](port, workers)


def run_celery_worker():
    """运行 Celery Worker（处理异步回测任务）"""
    from celery import concurrency
    from backend.services.engine.qlib_app.celery_config import celery_app

    logger.info("Starting Celery Worker for async backtest tasks")
    # 使用 solo 模式单进程执行，避免多进程复杂度
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=1",
        "--pool=solo",
    ])


def run_all_services():
    """运行所有服务（多进程模式 + 子进程死亡自动重启 + 健康检查看门狗）"""
    import time
    import urllib.request
    import urllib.error

    ports = get_service_ports()
    workers_config = get_workers_config()

    services = [
        ("api", run_api_service, (ports["api"], workers_config["api"])),
        ("engine", run_engine_service, (ports["engine"], workers_config["engine"])),
        ("trade", run_trade_service, (ports["trade"], workers_config["trade"])),
        ("stream", run_stream_service, (ports["stream"], workers_config["stream"])),
        ("celery", run_celery_worker, ()),
    ]

    # name -> (runner, args, process, restart_count, last_restart_ts, health_failures)
    state: dict = {}

    def _spawn(name: str, runner, args: tuple):
        p = mp.Process(target=runner, args=args, name=f"quantmind-{name}")
        p.start()
        state[name] = {
            "runner": runner,
            "args": args,
            "process": p,
            "restarts": state.get(name, {}).get("restarts", 0),
            "last_restart": time.time(),
            "health_failures": 0,
        }
        return p

    for name, runner, args in services:
        p = _spawn(name, runner, args)
        if name == "celery":
            logger.info(f"Started celery worker (PID: {p.pid})")
        else:
            port, workers = args
            logger.info(f"Started {name} service (PID: {p.pid}) on port {port} with {workers} workers")

    logger.info("=" * 60)
    logger.info("QuantMind OSS Edition - All services started")
    logger.info(f"  API Gateway:  http://localhost:{ports['api']}")
    logger.info(f"  Engine:       http://localhost:{ports['engine']}")
    logger.info(f"  Trade:        http://localhost:{ports['trade']}")
    logger.info(f"  Stream:       http://localhost:{ports['stream']}")
    logger.info("=" * 60)

    # Supervision loop: detect dead/zombie children and respawn with exponential-backoff cap
    MAX_RESTARTS_PER_WINDOW = 5
    RESTART_WINDOW_SEC = 300  # 5 min sliding window
    HEALTH_CHECK_INTERVAL = 30  # seconds between health checks
    HEALTH_TIMEOUT = 10  # seconds to wait for health response
    MAX_HEALTH_FAILURES = 2  # consecutive failures before restart
    SHUTTING_DOWN = False
    last_health_check = time.time()
    startup_grace_sec = 60  # skip health checks during initial startup

    def _check_service_health(name: str, port: int) -> bool:
        """Check if a service responds to /health. Returns True if healthy."""
        try:
            url = f"http://127.0.0.1:{port}/health"
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT)
            return resp.status == 200
        except Exception:
            return False

    def _restart_service(name: str, info: dict, reason: str):
        """Kill and restart a service."""
        p = info["process"]
        logger.error(f"🔴 {name} service {reason}, restarting...")
        try:
            p.terminate()
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
                p.join(timeout=2)
        except Exception:
            pass

        now = time.time()
        if now - info["last_restart"] > RESTART_WINDOW_SEC:
            info["restarts"] = 0

        if info["restarts"] >= MAX_RESTARTS_PER_WINDOW:
            logger.error(
                f"⛔ {name} crashed too many times "
                f"({info['restarts']}/{MAX_RESTARTS_PER_WINDOW} in {RESTART_WINDOW_SEC}s), "
                f"not restarting. Manual intervention required."
            )
            return

        info["restarts"] += 1
        new_p = _spawn(name, info["runner"], info["args"])
        state[name]["restarts"] = info["restarts"]
        logger.info(f"♻️  Restarted {name} service (new PID: {new_p.pid})")

    try:
        while not SHUTTING_DOWN:
            time.sleep(3)
            now = time.time()

            for name, info in list(state.items()):
                p = info["process"]
                # exitcode is None while alive; set when child exits (even zombie reaped here)
                if not p.is_alive() or p.exitcode is not None:
                    exit_code = p.exitcode
                    try:
                        p.join(timeout=1)
                    except Exception:
                        pass

                    if now - info["last_restart"] > RESTART_WINDOW_SEC:
                        info["restarts"] = 0

                    if info["restarts"] >= MAX_RESTARTS_PER_WINDOW:
                        logger.error(
                            f"⛔ {name} crashed too many times "
                            f"({info['restarts']}/{MAX_RESTARTS_PER_WINDOW} in {RESTART_WINDOW_SEC}s), "
                            f"not restarting. Manual intervention required."
                        )
                        continue

                    info["restarts"] += 1
                    logger.error(
                        f"⚠️  {name} service died (exitcode={exit_code}), "
                        f"respawning [attempt {info['restarts']}/{MAX_RESTARTS_PER_WINDOW}]..."
                    )
                    new_p = _spawn(name, info["runner"], info["args"])
                    state[name]["restarts"] = info["restarts"]
                    logger.info(f"♻️  Restarted {name} service (new PID: {new_p.pid})")

            # Health check watchdog (runs every HEALTH_CHECK_INTERVAL seconds, after startup grace)
            if now - last_health_check >= HEALTH_CHECK_INTERVAL and (now - state[list(state.keys())[0]]["last_restart"]) > startup_grace_sec:
                last_health_check = now
                for name, info in list(state.items()):
                    if name == "celery":
                        continue  # celery has no HTTP health endpoint
                    p = info["process"]
                    if not p.is_alive():
                        continue  # already handled by dead-process logic above

                    port_key = name
                    port = ports.get(port_key)
                    if not port:
                        continue

                    if _check_service_health(name, port):
                        if info.get("health_failures", 0) > 0:
                            logger.info(f"✅ {name} service recovered (port {port})")
                        info["health_failures"] = 0
                    else:
                        info["health_failures"] = info.get("health_failures", 0) + 1
                        logger.warning(
                            f"⚠️  {name} health check failed "
                            f"({info['health_failures']}/{MAX_HEALTH_FAILURES})"
                        )
                        if info["health_failures"] >= MAX_HEALTH_FAILURES:
                            _restart_service(name, info, "unresponsive to health checks")
    except KeyboardInterrupt:
        SHUTTING_DOWN = True
        logger.info("Shutting down all services...")
        for name, info in state.items():
            p = info["process"]
            if p.is_alive():
                p.terminate()
                logger.info(f"Terminated {name} service")

        for name, info in state.items():
            p = info["process"]
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
                logger.warning(f"Force killed {name} service")


def main():
    """主入口"""
    service_mode = os.getenv("SERVICE_MODE", "all").lower().strip()
    ports = get_service_ports()
    workers_config = get_workers_config()

    logger.info(f"QuantMind OSS Edition - Service Mode: {service_mode}")

    if service_mode == "all":
        run_all_services()
    elif service_mode in ("api", "engine", "trade", "stream"):
        run_single_service(service_mode, ports[service_mode], workers_config[service_mode])
    else:
        logger.error(f"Unknown SERVICE_MODE: {service_mode}")
        logger.info("Valid modes: all, api, engine, trade, stream")
        sys.exit(1)


if __name__ == "__main__":
    main()
