from types import SimpleNamespace

import pytest

from backend.services.engine.qlib_app.services import backtest_service as service_mod


def test_resolve_qlib_backend_real_preferred(monkeypatch):
    fake_qlib = SimpleNamespace(__version__="9.9.9")
    fake_backtest = SimpleNamespace(backtest=lambda *args, **kwargs: None)
    fake_data = SimpleNamespace(D=SimpleNamespace())

    def fake_import(name):
        if name == "qlib":
            return fake_qlib
        if name == "qlib.backtest":
            return fake_backtest
        if name == "qlib.data":
            return fake_data
        raise ImportError(name)

    monkeypatch.setattr(service_mod.importlib, "import_module", fake_import)
    qlib_mod, _, _, backend = service_mod._resolve_qlib_backend(allow_mock=False)
    assert qlib_mod is fake_qlib
    assert backend == "real"


def test_resolve_qlib_backend_fails_when_real_missing_and_mock_disabled(monkeypatch):
    def fake_import(name):
        raise ImportError(name)

    monkeypatch.setattr(service_mod.importlib, "import_module", fake_import)
    with pytest.raises(ImportError, match="ENGINE_ALLOW_MOCK_QLIB=false"):
        service_mod._resolve_qlib_backend(allow_mock=False)


def test_resolve_qlib_backend_mock_when_enabled(monkeypatch):
    fake_mock = SimpleNamespace(
        __version__="0.0.0-mock",
        backtest=lambda *args, **kwargs: None,
        D=SimpleNamespace(),
    )

    def fake_import(name):
        if name.startswith("qlib"):
            raise ImportError(name)
        if name == "backend.services.engine.qlib_mock":
            return fake_mock
        raise ImportError(name)

    monkeypatch.setattr(service_mod.importlib, "import_module", fake_import)
    qlib_mod, _, _, backend = service_mod._resolve_qlib_backend(allow_mock=True)
    assert qlib_mod is fake_mock
    assert backend == "mock"


def test_check_health_includes_qlib_backend(monkeypatch):
    service = service_mod.QlibBacktestService(provider_uri="db/qlib_data", region="cn")

    def fake_initialize():
        service._initialized = True

    monkeypatch.setattr(service, "initialize", fake_initialize)
    monkeypatch.setattr(service_mod, "D", SimpleNamespace(features=lambda *args, **kwargs: []))
    health = service.check_health()
    assert "qlib_backend" in health
    assert health["qlib_backend"] in {"real", "mock"}
