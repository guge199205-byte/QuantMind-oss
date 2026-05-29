import pytest


@pytest.mark.asyncio
async def test_notification_pusher_broadcasts_to_user_topic(monkeypatch):
    from backend.services.stream.ws_core.notification_pusher import NotificationPusher

    published = {}

    async def fake_publish(topic, message):
        published["topic"] = topic
        published["message"] = message
        return 1

    monkeypatch.setattr(
        "backend.services.stream.ws_core.notification_pusher.manager.publish",
        fake_publish,
    )

    pusher = NotificationPusher()
    await pusher._broadcast(
        {
            "notification_id": "42",
            "user_id": "1001",
            "tenant_id": "default",
            "title": "订单成交确认",
            "content": "已成交",
            "type": "trading",
            "level": "success",
            "action_url": "/trading",
            "created_at": "2026-03-10T10:00:00+00:00",
        }
    )

    assert published["topic"] == "notification.1001"
    assert published["message"]["type"] == "notification"
    assert published["message"]["data"]["id"] == 42
    assert published["message"]["data"]["title"] == "订单成交确认"


@pytest.mark.asyncio
async def test_notification_subscribe_requires_matching_user():
    from backend.services.stream.ws_core import server as ws_server

    messages = []

    ws_server.manager.connection_metadata["cid-1"] = {
        "authenticated": True,
        "user_id": "1001",
    }

    async def fake_subscribe(connection_id, topic):
        return True

    async def fake_send_message(connection_id, message, use_queue=False, **kwargs):
        messages.append(message)
        return True

    original_subscribe = ws_server.manager.subscribe
    original_send_message = ws_server.manager.send_message
    ws_server.manager.subscribe = fake_subscribe
    ws_server.manager.send_message = fake_send_message
    try:
        await ws_server.handle_message(
            "cid-1",
            {"type": "subscribe", "topic": "notification.9999"},
        )
    finally:
        ws_server.manager.subscribe = original_subscribe
        ws_server.manager.send_message = original_send_message
        ws_server.manager.connection_metadata.pop("cid-1", None)

    assert messages
    assert messages[0]["type"] == "error"
    assert messages[0]["error_code"] == "SUBSCRIPTION_FORBIDDEN"
