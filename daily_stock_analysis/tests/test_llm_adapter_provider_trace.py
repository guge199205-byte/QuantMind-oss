# -*- coding: utf-8 -*-
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.agent.llm_adapter import LLMToolAdapter  # noqa: E402


def test_convert_messages_preserves_reasoning_blocks_and_provider_specific_fields() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    messages = [
        {
            "role": "assistant",
            "content": "checking",
            "_trace_provider": "anthropic",
            "_trace_model": "anthropic/claude-test",
            "provider_blocks": [
                {"type": "thinking", "thinking": "opaque"},
                {"type": "redacted_thinking", "data": "redacted"},
                {"type": "text", "text": "checking"},
            ],
            "reasoning_content": "reasoning",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "echo",
                    "arguments": {"message": "hello"},
                    "thought_signature": "sig-1",
                    "provider_specific_fields": {"thought_signature": "sig-1", "extra": "keep"},
                }
            ],
        }
    ]

    converted = adapter._convert_messages(messages)

    assert converted[0]["role"] == "assistant"
    assert converted[0]["content"][0]["type"] == "thinking"
    assert converted[0]["reasoning_content"] == "reasoning"
    assert converted[0]["tool_calls"][0]["provider_specific_fields"] == {
        "thought_signature": "sig-1",
        "extra": "keep",
    }
    assert "_trace_provider" not in converted[0]


def test_convert_messages_only_sends_provider_trace_to_matching_target_model() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    messages = [
        {
            "role": "assistant",
            "content": "checking",
            "_trace_provider": "anthropic",
            "_trace_model": "anthropic/claude-test",
            "provider_blocks": [{"type": "thinking", "thinking": "opaque"}],
            "reasoning_content": "provider-only",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "echo",
                    "arguments": {"message": "hello"},
                    "thought_signature": "sig-1",
                    "provider_specific_fields": {"thought_signature": "sig-1"},
                }
            ],
        }
    ]

    matching = adapter._convert_messages(messages, target_model="anthropic/claude-test")
    mismatched = adapter._convert_messages(messages, target_model="openai/gpt-4o-mini")

    assert matching[0]["content"] == [{"type": "thinking", "thinking": "opaque"}]
    assert matching[0]["reasoning_content"] == "provider-only"
    assert matching[0]["tool_calls"][0]["provider_specific_fields"] == {"thought_signature": "sig-1"}

    assert mismatched == []


def test_convert_messages_skips_entire_trace_segment_for_mismatched_attempt() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    messages = [
        {"role": "user", "content": "u1"},
        {
            "role": "assistant",
            "content": "checking",
            "_trace_provider": "deepseek",
            "_trace_model": "deepseek/deepseek-chat",
            "reasoning_content": "provider-only",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "echo",
                    "arguments": {"message": "hello"},
                    "provider_specific_fields": {"thought_signature": "sig-1"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "tool-result",
            "_trace_provider": "deepseek",
            "_trace_model": "deepseek/deepseek-chat",
        },
        {"role": "assistant", "content": "a1-final"},
    ]

    primary = adapter._convert_messages(messages, target_model="openai/gpt-4o-mini")
    fallback = adapter._convert_messages(messages, target_model="deepseek/deepseek-chat")

    assert [msg["role"] for msg in primary] == ["user", "assistant"]
    assert primary[-1]["content"] == "a1-final"
    assert all(msg.get("tool_call_id") != "call_1" for msg in primary)

    assert [msg["role"] for msg in fallback] == ["user", "assistant", "tool", "assistant"]
    assert fallback[1]["reasoning_content"] == "provider-only"
    assert fallback[1]["tool_calls"][0]["provider_specific_fields"] == {"thought_signature": "sig-1"}
    assert fallback[2]["tool_call_id"] == "call_1"


def test_convert_messages_matches_slashless_openai_target_without_provider_leakage() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    messages = [
        {
            "role": "assistant",
            "content": "checking",
            "_trace_provider": "openai",
            "_trace_model": "gpt-4o-mini",
            "reasoning_content": "provider-only",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "echo",
                    "arguments": {},
                    "provider_specific_fields": {"thought_signature": "sig-1"},
                }
            ],
        }
    ]

    matching = adapter._convert_messages(messages, target_model="gpt-4o-mini")
    mismatched = adapter._convert_messages(messages, target_model="claude-router")

    assert matching[0]["reasoning_content"] == "provider-only"
    assert matching[0]["tool_calls"][0]["provider_specific_fields"] == {"thought_signature": "sig-1"}
    assert mismatched == []


def test_parse_litellm_response_extracts_claude_blocks_and_tool_provider_fields() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    blocks = [
        {"type": "thinking", "thinking": "opaque"},
        {"type": "redacted_thinking", "data": "hidden"},
        {"type": "text", "text": "Need data"},
    ]
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=blocks,
                    reasoning_content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="echo",
                                arguments='{"message": "hello"}',
                                provider_specific_fields=None,
                            ),
                            provider_specific_fields={"thought_signature": "sig-1", "extra": "keep"},
                        )
                    ],
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )

    parsed = adapter._parse_litellm_response(response, "anthropic/claude-test")

    assert parsed.content == "Need data"
    assert parsed.provider_blocks == blocks
    assert parsed.provider == "anthropic"
    assert parsed.model == "anthropic/claude-test"
    assert parsed.tool_calls[0].thought_signature == "sig-1"
    assert parsed.tool_calls[0].provider_specific_fields == {
        "thought_signature": "sig-1",
        "extra": "keep",
    }


def test_parse_litellm_response_resolves_provider_for_slashless_router_alias() -> None:
    adapter = LLMToolAdapter.__new__(LLMToolAdapter)
    adapter._config = SimpleNamespace(
        llm_model_list=[
            {
                "model_name": "claude-router",
                "litellm_params": {"model": "anthropic/claude-sonnet-test"},
            }
        ]
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="ok",
                    reasoning_content=None,
                    tool_calls=[],
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )

    parsed_alias = adapter._parse_litellm_response(response, "claude-router")
    parsed_bare_openai = adapter._parse_litellm_response(response, "gpt-4o-mini")

    assert parsed_alias.provider == "anthropic"
    assert parsed_alias.model == "claude-router"
    assert parsed_bare_openai.provider == "openai"
    assert parsed_bare_openai.model == "gpt-4o-mini"
