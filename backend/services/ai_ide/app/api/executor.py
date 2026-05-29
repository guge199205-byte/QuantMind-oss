import ast
import asyncio
import json
import logging
import os
import re
import sys
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-IDE-Executor")

router = APIRouter()

jobs = {}


class StartRequest(BaseModel):
    filename: str


class RunTmpRequest(BaseModel):
    content: str
    filename: str


def _load_workspace_root_from_config() -> str | None:
    data_dir = os.getenv("AI_IDE_DATA_DIR")
    if not data_dir:
        return None
    config_path = os.path.join(data_dir, "config.json")
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        root_path = str(data.get("root_path") or "").strip()
        if root_path and os.path.isdir(root_path):
            return os.path.abspath(root_path)
    except Exception as exc:
        logger.warning("Failed to load AI-IDE root_path from config: %s", exc)
    return None


def get_project_root():
    workspace_root = _load_workspace_root_from_config()
    if workspace_root:
        return workspace_root
    root = os.getenv("AI_IDE_PROJECT_ROOT")
    if not root:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    return os.path.abspath(root)


@router.post("/start")
async def start_execution(request: StartRequest):
    project_root = get_project_root()

    # 路径查找优先级：
    # 1. 绝对路径
    # 2. 相对于项目根目录
    # 3. 常见的策略子目录
    possible_paths = [
        request.filename,
        os.path.join(project_root, request.filename),
        os.path.join(project_root, "user_strategies", request.filename),
        os.path.join(project_root, "backend/user_strategies", request.filename),
    ]

    full_path = None
    for p in possible_paths:
        abs_p = os.path.abspath(p)
        if os.path.exists(abs_p) and os.path.isfile(abs_p):
            full_path = abs_p
            break

    if not full_path:
        # 最后尝试模糊搜索 (处理某些编码或路径深度问题)
        logger.warning(f"File not found in primary paths: {request.filename}. Attempting search...")
        for root, dirs, files in os.walk(project_root):
            if request.filename in files:
                full_path = os.path.join(root, request.filename)
                break

    if not full_path:
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "queue": asyncio.Queue()}

    asyncio.create_task(run_process(job_id, full_path, project_root))

    return {"job_id": job_id, "status": "started"}


@router.post("/run-tmp")
async def run_tmp_execution(request: RunTmpRequest):
    project_root = get_project_root()

    # 使用可写的数据目录存放临时运行文件
    data_dir = os.getenv("AI_IDE_DATA_DIR")
    if not data_dir:
        tmp_dir = os.path.join(project_root, "tmp", "ai_ide_run")
    else:
        tmp_dir = os.path.join(data_dir, "tmp_run")
    try:
        os.makedirs(tmp_dir, exist_ok=True)

        safe_filename = request.filename.replace("/", "_").replace("\\", "_")
        if not safe_filename.strip():
            safe_filename = "tmp.py"
        tmp_file = os.path.join(tmp_dir, f"run_{uuid.uuid4().hex[:8]}_{safe_filename}")

        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(request.content)

        job_id = str(uuid.uuid4())
        jobs[job_id] = {"status": "running", "queue": asyncio.Queue()}

        asyncio.create_task(run_process(job_id, tmp_file, project_root))
        return {"job_id": job_id, "status": "started"}
    except Exception as exc:
        logger.exception("run-tmp failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"run-tmp failed: {exc}")


@router.post("/stop/{job_id}")
async def stop_execution(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = jobs[job_id]
    process = job_info.get("process")

    if process and process.returncode is None:
        try:
            process.terminate()
            # 给一点时间让它优雅退出
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()

            await job_info["queue"].put("[ERROR] Process stopped by user")
            return {"status": "stopped"}
        except Exception as e:
            logger.error(f"Failed to stop process {job_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return {"status": "already_stopped"}


# Regex
RE_QLIB_PROGRESS = re.compile(r"Epoch\s+(\d+)/(\d+)")
RE_REPORT_GENERATED = re.compile(r"Analysis Report Generated:\s*(.+)")


@router.get("/logs/{job_id}")
async def get_logs_stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def log_generator():
        queue = jobs[job_id]["queue"]
        while True:
            try:
                log_line = await queue.get()
                if log_line == "[EOF]":
                    yield "data: [PROCESS_FINISHED]\n\n"
                    break

                # 处理日志中的换行符，遵循 SSE 规范
                lines = log_line.splitlines()
                if not lines:  # 处理空行
                    yield "data: \n\n"
                    continue

                for line in lines:
                    # 1. 识别错误
                    if "Traceback" in line or "Error:" in line or line.startswith("  File"):
                        yield f"data: [ERROR] {line}\n"
                    else:
                        yield f"data: {line}\n"

                    # 2. 进度解析
                    match_epoch = RE_QLIB_PROGRESS.search(line)
                    if match_epoch:
                        current, total = map(int, match_epoch.groups())
                        percent = int((current / total) * 100)
                        yield f'event: progress\ndata: {{"percent": {percent}, "message": "Training Epoch {current}/{total}"}}\n\n'

                    # 3. 报告生成
                    match_report = RE_REPORT_GENERATED.search(line)
                    if match_report:
                        report_path = match_report.group(1).strip()
                        yield f'event: report\ndata: {{"path": "{report_path}", "summary": "回测报告已生成"}}\n\n'

                yield "\n"  # 事件结束

            except Exception as e:
                yield f"data: [ERROR] Log streaming error: {str(e)}\n\n"
                break

        if job_id in jobs:
            del jobs[job_id]

    return StreamingResponse(log_generator(), media_type="text/event-stream")


async def run_process(job_id: str, file_path: str, cwd: str):
    if job_id not in jobs:
        return
    queue = jobs[job_id]["queue"]

    python_exe = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{cwd}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            python_exe,
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env=env,
        )

        # 保存 process 对象以便 stop 接口使用
        if job_id in jobs:
            jobs[job_id]["process"] = process

        async def read_stream():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\r\n")
                await queue.put(text)

        # 启动日志读取任务
        log_task = asyncio.create_task(read_stream())

        # 等待进程结束，设置超时时间（例如 300 秒）
        try:
            await asyncio.wait_for(process.wait(), timeout=300)
        except asyncio.TimeoutError:
            if process.returncode is None:
                process.kill()
                await queue.put("[ERROR] Execution timed out (300s limit)")

        await log_task

    except Exception as e:
        await queue.put(f"[ERROR] Execution failed: {str(e)}")
    finally:
        await queue.put("[EOF]")
        if job_id in jobs:
            jobs[job_id]["status"] = "completed"
            # 清理引用
            if "process" in jobs[job_id]:
                del jobs[job_id]["process"]


@router.post("/check-syntax")
async def check_syntax(item: RunTmpRequest):
    # 注意：前端可能传 content 字段，也可能传 code 字段。这里复用 RunTmpRequest (含 content)
    # 或者定义新的 CheckSyntaxRequest
    code = item.content
    try:
        tree = ast.parse(code)

        # 进一步检查 Qlib 格式
        # Qlib 策略通常需要包含 Initialize 和 Step 方法
        has_init = False
        has_step = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == "Initialize":
                    has_init = True
                elif node.name == "Step":
                    has_step = True

        is_qlib = has_init and has_step

        return {
            "valid": True,
            "is_qlib": is_qlib,
            "message": ("Valid Qlib Strategy" if is_qlib else "Valid Python Code (Not Qlib Format)"),
        }

    except SyntaxError as e:
        return {
            "valid": False,
            "line": e.lineno,
            "column": e.offset,
            "msg": e.msg,
            "detail": f"SyntaxError at line {e.lineno}: {e.msg}",
        }
    except Exception as e:
        return {"valid": False, "msg": str(e), "detail": str(e)}
