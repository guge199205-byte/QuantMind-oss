import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services.ai_ide.app.api import chat, config, executor, workspace
from backend.services.ai_ide.app.settings import settings
from backend.shared.cors import resolve_cors_origins

app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_origins(logger=logger),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat.router, prefix="/api/v1/ai")
app.include_router(workspace.router, prefix="/api/v1/files")
app.include_router(executor.router, prefix="/api/v1/execute")
app.include_router(config.router, prefix="/api/v1/config")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AI_IDE_BACKEND_PORT", 8009))
    uvicorn.run(app, host="127.0.0.1", port=port)
