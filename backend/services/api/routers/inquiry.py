from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter(prefix="/inquiry", tags=["Inquiry"])

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_INQUIRY_STORAGE_PATH = Path(
    os.getenv("INQUIRY_STORAGE_PATH", str(_PROJECT_ROOT / "data" / "inquiries.json"))
)
_INQUIRY_LOCK = threading.Lock()


class InquiryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    company: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=200)
    interests: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1, max_length=8000)

    @field_validator("name", "email", "company", "phone", "title", "message", mode="before")
    @classmethod
    def _strip_strings(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("邮箱格式不正确")
        local_part, domain_part = normalized.rsplit("@", 1)
        if not local_part or "." not in domain_part:
            raise ValueError("邮箱格式不正确")
        return normalized

    @field_validator("interests", mode="before")
    @classmethod
    def _normalize_interests(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("interests 必须是数组")
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                normalized.append(text[:120])
        return normalized


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_inquiries() -> list[dict]:
    if not _INQUIRY_STORAGE_PATH.exists():
        return []
    try:
        payload = json.loads(_INQUIRY_STORAGE_PATH.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def _persist_inquiry(record: dict) -> None:
    _INQUIRY_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _INQUIRY_LOCK:
        inquiries = _load_inquiries()
        inquiries.append(record)
        tmp_path = _INQUIRY_STORAGE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(inquiries, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(_INQUIRY_STORAGE_PATH)


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_inquiry(payload: InquiryRequest, request: Request):
    record = {
        "id": str(uuid4()),
        "received_at": _now_iso(),
        "name": payload.name,
        "email": payload.email,
        "company": payload.company or "",
        "phone": payload.phone or "",
        "title": payload.title or "",
        "interests": payload.interests,
        "message": payload.message,
        "user_agent": request.headers.get("user-agent", ""),
        "ip_address": request.client.host if request.client else None,
    }

    try:
        _persist_inquiry(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存咨询失败: {exc}") from exc

    return {
        "code": 201,
        "success": True,
        "message": "Inquiry received",
        "data": {
            "id": record["id"],
            "received_at": record["received_at"],
        },
    }
