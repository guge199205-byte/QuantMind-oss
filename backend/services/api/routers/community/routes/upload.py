"""File upload routes."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.services.api.community_app.models import UploadResponse
from backend.shared.file_upload_service import file_upload_service

from ..auth import Principal, require_user

router = APIRouter()
IMAGE_UPLOAD_FIELD = File(...)


@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(file: UploadFile = IMAGE_UPLOAD_FIELD, principal: Principal = Depends(require_user)):
    """Upload an image (requires authentication)."""
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    user_id = principal.user_id or "anonymous"

    # Use the shared file upload service
    try:
        result = await file_upload_service.upload_file(file=file, user_id=user_id, category="image")

        if result.get("code") != 0:
            raise HTTPException(status_code=500, detail=result.get("message", "Upload failed"))

        data = result.get("data", {})
        return UploadResponse(
            url=data.get("file_url", ""),
            # Simple fallback if no specific thumbnail
            thumbnail=data.get("file_url", ""),
            filename=data.get("original_name", file.filename),
            size=data.get("file_size", 0),
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Upload processing error: {str(e)}")
