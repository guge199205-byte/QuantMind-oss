import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.ai_ide.app.core.agent import QuantAgent
from backend.services.ai_ide.app.settings import PROJECT_ROOT, refresh_runtime_settings, settings

logger = logging.getLogger(__name__)

router = APIRouter()

agent = QuantAgent(
    api_key=settings.api_key,
    base_url=settings.base_url,
    model=settings.model,
    project_root=PROJECT_ROOT,
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    current_code: str | None = None
    selection: str | None = None
    error_msg: str | None = None
    file_path: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    history: list[ChatMessage] | None = []
    extra_context: dict[str, Any] | None = None
    role: str | None = None  # quant_analyst | bug_fixer | code_reviewer


@router.post("/chat")
async def chat_completions(request: ChatRequest):
    # 动态更新 API Key (适配配置热更新)
    refresh_runtime_settings()
    agent.api_key = settings.api_key
    agent.base_url = settings.base_url
    agent.model = settings.model

    if not agent.api_key:
        raise HTTPException(status_code=500, detail="尚未配置 AI Key，请在 AI-IDE 设置中填写后重试。")

    # 角色切换
    if request.role and request.role != agent.role:
        agent.role = request.role
        agent._system_prompt_base = agent._build_system_prompt_base()
        agent._kb_context_cached = None  # 重置知识库缓存

    context = {
        "current_code": request.current_code,
        "selection": request.selection,
        "error_msg": request.error_msg,
        "file_path": request.file_path,
        "history": [m.model_dump() for m in (request.history or [])],
        **(request.extra_context or {}),
    }

    async def event_generator():
        try:
            async for chunk in agent.chat_stream(request.message, context):
                if chunk:
                    # 使用 JSON 封装 delta，确保换行符和空格透传，避免 SSE 协议的行处理干扰
                    data = json.dumps({"delta": chunk}, ensure_ascii=False)
                    yield f"data: {data}\n\n"
        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            error_msg = f"\n\n**System Error:** {str(e)}"
            error_data = json.dumps({"delta": error_msg}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

        # 发送结束信号
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/stop")
async def stop_chat():
    return {"status": "stopped"}
