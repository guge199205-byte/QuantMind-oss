"""
腾讯云COS配置管理模块
提供统一的COS配置管理和安全验证功能
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

# 加载环境变量
load_dotenv()


class COSConfigManager:
    """腾讯云COS配置管理器"""

    def __init__(self):
        """初始化配置管理器"""
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> dict[str, Any]:
        """从环境变量加载配置"""
        return {
            # 基础配置
            "secret_id": os.getenv("TENCENT_SECRET_ID") or os.getenv("SecretId"),
            "secret_key": os.getenv("TENCENT_SECRET_KEY") or os.getenv("SecretKey"),
            "region": os.getenv("TENCENT_REGION", "ap-guangzhou"),
            "bucket": os.getenv("TENCENT_BUCKET") or os.getenv("Bucket"),
            "scheme": os.getenv("TENCENT_SCHEME", "https"),
            "base_url": os.getenv("TENCENT_COS_URL"),
            # 安全配置
            "token_expire_time": int(os.getenv("TENCENT_TOKEN_EXPIRE_TIME", "3600")),  # 1小时
            "max_file_size": int(os.getenv("TENCENT_MAX_FILE_SIZE", "104857600")),  # 100MB
            "allowed_file_types": os.getenv(
                "TENCENT_ALLOWED_FILE_TYPES",
                "jpg,jpeg,png,gif,webp,pdf,doc,docx,txt,md,csv,xlsx,xls",
            ).split(","),
            # 上传路径配置
            "upload_path_pattern": os.getenv("TENCENT_UPLOAD_PATH_PATTERN", "{category}/{user_id}/{year}/{month}"),
            # CDN配置
            "cdn_domain": os.getenv("TENCENT_CDN_DOMAIN"),
            "use_https": os.getenv("TENCENT_USE_HTTPS", "true").lower() == "true",
            # 访问控制
            "private_read": os.getenv("TENCENT_PRIVATE_READ", "false").lower() == "true",
            "cache_control": os.getenv("TENCENT_CACHE_CONTROL", "max-age=31536000"),  # 1年
        }

    def _validate_config(self):
        """验证配置的完整性和有效性"""
        required_fields = ["secret_id", "secret_key", "region", "bucket"]
        missing_fields = [field for field in required_fields if not self.config.get(field)]

        if missing_fields:
            raise ValueError(f"COS配置不完整，缺少必要字段: {', '.join(missing_fields)}")

        # 验证region格式
        if not self.config["region"].startswith("ap-"):
            logger.warning(f"COS region格式可能不正确: {self.config['region']}")

        # 验证bucket格式
        if "-" not in self.config["bucket"]:
            logger.warning(f"COS bucket格式可能不正确，应包含APPID: {self.config['bucket']}")

        logger.info(f"COS配置验证通过 - Bucket: {self.config['bucket']}, Region: {self.config['region']}")

    def get_config(self) -> dict[str, Any]:
        """获取完整配置"""
        return self.config.copy()

    def get_base_url(self) -> str:
        """获取基础URL"""
        if self.config["base_url"]:
            return self.config["base_url"].rstrip("/")

        scheme = self.config["scheme"]
        bucket = self.config["bucket"]
        region = self.config["region"]

        return f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

    def get_cdn_url(self, file_key: str) -> str:
        """获取CDN加速URL"""
        if self.config["cdn_domain"]:
            return f"https://{self.config['cdn_domain']}/{file_key}"
        return f"{self.get_base_url()}/{file_key}"

    def is_file_type_allowed(self, file_extension: str, category: str = "general") -> bool:
        """检查文件类型是否被允许"""
        file_extension = file_extension.lower().lstrip(".")
        allowed_types = self.config["allowed_file_types"]

        # 根据类别进行特殊处理
        if category == "avatar":
            avatar_types = ["jpg", "jpeg", "png", "gi", "webp"]
            return file_extension in avatar_types
        elif category == "image":
            image_types = ["jpg", "jpeg", "png", "gi", "webp", "bmp"]
            return file_extension in image_types
        elif category == "document":
            doc_types = ["pd", "doc", "docx", "txt", "md", "csv", "xlsx", "xls"]
            return file_extension in doc_types

        return file_extension in allowed_types

    def get_max_file_size(self, category: str = "general") -> int:
        """根据类别获取最大文件大小限制"""
        base_size = self.config["max_file_size"]

        # 根据类别调整大小限制
        size_limits = {
            "avatar": 5 * 1024 * 1024,  # 5MB
            "avatar_image": 2 * 1024 * 1024,  # 2MB
            "comment_image": 5 * 1024 * 1024,  # 5MB
            "post_image": 10 * 1024 * 1024,  # 10MB
            "cover_image": 8 * 1024 * 1024,  # 8MB
            "document": 50 * 1024 * 1024,  # 50MB
            "archive": 100 * 1024 * 1024,  # 100MB
        }

        return size_limits.get(category, base_size)

    def generate_upload_path(self, category: str, user_id: str, filename: str) -> str:
        """生成上传路径"""
        import uuid
        from datetime import datetime

        # 生成唯一文件名
        file_ext = os.path.splitext(filename)[1]
        unique_name = f"{uuid.uuid4().hex}{file_ext}"

        # 获取时间信息
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        # 根据模式生成路径
        pattern = self.config["upload_path_pattern"]
        upload_path = pattern.format(
            category=category,
            user_id=user_id,
            year=year,
            month=month,
            filename=unique_name,
        )

        return upload_path

    def generate_presigned_url(self, file_key: str, expire_seconds: int = None) -> dict[str, Any]:
        """生成预签名URL"""
        if expire_seconds is None:
            expire_seconds = self.config["token_expire_time"]

        # 这里应该实现腾讯云COS的签名算法
        # 简化实现，实际应该使用完整的SDK
        base_url = self.get_base_url()
        url = f"{base_url}/{file_key}"

        # 生成签名（简化版本）
        timestamp = int(datetime.now().timestamp())
        expire_time = timestamp + expire_seconds

        return {
            "url": url,
            "expire_time": expire_time,
            "expire_seconds": expire_seconds,
            "method": "GET",
        }

    def get_security_headers(self) -> dict[str, str]:
        """获取安全相关的HTTP头"""
        headers = {}

        if self.config["cache_control"]:
            headers["Cache-Control"] = self.config["cache_control"]

        # 添加其他安全头
        headers.update(
            {
                "X-Content-Type-Options": "nosnif",
                "X-Frame-Options": "SAMEORIGIN",
                "X-XSS-Protection": "1; mode=block",
            }
        )

        return headers

    def validate_file_security(self, filename: str, file_size: int, content_type: str) -> dict[str, Any]:
        """验证文件安全性"""
        validation_result = {"valid": True, "errors": [], "warnings": []}

        # 检查文件名安全性
        dangerous_chars = ["..", "/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        for char in dangerous_chars:
            if char in filename:
                validation_result["valid"] = False
                validation_result["errors"].append(f"文件名包含危险字符: {char}")

        # 检查文件大小
        max_size = self.config["max_file_size"]
        if file_size > max_size:
            validation_result["valid"] = False
            validation_result["errors"].append(f"文件大小超过限制: {file_size} > {max_size}")

        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if not self.is_file_type_allowed(file_ext):
            validation_result["valid"] = False
            validation_result["errors"].append(f"不允许的文件类型: {file_ext}")

        # 检查内容类型
        if content_type and "script" in content_type.lower():
            validation_result["valid"] = False
            validation_result["errors"].append("不允许上传脚本文件")

        return validation_result

    def sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除危险字符"""
        # 移除危险字符
        dangerous_chars = ["..", "/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        safe_filename = filename

        for char in dangerous_chars:
            safe_filename = safe_filename.replace(char, "_")

        # 限制文件名长度
        name, ext = os.path.splitext(safe_filename)
        if len(name) > 100:
            name = name[:100]

        return f"{name}{ext}"

    def get_content_type(self, filename: str, default_type: str = "application/octet-stream") -> str:
        """根据文件名获取Content-Type"""
        ext = os.path.splitext(filename)[1].lower()

        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gi": "image/gi",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".pd": "application/pd",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
            ".7z": "application/x-7z-compressed",
        }

        return content_types.get(ext, default_type)


# 创建全局配置管理器实例
cos_config_manager = COSConfigManager()


def get_cos_config() -> COSConfigManager:
    """获取COS配置管理器实例"""
    return cos_config_manager


def get_cos_config_dict() -> dict[str, Any]:
    """获取COS配置字典"""
    return cos_config_manager.get_config()


# 预定义的文件类别配置
FILE_CATEGORIES = {
    "avatar": {
        "name": "头像",
        "max_size": 5 * 1024 * 1024,  # 5MB
        "allowed_types": ["jpg", "jpeg", "png", "gi", "webp"],
        "description": "用户头像图片",
    },
    "avatar_image": {
        "name": "头像图片",
        "max_size": 2 * 1024 * 1024,  # 2MB
        "allowed_types": ["jpg", "jpeg", "png"],
        "description": "小型头像图片",
    },
    "comment_image": {
        "name": "评论图片",
        "max_size": 5 * 1024 * 1024,  # 5MB
        "allowed_types": ["jpg", "jpeg", "png", "gi", "webp"],
        "description": "评论中的图片",
    },
    "post_image": {
        "name": "帖子图片",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "allowed_types": ["jpg", "jpeg", "png", "gi", "webp", "bmp"],
        "description": "帖子中的图片",
    },
    "cover_image": {
        "name": "封面图片",
        "max_size": 8 * 1024 * 1024,  # 8MB
        "allowed_types": ["jpg", "jpeg", "png", "webp"],
        "description": "封面图片",
    },
    "document": {
        "name": "文档",
        "max_size": 50 * 1024 * 1024,  # 50MB
        "allowed_types": ["pd", "doc", "docx", "txt", "md", "csv", "xlsx", "xls"],
        "description": "文档文件",
    },
    "archive": {
        "name": "压缩包",
        "max_size": 100 * 1024 * 1024,  # 100MB
        "allowed_types": ["zip", "rar", "7z", "tar", "gz"],
        "description": "压缩包文件",
    },
    "strategy_file": {
        "name": "策略文件",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "allowed_types": ["py", "txt", "json", "yaml", "yml"],
        "description": "策略相关文件",
    },
}


def get_file_category_config(category: str) -> dict[str, Any] | None:
    """获取文件类别配置"""
    return FILE_CATEGORIES.get(category.lower())


def list_supported_categories() -> list[dict[str, Any]]:
    """列出所有支持的文件类别"""
    return [
        {
            "key": key,
            "name": config["name"],
            "max_size": config["max_size"],
            "max_size_mb": config["max_size"] // (1024 * 1024),
            "allowed_types": config["allowed_types"],
            "description": config["description"],
        }
        for key, config in FILE_CATEGORIES.items()
    ]
