"""
文件管理服务
处理策略文件的上传、下载、管理等功能
"""

import hashlib
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

# 导入共享枚举
try:
    from shared.enums import MessageRole, MessageType
except ImportError:
    MessageRole = str
    MessageType = str


class FileInfo:
    """文件信息"""

    def __init__(
        self,
        file_id: str,
        filename: str,
        content_type: str,
        size: int,
        file_path: str,
        upload_time: datetime,
        user_id: str,
        category: str = "general",
    ):
        self.file_id = file_id
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.file_path = file_path
        self.upload_time = upload_time
        self.user_id = user_id
        self.category = category
        self.content_hash = None
        self.description = ""
        self.tags = []

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "file_path": self.file_path,
            "upload_time": self.upload_time.isoformat(),
            "user_id": self.user_id,
            "category": self.category,
            "content_hash": self.content_hash,
            "description": self.description,
            "tags": self.tags,
        }


class FileManager:
    """文件管理器"""

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.files = {}  # file_id -> FileInfo
        self.user_files = {}  # user_id -> List[file_id]
        self.category_files = {}  # category -> List[file_id]

        # 创建目录结构
        self._create_directories()

    def _create_directories(self):
        """创建目录结构"""
        directories = [
            "strategies",
            "templates",
            "backtests",
            "data",
            "documents",
            "images",
            "temp",
        ]

        for directory in directories:
            (self.base_dir / directory).mkdir(exist_ok=True)

    def _generate_file_id(self) -> str:
        """生成文件ID"""
        return str(uuid.uuid4())

    def _calculate_file_hash(self, file_content: bytes) -> str:
        """计算文件哈希"""
        return hashlib.sha256(file_content).hexdigest()

    def _detect_category(self, filename: str, content_type: str, user_category: str = None) -> str:
        """检测文件类别"""
        if user_category and user_category != "auto":
            return user_category

        # 基于MIME类型检测
        if content_type.startswith("image/"):
            return "images"
        elif content_type.startswith("text/"):
            if filename.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c")):
                return "strategies"
            elif filename.endswith((".md", ".txt", ".doc", ".pd")):
                return "documents"
            else:
                return "general"
        elif content_type.startswith("application/"):
            if "json" in content_type:
                return "data"
            elif "pd" in content_type:
                return "documents"
            elif "zip" in content_type or "tar" in content_type:
                return "general"
            else:
                return "general"
        else:
            return "general"

    def upload_file(
        self,
        file_content: BinaryIO,
        filename: str,
        user_id: str,
        category: str = "auto",
        description: str = "",
        tags: list[str] = None,
    ) -> FileInfo:
        """上传文件"""
        # 读取文件内容
        content = file_content.read()
        file_size = len(content)

        # 生成文件ID和路径
        file_id = self._generate_file_id()
        content_hash = self._calculate_file_hash(content)

        # 检测文件类型
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        detected_category = self._detect_category(filename, content_type, category)

        # 确定存储路径
        category_dir = self.base_dir / detected_category
        file_path = category_dir / f"{file_id}_{filename}"

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)

        # 创建文件信息对象
        file_info = FileInfo(
            file_id=file_id,
            filename=filename,
            content_type=content_type,
            size=file_size,
            file_path=str(file_path),
            upload_time=datetime.now(),
            user_id=user_id,
            category=detected_category,
        )
        file_info.content_hash = content_hash
        file_info.description = description
        file_info.tags = tags or []

        # 更新索引
        self.files[file_id] = file_info
        if user_id not in self.user_files:
            self.user_files[user_id] = []
        self.user_files[user_id].append(file_id)

        if detected_category not in self.category_files:
            self.category_files[detected_category] = []
        self.category_files[detected_category].append(file_id)

        return file_info

    def get_file(self, file_id: str) -> FileInfo | None:
        """获取文件信息"""
        return self.files.get(file_id)

    def get_file_content(self, file_id: str) -> bytes | None:
        """获取文件内容"""
        file_info = self.get_file(file_id)
        if not file_info:
            return None

        try:
            with open(file_info.file_path, "rb") as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return None

    def download_file(self, file_id: str) -> str | None:
        """下载文件（返回文件路径）"""
        file_info = self.get_file(file_id)
        if not file_info:
            return None

        return file_info.file_path

    def delete_file(self, file_id: str, user_id: str) -> bool:
        """删除文件"""
        file_info = self.get_file(file_id)
        if not file_info:
            return False

        # 检查权限
        if file_info.user_id != user_id:
            return False

        try:
            # 删除物理文件
            os.remove(file_info.file_path)

            # 更新索引
            if file_id in self.files:
                del self.files[file_id]

            if user_id in self.user_files and file_id in self.user_files[user_id]:
                self.user_files[user_id].remove(file_id)
                if not self.user_files[user_id]:
                    del self.user_files[user_id]

            if file_info.category in self.category_files and file_id in self.category_files[file_info.category]:
                self.category_files[file_info.category].remove(file_id)
                if not self.category_files[file_info.category]:
                    del self.category_files[file_info.category]

            return True

        except (FileNotFoundError, PermissionError):
            return False

    def list_user_files(
        self,
        user_id: str,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """列出用户文件"""
        if user_id not in self.user_files:
            return {"files": [], "total": 0, "limit": limit, "offset": offset}

        file_ids = self.user_files[user_id]

        # 应用分类过滤
        if category and category != "all":
            category_file_ids = self.category_files.get(category, [])
            file_ids = [fid for fid in file_ids if fid in category_file_ids]

        # 应用分页
        total = len(file_ids)
        start = offset
        end = min(start + limit, total)
        paginated_ids = file_ids[start:end]

        files = []
        for file_id in paginated_ids:
            file_info = self.get_file(file_id)
            if file_info:
                files.append(file_info.to_dict())

        return {"files": files, "total": total, "limit": limit, "offset": offset}

    def list_files_by_category(self, category: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """按类别列出文件"""
        if category not in self.category_files:
            return {"files": [], "total": 0, "limit": limit, "offset": offset}

        file_ids = self.category_files[category]

        # 应用分页
        total = len(file_ids)
        start = offset
        end = min(start + limit, total)
        paginated_ids = file_ids[start:end]

        files = []
        for file_id in paginated_ids:
            file_info = self.get_file(file_id)
            if file_info:
                files.append(file_info.to_dict())

        return {
            "files": files,
            "total": total,
            "limit": limit,
            "offset": offset,
            "category": category,
        }

    def search_files(
        self,
        query: str,
        user_id: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[FileInfo]:
        """搜索文件"""
        results = []
        query_lower = query.lower()

        # 确定搜索范围
        if user_id:
            file_ids = self.user_files.get(user_id, [])
        else:
            file_ids = list(self.files.keys())

        if category and category != "all":
            category_file_ids = self.category_files.get(category, [])
            file_ids = [fid for fid in file_ids if fid in category_file_ids]

        # 搜索文件
        for file_id in file_ids:
            file_info = self.get_file(file_id)
            if file_info:
                # 搜索文件名、描述、标签
                search_text = (
                    file_info.filename.lower()
                    + " "
                    + file_info.description.lower()
                    + " "
                    + " ".join(file_info.tags).lower()
                )

                if query_lower in search_text:
                    results.append(file_info)

        # 限制结果数量
        return results[:limit]

    def update_file_metadata(
        self,
        file_id: str,
        user_id: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """更新文件元数据"""
        file_info = self.get_file(file_id)
        if not file_info or file_info.user_id != user_id:
            return False

        if description is not None:
            file_info.description = description

        if tags is not None:
            file_info.tags = tags

        return True

    def cleanup_temp_files(self, max_age_days: int = 7):
        """清理临时文件"""
        temp_dir = self.base_dir / "temp"
        if not temp_dir.exists():
            return

        current_time = datetime.now()
        deleted_count = 0

        for file_path in temp_dir.glob("*"):
            if file_path.is_file():
                # 检查文件年龄
                file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)

                if file_age > timedelta(days=max_age_days):
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except (OSError, PermissionError):
                        pass

        return deleted_count

    def get_storage_stats(self) -> dict[str, Any]:
        """获取存储统计信息"""
        total_files = len(self.files)
        total_size = sum(info.size for info in self.files.values())

        category_stats = {}
        for category, file_ids in self.category_files.items():
            category_size = sum(self.files[fid].size for fid in file_ids if fid in self.files)
            category_stats[category] = {"count": len(file_ids), "size": category_size}

        user_stats = {}
        for user_id, file_ids in self.user_files.items():
            user_size = sum(self.files[fid].size for fid in file_ids if fid in self.files)
            user_stats[user_id] = {"count": len(file_ids), "size": user_size}

        return {
            "total_files": total_files,
            "total_size": total_size,
            "base_directory": str(self.base_dir),
            "categories": category_stats,
            "users": user_stats,
            "storage_limit": None,  # 可以设置存储限制
            "last_cleanup": None,
        }


# 全局文件管理器实例
file_manager = FileManager()
