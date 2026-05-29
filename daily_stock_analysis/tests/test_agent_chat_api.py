# -*- coding: utf-8 -*-
"""Agent chat history API regressions."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def teardown_function() -> None:
    DatabaseManager.reset_instance()
    Config.reset_instance()


def test_chat_session_messages_api_does_not_expose_provider_trace(tmp_path: Path) -> None:
    DatabaseManager.reset_instance()
    Config.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'trace.db'}")
    session_id = "api-trace-hidden"
    user_id = db.save_conversation_message(session_id, "user", "visible question")
    assistant_id = db.save_conversation_message(session_id, "assistant", "visible answer")
    db.save_agent_provider_turn(
        session_id=session_id,
        run_id="run-hidden",
        provider="deepseek",
        model="deepseek/deepseek-chat",
        anchor_user_message_id=user_id,
        anchor_assistant_message_id=assistant_id,
        messages=[
            {
                "role": "assistant",
                "content": "checking",
                "reasoning_content": "SECRET_REASONING",
                "tool_calls": [{"id": "call_1", "name": "echo", "arguments": {}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "SECRET_TOOL_RESULT"},
        ],
        contains_reasoning=True,
        contains_tool_calls=True,
        contains_thinking_blocks=False,
        must_roundtrip=True,
        estimated_tokens=10,
    )

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        client = TestClient(create_app(static_dir=tmp_path / "static"))
        response = client.get(f"/api/v1/agent/chat/sessions/{session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert [(msg["role"], msg["content"]) for msg in payload["messages"]] == [
        ("user", "visible question"),
        ("assistant", "visible answer"),
    ]
    assert "SECRET_REASONING" not in response.text
    assert "SECRET_TOOL_RESULT" not in response.text
    assert "tool_calls" not in response.text
