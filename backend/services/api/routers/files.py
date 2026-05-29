"""
Unified file routes for user-center upload/delete.

These routes must be handled by API service directly instead of AI-IDE proxy.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.services.api.user_app.middleware.auth import get_optional_user
from backend.shared.file_upload_service import file_upload_service

router = APIRouter(prefix="/files", tags=["Files"])


class DeleteFileRequest(BaseModel):
    file_key: str
    user_id: str


def _resolve_effective_user_id(optional_user: dict | None, requested_user_id: str) -> str:
    """
    Resolve effective user_id for file operations.

    Security rule:
    - If token user exists, always use token user_id (ignore body/form user_id).
    - If no token user, fallback to requested_user_id.
    """
    auth_user_id = str((optional_user or {}).get("user_id") or "").strip()
    req_user_id = str(requested_user_id or "").strip()
    effective_user_id = auth_user_id or req_user_id
    if not effective_user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    return effective_user_id


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    category: str = Form("auto"),
    description: str = Form(""),
    optional_user: dict | None = Depends(get_optional_user),
):
    effective_user_id = _resolve_effective_user_id(optional_user, user_id)
    result = await file_upload_service.upload_file(
        file=file,
        user_id=effective_user_id,
        category=category,
        description=description,
        tags=[],
    )
    return result


@router.delete("/delete")
async def delete_file(
    payload: DeleteFileRequest,
    optional_user: dict | None = Depends(get_optional_user),
):
    effective_user_id = _resolve_effective_user_id(optional_user, payload.user_id)
    return file_upload_service.delete_file(payload.file_key, effective_user_id)
