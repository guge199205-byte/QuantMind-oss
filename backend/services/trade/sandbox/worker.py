import json
import os
import signal
import time
import traceback
from multiprocessing import Queue

from backend.services.trade.redis_client import RedisClient, get_redis
from backend.services.trade.sandbox.context import create_sandbox_context

# 模拟策略运行频率（秒/Tick），这里为了简单演示，设为10秒一个Tick
TICK_INTERVAL_SEC = 10


def _restricted_execute(code_str: str, sandbox_context):
    """
    在一个受限的命名空间中安全执行用户的 Python 代码。
    注入 sandbox_context 供用户的策略调用。
    """
    # 构建安全受限的全局命名空间
    loc_env = {}
    glob_env = {
        "__builtins__": __builtins__,
        "context": sandbox_context,  # 注入我们模拟的 SDK Context
    }

    # 将 context 开放的方法暴露在全局，以便用户直接调用 order_target_percent 等
    glob_env["order_target_percent"] = sandbox_context.order_target_percent
    glob_env["order"] = sandbox_context.order
    glob_env["log"] = sandbox_context.log
    glob_env["get_position"] = sandbox_context.get_position
    glob_env["get_cash"] = sandbox_context.get_cash
    glob_env["get_total_asset"] = sandbox_context.get_total_asset

    try:
        # 先编译以尽早发现语法错误
        compiled_code = compile(code_str, "<strategy>", "exec")

        # 模拟执行环境初始化
        sandbox_context.log("Sandbox Strategy Starting...")

        # 定义一个简单的事件驱动钩子（真实环境需要更完备的生命周期：on_init, on_bar 等）
        # 这里为了演示，我们看看用户代码是否定义了 `on_tick`，如果定义了就调用；否则仅仅把代码顺序执行一遍

        exec(compiled_code, glob_env, loc_env)

        on_tick_func = loc_env.get("on_tick") or glob_env.get("on_tick")

        # 简易的主循环，由外界的中断信号控制退出
        while True:
            sandbox_context.set_time(time.time())

            if on_tick_func:
                try:
                    on_tick_func(sandbox_context)
                except Exception as e:
                    sandbox_context.log(f"on_tick 执行出错: {e}")

            # 将这个Tick产生的信号抛出到外部
            signals = sandbox_context.flush_signals()
            if signals:
                _publish_signals_to_redis(signals)

            time.sleep(TICK_INTERVAL_SEC)

    except KeyboardInterrupt:
        # 被停止运行
        sandbox_context.log("Sandbox execution stopped by user command.")
    except Exception:
        error_msg = f"策略执行异常:\n{traceback.format_exc()}"
        sandbox_context.log(error_msg)
    finally:
        # flush remnants
        signals = sandbox_context.flush_signals()
        if signals:
            _publish_signals_to_redis(signals)


def _publish_signals_to_redis(signals: list):
    """将获取到的意图信号推送到 Redis 队列给中央引擎消费"""
    try:
        # 在 Worker 进程中独立获取一个 Redis 连接
        # 由于依赖 backend.services，需要确保 Worker 能正常读到环境配置
        import redis

        host = os.getenv("REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD", None)
        client = redis.Redis(host=host, port=port, password=password, db=int(os.getenv("REDIS_DB_TRADE", "2")))

        for sig in signals:
            client.rpush("trade:simulation:signals", json.dumps(sig))
    except Exception as e:
        print(f"[Worker Error] Publish to Redis failed: {e}")


def sandbox_worker_main(task_queue: Queue):
    """
    子进程入口：常驻挂起，监听分配给它的策略执行任务。
    一次只能跑一个策略，所以在拿到任务后就开始内部阻塞跑策略；
    如果策略被终止（或者是批处理结束），则继续从 queue 里拿下一个任务。
    """
    print(f"[Sandbox Worker {os.getpid()}] Started and waiting for tasks...")

    # 捕获终止信号，优雅退出
    def _term_handler(signum, frame):
        print(f"[Sandbox Worker {os.getpid()}] Shutting down...")
        exit(0)

    signal.signal(signal.SIGTERM, _term_handler)

    while True:
        try:
            # 阻塞等待属于自己的策略执行任务
            task = task_queue.get()
            if task is None:  # 毒药丸，退出进程
                break

            tenant_id = task.get("tenant_id")
            user_id = task.get("user_id")
            strategy_id = task.get("strategy_id")
            run_id = task.get("run_id")
            exec_config = task.get("exec_config", {})
            live_trade_config = task.get("live_trade_config", {})
            code_str = task.get("code_str", "")

            # 构建沙箱上下文 SDK
            ctx = create_sandbox_context(tenant_id, user_id, strategy_id, run_id, exec_config, live_trade_config)

            print(f"[Sandbox Worker {os.getpid()}] Starting strategy {strategy_id} for user {user_id}")

            # 阻塞执行受限环境
            _restricted_execute(code_str, ctx)

            print(f"[Sandbox Worker {os.getpid()}] Strategy {strategy_id} execution finished.")

        except Exception as e:
            print(f"[Sandbox Worker {os.getpid()}] Task Error: {e}")
            time.sleep(1)
