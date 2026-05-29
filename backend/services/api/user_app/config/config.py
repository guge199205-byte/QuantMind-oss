"""
User Service Configuration
增强版: 自动查找.env、生成SECRET_KEY、配置验证
"""

import os
import secrets
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# 加载 .env 文件
_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"
if _ROOT_ENV.exists():
    load_dotenv(str(_ROOT_ENV), override=False)

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.auth import DEFAULT_INTERNAL_CALL_SECRET


def find_env_file() -> Path | None:
    """
    智能查找.env文件
    优先级: 环境变量指定 > 项目根目录 > 服务目录 > Docker容器
    """
    # 1. 检查环境变量指定的路径
    env_path_str = os.getenv("ENV_FILE_PATH")
    if env_path_str:
        env_path = Path(env_path_str)
        if env_path.exists():
            return env_path

    # 2. 尝试多个可能的位置
    # 2. 尝试多个可能的位置
    possible_locations = [
        Path("/app/.env"),  # Docker容器
    ]

    # safely add parents[3]
    try:
        possible_locations.append(Path(__file__).resolve().parents[3] / ".env")
    except IndexError:
        pass

    possible_locations.extend(
        [
            Path(__file__).resolve().parent.parent / ".env",  # 服务目录
            Path.cwd() / ".env",  # 当前工作目录
        ]
    )

    for location in possible_locations:
        if location and location.exists():
            return location

    # 3. 未找到.env文件
    return None


# 查找.env文件
_ENV_FILE = find_env_file()


class Settings(BaseSettings):
    """
    应用配置

    自动从.env加载配置，支持环境变量覆盖
    如果SECRET_KEY未配置，会自动生成并警告
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============ 应用配置 ============
    APP_NAME: str = "User Service"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = False

    # ============ 数据库配置 ============
    DB_MASTER_HOST: str = os.getenv("DB_MASTER_HOST", "localhost")
    DB_MASTER_PORT: int = int(os.getenv("DB_MASTER_PORT", "5432"))
    DB_SLAVE_HOSTS: str = os.getenv("DB_SLAVE_HOSTS", "")  # 仅主库，空字符串表示无从库
    DB_NAME: str = os.getenv("DB_NAME", "quantmind")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "30"))

    # ============ Redis配置 ============
    REDIS_HOST: str = os.getenv("REDIS_HOST") or ("quantmind-redis" if os.path.exists("/.dockerenv") else "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    @model_validator(mode="after")
    def post_init(self) -> "Settings":
        """初始化后处理"""
        # 如果 REDIS_HOST 仍然是 localhost 且在 Docker 中，强制改为 quantmind-redis
        if os.path.exists("/.dockerenv") and self.REDIS_HOST in ("localhost", "127.0.0.1"):
            self.REDIS_HOST = "quantmind-redis"
        return self

    REDIS_SENTINELS: str = os.getenv("REDIS_SENTINELS", "localhost:26379,localhost:26380,localhost:26381")
    REDIS_MASTER_NAME: str = os.getenv("REDIS_MASTER_NAME", "quantmind-master")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

    # ============ JWT配置 ============
    SECRET_KEY: str = ""  # 将在验证器中检查或生成
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 48  # 48 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # 内部调用鉴别密钥（开发/联调用；生产建议通过网关侧剥离外部 Header + 独立密钥管理）
    INTERNAL_CALL_SECRET: str = DEFAULT_INTERNAL_CALL_SECRET

    # ============ CORS配置 ============
    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: any) -> list[str]:
        """
        支持从 .env 传入逗号分隔的字符串或直接传入列表
        """
        if isinstance(v, str):
            if v.strip() == "":
                return ["*"]
            # 处理可能的 JSON 数组格式
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except Exception:
                    pass
            # 默认按逗号分割
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ============ 日志配置 ============
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # ============ 缓存配置 ============
    CACHE_TTL_USER_PROFILE: int = 300  # 5分钟
    CACHE_TTL_USER_SESSION: int = 3600  # 1小时

    # ============ 档案表自动建表配置 ============
    AUTO_CREATE_PROFILE_TABLE: bool = False  # 仅开发环境或显式开启

    # ============ 安全配置 ============
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False

    # ============ 速率限制 ============
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_LOCKOUT_THRESHOLD: int = 5
    LOGIN_LOCKOUT_DURATION_MINUTES: int = 15

    # ============ SMS配置 (阿里云) ============
    ALIBABA_CLOUD_ACCESS_KEY_ID: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str = ""
    ALIBABA_CLOUD_SMS_SIGN_NAME: str = ""
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE_REGISTER: str = ""  # 注册验证码模板
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE_LOGIN: str = ""  # 登录验证码模板
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE_RESET_PASSWORD: str = ""  # 重置密码验证码模板
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE_BIND_PHONE: str = ""  # 绑定手机号模板（个人中心）
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE_CHANGE_PHONE: str = ""  # 换绑手机号模板（个人中心）

    # ============ SMS验证码与限流（企业级必需） ============
    SMS_CODE_EXPIRE_MINUTES: int = 5
    SMS_RATE_LIMIT_PER_IP_PER_MINUTE: int = 20
    SMS_RATE_LIMIT_PER_PHONE_PER_MINUTE: int = 3
    SMS_RATE_LIMIT_PER_PHONE_PER_DAY: int = 20
    AUTO_CREATE_PHONE_VERIFICATION_TABLE: bool = False  # 仅开发环境或显式开启

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        验证SECRET_KEY，如果为空则自动生成
        """
        if not v or v.strip() == "":
            # 生成随机密钥
            generated_key = secrets.token_hex(32)

            print("=" * 60)
            print("[WARNING]  WARNING: SECRET_KEY not configured!")
            print("=" * 60)
            print(f"Generated temporary SECRET_KEY: {generated_key}")
            print()
            print("IMPORTANT: This is a temporary key for development only!")
            print("For production, please:")
            print("  1. Add SECRET_KEY to your .env file")
            print("  2. Use a secure random value (at least 32 characters)")
            print("  3. Never commit SECRET_KEY to version control")
            print()
            print("To generate a secure key:")
            print("  Python:  python -c 'import secrets; print(secrets.token_hex(32))'")
            print("  OpenSSL: openssl rand -hex 32")
            print("=" * 60)
            print()

            return generated_key

        # 检查密钥强度
        if len(v) < 32:
            print(f"[WARNING]  Warning: SECRET_KEY is too short ({len(v)} chars)")
            print("   Recommended: at least 32 characters")

        return v

    @field_validator("DB_PASSWORD", mode="before")
    @classmethod
    def validate_db_password(cls, v: str) -> str:
        """验证数据库密码"""
        if not v or v.strip() == "":
            print("[WARNING]  Warning: DB_PASSWORD is empty!")
        elif v == "admin123":
            print("[WARNING]  Warning: Using default DB_PASSWORD!")
            print("   Please change it in production!")
        return v

    @model_validator(mode="after")
    def validate_settings(self):
        """整体配置验证"""
        # 检查端口范围
        if not (1 <= self.PORT <= 65535):
            raise ValueError(f"Invalid PORT: {self.PORT}")

        # 检查池大小
        if self.DB_POOL_SIZE < 1:
            raise ValueError(f"DB_POOL_SIZE must be >= 1, got {self.DB_POOL_SIZE}")

        # 检查密码策略一致性
        if self.PASSWORD_MIN_LENGTH < 4:
            print(f"[WARNING]  Warning: PASSWORD_MIN_LENGTH is very low ({self.PASSWORD_MIN_LENGTH})")

        return self


def get_settings() -> Settings:
    """
    获取配置单例
    提供更好的错误处理和配置加载日志
    """
    try:
        return Settings()
    except Exception as e:
        print("=" * 60)
        print("[FATAL] Failed to load configuration!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Please check:")
        print("  1. .env file exists and is readable")
        print("  2. All required variables are set")
        print("  3. Variable values are valid")
        print()
        sys.exit(1)


# 全局配置实例
settings = get_settings()
