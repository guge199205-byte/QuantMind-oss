from backend.services.trade.runner import main as runner_main


def test_current_phase_splits_sell_and_buy_windows():
    cfg = {
        "sell_time": "14:30",
        "buy_time": "14:45",
        "sell_first": True,
    }

    assert runner_main._current_phase("14:20", cfg) == "IDLE"
    assert runner_main._current_phase("14:35", cfg) == "SELL"
    assert runner_main._current_phase("14:50", cfg) == "BUY"


def test_filter_signals_by_phase_keeps_only_matching_side():
    signals = [
        {"action": "BUY", "symbol": "000001.SZ"},
        {"action": "SELL", "symbol": "600000.SH"},
        {"action": "BUY", "symbol": "600519.SH"},
    ]

    assert runner_main._filter_signals_by_phase(signals, "SELL") == [{"action": "SELL", "symbol": "600000.SH"}]
    assert runner_main._filter_signals_by_phase(signals, "BUY") == [
        {"action": "BUY", "symbol": "000001.SZ"},
        {"action": "BUY", "symbol": "600519.SH"},
    ]
    assert runner_main._filter_signals_by_phase(signals, "IDLE") == []


def test_within_enabled_session_respects_am_pm_selection():
    assert runner_main._is_within_enabled_session("10:00", {"enabled_sessions": ["PM"]}) is False
    assert runner_main._is_within_enabled_session("10:00", {"enabled_sessions": ["AM"]}) is True
    assert runner_main._is_within_enabled_session("14:30", {"enabled_sessions": ["PM"]}) is True
    assert runner_main._is_within_enabled_session("14:30", {"enabled_sessions": ["AM"]}) is False


def test_apply_portfolio_risk_gate_uses_stop_loss_from_execution_config():
    signals = [
        {"action": "BUY", "symbol": "000001.SZ", "price": 10.0, "volume": 100},
        {"action": "SELL", "symbol": "600000.SH", "price": 12.0, "volume": 100},
    ]

    filtered = runner_main._apply_portfolio_risk_gate(
        signals,
        account={"total_value": 100000, "drawdown": -0.09, "positions": {}},
        exec_config={"stop_loss": -0.08},
        market_snapshot={},
        live_trade_config={},
    )
    # 没有 trade_action 时默认按旧逻辑(拦截所有BUY)，所以 filtered 为空 (因为没有 SELL_TO_CLOSE/BUY_TO_CLOSE)
    assert filtered == []

    # 显式提供 trade_action 的情况
    signals_with_action = [
        {"action": "BUY", "symbol": "000001.SZ", "price": 10.0, "volume": 100, "trade_action": "BUY_TO_CLOSE"},
        {"action": "BUY", "symbol": "000002.SZ", "price": 15.0, "volume": 100, "trade_action": "BUY_TO_OPEN"},
    ]
    filtered_with_action = runner_main._apply_portfolio_risk_gate(
        signals_with_action,
        account={"total_value": 100000, "drawdown": -0.09, "positions": {}},
        exec_config={"stop_loss": -0.08},
        market_snapshot={},
        live_trade_config={},
    )
    # 应该仅保留 BUY_TO_CLOSE
    assert len(filtered_with_action) == 1
    assert filtered_with_action[0]["symbol"] == "000001.SZ"


def test_apply_portfolio_risk_gate_uses_live_trade_max_price_deviation():
    signals = [{"action": "BUY", "symbol": "000001.SZ", "price": 10.0, "volume": 100}]

    filtered = runner_main._apply_portfolio_risk_gate(
        signals,
        account={"total_value": 100000, "drawdown": 0, "positions": {}},
        exec_config={},
        market_snapshot={"000001.SZ": {"Now": 11.0}},
        live_trade_config={"max_price_deviation": 0.02},
    )

    assert filtered == []


def test_apply_portfolio_risk_gate_applies_max_buy_drop():
    # A. BUY_TO_OPEN 触发拦截
    signals = [{"trade_action": "BUY_TO_OPEN", "action": "BUY", "symbol": "000001.SZ", "price": 10.0, "volume": 100}]
    filtered = runner_main._apply_portfolio_risk_gate(
        signals,
        account={"total_value": 100000, "drawdown": 0, "positions": {}},
        exec_config={"max_buy_drop": -0.03},
        market_snapshot={"000001.SZ": {"Now": 10.0, "pct_chg": -5.0}},
        live_trade_config={},
    )
    assert filtered == []

    # B. BUY_TO_CLOSE (空头平仓) 不应被大跌拦截
    signals_b = [{"trade_action": "BUY_TO_CLOSE", "action": "BUY", "symbol": "000001.SZ", "price": 10.0, "volume": 100}]
    filtered_b = runner_main._apply_portfolio_risk_gate(
        signals_b,
        account={"total_value": 100000, "drawdown": 0, "positions": {}},
        exec_config={"max_buy_drop": -0.03},
        market_snapshot={"000001.SZ": {"Now": 10.0, "pct_chg": -5.0}},
        live_trade_config={},
    )
    assert len(filtered_b) == 1

    # C. SELL_TO_OPEN (空头开仓) 触发大涨拦截 (使用对称的 3%)
    signals_c = [{"trade_action": "SELL_TO_OPEN", "action": "SELL", "symbol": "000001.SZ", "price": 10.0, "volume": 100}]
    filtered_c = runner_main._apply_portfolio_risk_gate(
        signals_c,
        account={"total_value": 100000, "drawdown": 0, "positions": {}},
        exec_config={"max_buy_drop": -0.03},
        market_snapshot={"000001.SZ": {"Now": 10.0, "pct_chg": 5.0}},
        live_trade_config={},
    )
    assert filtered_c == []
