"""AI 策略向导 - 远程策略相关 Schema 定义"""

from typing import List

from pydantic import BaseModel


class ScanRemoteRequest(BaseModel):
    user_id: str


class ImportRemoteRequest(BaseModel):
    user_id: str
    files: list[str]  # key 列表
