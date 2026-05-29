import json
import logging
import os
import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-IDE-Workspace")

router = APIRouter()


# 数据目录 (优先使用环境变量，确保生产环境可写)
DATA_DIR = os.getenv("AI_IDE_DATA_DIR")
if not DATA_DIR:
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return {}


def save_config(data):
    try:
        current = load_config()
        current.update(data)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def get_project_root():
    # 优先从配置文件读取
    config = load_config()
    if config.get("root_path") and os.path.exists(config["root_path"]):
        return config["root_path"]

    root = os.getenv("AI_IDE_PROJECT_ROOT")
    if not root:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    return os.path.abspath(root)


CURRENT_ROOT = get_project_root()


def _resolve_workspace_path(path: str, *, must_exist: bool = False) -> str:
    """Resolve a relative path under CURRENT_ROOT and enforce boundary checks."""
    root = os.path.abspath(CURRENT_ROOT)
    target = os.path.abspath(os.path.join(root, path or ""))
    try:
        in_workspace = os.path.commonpath([root, target]) == root
    except ValueError:
        in_workspace = False

    if not in_workspace:
        raise HTTPException(status_code=403, detail="Path is outside workspace root")
    if must_exist and not os.path.exists(target):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    return target


class CreateItemRequest(BaseModel):
    name: str
    dir: str | None = None


class RenameRequest(BaseModel):
    old_path: str
    new_path: str


class SetRootRequest(BaseModel):
    path: str


class SaveRequest(BaseModel):
    content: str


@router.get("/list")
async def list_files(path: str = ""):
    """
    列出目录，支持 base 和 parent 字段
    """
    # 确保路径安全
    try:
        target_path = _resolve_workspace_path(path)
    except HTTPException:
        target_path = os.path.abspath(CURRENT_ROOT)

    if not os.path.exists(target_path):
        target_path = os.path.abspath(CURRENT_ROOT)

    try:
        items = []
        for entry in os.scandir(target_path):
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue

            rel_path = os.path.relpath(entry.path, CURRENT_ROOT)
            info = entry.stat()
            items.append(
                {
                    "id": rel_path,  # 增加 id 字段用于前端渲染 key
                    "name": entry.name,
                    "path": rel_path,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": info.st_size,
                    "last_modified": info.st_mtime,
                }
            )

        items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))

        # --- 修正后的父目录计算逻辑 ---
        if target_path == CURRENT_ROOT:
            parent_rel = None  # 已经在根目录，没有上级
        else:
            # 计算当前目录的父目录相对于 CURRENT_ROOT 的路径
            parent_rel = os.path.relpath(os.path.dirname(target_path), CURRENT_ROOT)
            # 如果父目录就是根目录，relpath 会返回 "."，我们需要将其转为 "" 以适配前端
            if parent_rel == ".":
                parent_rel = ""
            # 如果路径包含 .. 说明超出了根目录范围，设为 None
            elif parent_rel.startswith(".."):
                parent_rel = None

        return {
            "items": items,
            "base": CURRENT_ROOT,
            "parent": parent_rel,
            "current": (os.path.relpath(target_path, CURRENT_ROOT) if target_path != CURRENT_ROOT else ""),
        }
    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-root")
async def set_root(request: SetRootRequest):
    global CURRENT_ROOT
    normalized = os.path.abspath(request.path)
    if os.path.exists(normalized) and os.path.isdir(normalized):
        CURRENT_ROOT = normalized
        save_config({"root_path": CURRENT_ROOT})
        return {"status": "success", "current_root": CURRENT_ROOT}
    else:
        raise HTTPException(status_code=400, detail="Invalid directory path")


@router.post("/create/file")
async def create_file(request: CreateItemRequest):
    full_path = _resolve_workspace_path(os.path.join(request.dir or "", request.name))
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write("")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create/folder")
async def create_folder(request: CreateItemRequest):
    full_path = _resolve_workspace_path(os.path.join(request.dir or "", request.name))
    try:
        os.makedirs(full_path, exist_ok=True)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
async def rename_item(request: RenameRequest):
    old_full = _resolve_workspace_path(request.old_path, must_exist=True)
    new_full = _resolve_workspace_path(request.new_path)
    try:
        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        os.rename(old_full, new_full)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_path:path}")
async def get_content(file_path: str):
    full_path = _resolve_workspace_path(file_path, must_exist=True)
    try:
        if os.path.isdir(full_path):
            raise HTTPException(status_code=400, detail="Path is a directory")
        with open(full_path, encoding="utf-8") as f:
            return {"content": f.read()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_path:path}")
async def save_content(file_path: str, request: SaveRequest):
    full_path = _resolve_workspace_path(file_path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(request.content)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_path:path}")
async def delete_item(file_path: str):
    full_path = _resolve_workspace_path(file_path, must_exist=True)
    try:
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
