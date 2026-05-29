"""
Redis Configuration Schemas
"""

from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    """密码修改请求"""

    old_password: str = Field(..., description="当前密码", min_length=8)
    new_password: str = Field(..., description="新密码", min_length=8, max_length=64)


class ChangePasswordResponse(BaseModel):
    """密码修改响应"""

    code: int = 200
    message: str = "密码修改成功"
    data: dict = {}


class RedisConfigResponse(BaseModel):
    """Redis配置响应"""

    code: int = 200
    message: str = "获取成功"
    data: dict
