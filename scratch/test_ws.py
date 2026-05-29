import asyncio
import websockets

async def test():
    try:
        async with websockets.connect('ws://127.0.0.1:8003/api/v1/ws/market') as ws:
            print('SUCCESS')
    except Exception as e:
        print(f'FAILED: {e}')

if __name__ == "__main__":
    asyncio.run(test())
