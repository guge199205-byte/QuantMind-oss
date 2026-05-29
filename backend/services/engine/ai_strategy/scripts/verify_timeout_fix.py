import asyncio

import httpx


async def test_ai_strategy_generate():
    print("Testing AI Strategy /strategy/generate ...")
    url = "http://127.0.0.1:8008/api/v1/strategy/generate"
    payload = {
        "description": "Test strategy with ma cross",
        "market": "CN",
        "risk_level": "medium",
        "timeframe": "1d",
        "symbols": ["000001.SZ"],
        "initial_capital": 100000.0,
        "position_size": 10.0,
        "max_positions": 5,
        "stop_loss": 5.0,
        "take_profit": 20.0,
        "backtest_period": "1year",
        "user_id": "test_user",
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # We use a long timeout now to wait for generation
            response = await client.post(url, json=payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success! (or at least it didn't 403)")
                # print(response.json().get("code")[:100])
            else:
                print(f"Error: {response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")


async def test_ai_ide_chat():
    print("\nTesting AI IDE /ai/chat (SSE)...")
    url = "http://127.0.0.1:8009/api/v1/ai/chat"
    payload = {
        "message": "Hello, this is a test.",
        "user_id": "test_user",
        "conversation_id": "test_conv",
        "history": [],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                print(f"Status: {response.status_code}")
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        print(f"Chunk: {line[6:]}")
                        break  # Just one chunk is enough
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_ai_strategy_generate())
    asyncio.run(test_ai_ide_chat())
