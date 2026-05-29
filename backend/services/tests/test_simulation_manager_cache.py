import json

import pytest

from backend.services.trade.services.simulation_manager import SimulationAccountManager


class _FakeRedisClient:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value

    def eval(self, script, numkeys, *args):
        key = args[0]
        symbol = args[1]
        delta_cash = float(args[2])
        delta_volume = float(args[3])
        price = float(args[4])
        account = json.loads(self.store[key])
        account["cash"] = float(account.get("cash") or 0.0) + delta_cash
        positions = dict(account.get("positions") or {})
        pos = dict(positions.get(symbol) or {"volume": 0, "cost": 0, "market_value": 0, "price": 0})
        pos["volume"] = float(pos.get("volume") or 0.0) + delta_volume
        pos["price"] = price
        pos["market_value"] = float(pos["volume"] or 0.0) * price
        positions[symbol] = pos
        account["positions"] = positions
        account["market_value"] = sum(float(p.get("volume") or 0.0) * float(p.get("price") or 0.0) for p in positions.values())
        account["total_asset"] = float(account.get("cash") or 0.0) + float(account.get("market_value") or 0.0)
        self.store[key] = json.dumps(account, ensure_ascii=False)
        return {"success": True}


class _FakeRedis:
    def __init__(self):
        self.client = _FakeRedisClient()


@pytest.mark.asyncio
async def test_simulation_manager_writes_settings_and_account_json():
    redis = _FakeRedis()
    manager = SimulationAccountManager(redis)

    await manager.set_initial_cash(
        user_id=1,
        tenant_id="default",
        initial_cash=1_000_000,
    )
    settings = await manager.get_settings(
        user_id=1,
        tenant_id="default",
        default_initial_cash=500_000,
    )
    assert settings["initial_cash"] == 1_000_000
    assert json.loads(redis.client.get("simulation:settings:default:1"))["initial_cash"] == 1_000_000

    account = await manager.init_account(user_id=1, tenant_id="default", initial_cash=2_000_000)
    assert account["cash"] == 2_000_000
    assert json.loads(redis.client.get("simulation:account:default:1"))["cash"] == 2_000_000


@pytest.mark.asyncio
async def test_simulation_manager_account_update_uses_cache_helper():
    redis = _FakeRedis()
    manager = SimulationAccountManager(redis)

    await manager.init_account(user_id=1, tenant_id="default", initial_cash=1_000_000)
    result = await manager.update_balance(
        user_id=1,
        symbol="600000.SH",
        delta_cash=-1000,
        delta_volume=100,
        price=10.0,
        tenant_id="default",
    )

    assert result["success"] is True
    cached = json.loads(redis.client.get("simulation:account:default:1"))
    assert cached["cash"] == 999000
    assert cached["total_asset"] > 0
