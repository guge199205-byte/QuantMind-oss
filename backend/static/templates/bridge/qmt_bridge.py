# ==============================================================================
# QuantMind QMT Agent Reference Template (过渡参考模板)
# 使用说明：
# 1. 该文件仅作为 QMT Agent 协议参考，不再作为生产交付物。
# 2. 正式接入请优先使用 tools/qmt_agent/qmt_agent.py 或独立 QMT Agent 程序。
# 3. 本模板演示双密钥换取短期 session token，再用 Bearer token 连接 /ws/bridge。
# ==============================================================================

from __future__ import annotations

import json
import socket
import time

import requests
import websocket

ACCESS_KEY = "{{ACCESS_KEY}}"
SECRET_KEY = "{{SECRET_KEY}}"
ACCOUNT_ID = "{{ACCOUNT_ID}}"
HOSTNAME = socket.gethostname()
CLIENT_FINGERPRINT = HOSTNAME
CLIENT_VERSION = "0.1.0"
API_BASE_URL = "{{API_BASE_URL}}"  # 例如 http://localhost:8000/api/v1
BRIDGE_WS_URL = "{{SERVER_URL}}"  # 例如 ws://localhost:8003/ws/bridge


def bootstrap_bridge_session() -> tuple[str, int]:
    response = requests.post(
        f"{API_BASE_URL.rstrip('/')}/internal/strategy/bridge/session",
        json={
            "access_key": ACCESS_KEY,
            "secret_key": SECRET_KEY,
            "agent_type": "qmt",
            "account_id": ACCOUNT_ID,
            "client_fingerprint": CLIENT_FINGERPRINT,
            "client_version": CLIENT_VERSION,
            "hostname": HOSTNAME,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data["bridge_session_token"], int(data["expires_in"])


def refresh_bridge_session(current_token: str) -> tuple[str, int]:
    response = requests.post(
        f"{API_BASE_URL.rstrip('/')}/internal/strategy/bridge/session/refresh",
        headers={"Authorization": f"Bearer {current_token}"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data["bridge_session_token"], int(data["expires_in"])


def report_heartbeat(token: str) -> None:
    requests.post(
        f"{API_BASE_URL.rstrip('/')}/internal/strategy/bridge/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "account_id": ACCOUNT_ID,
            "client_version": CLIENT_VERSION,
            "hostname": HOSTNAME,
            "status": "running",
            "qmt_connected": True,
            "latency_ms": 0,
        },
        timeout=15,
    ).raise_for_status()


def report_account(token: str) -> None:
    requests.post(
        f"{API_BASE_URL.rstrip('/')}/internal/strategy/bridge/account",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "account_id": ACCOUNT_ID,
            "broker": "qmt",
            "cash": 0.0,
            "available_cash": 0.0,
            "total_asset": 0.0,
            "market_value": 0.0,
            "positions": [],
        },
        timeout=15,
    ).raise_for_status()


def on_message(_ws, message: str) -> None:
    data = json.loads(message)
    print("[QMTAgent] received:", data)


def main() -> None:
    token, expires_in = bootstrap_bridge_session()
    report_account(token)
    report_heartbeat(token)
    ws = websocket.WebSocketApp(
        BRIDGE_WS_URL,
        header=[f"Authorization: Bearer {token}"],
        on_message=on_message,
        on_error=lambda _ws, err: print("[QMTAgent] ws error:", err),
        on_close=lambda _ws, code, msg: print("[QMTAgent] ws closed:", code, msg),
    )

    started_at = time.time()
    while True:
        if time.time() - started_at >= max(60, expires_in - 300):
            token, expires_in = refresh_bridge_session(token)
            started_at = time.time()
        ws.run_forever(ping_interval=20, ping_timeout=10)
        time.sleep(3)


if __name__ == "__main__":
    main()
