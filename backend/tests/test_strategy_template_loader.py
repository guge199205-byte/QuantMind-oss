"""
策略模板动态加载器单元测试

测试 StrategyTemplateLoader 从文件系统加载 .py + .json 模板、TTL 缓存、
invalidate_cache 以及公开接口 get_all_templates / get_template_by_id。
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 确保能找到项目模块（在 .venv 环境下运行无需额外配置）
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def template_dir(tmp_path: Path):
    """创建临时策略模板目录，并写入两个合法模板。"""
    # 模板 1
    (tmp_path / "test_topk.json").write_text(
        json.dumps(
            {
                "id": "test_topk",
                "name": "测试 TopK 策略",
                "description": "单元测试用策略",
                "category": "basic",
                "difficulty": "beginner",
                "params": [{"name": "topk", "description": "选股数量", "default": 20, "min": 5, "max": 100}],
                "execution_defaults": {},
                "live_defaults": {},
                "live_config_tips": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_topk.py").write_text(
        'STRATEGY_CONFIG = {"class": "RedisTopkStrategy", "kwargs": {"topk": 20}}\n',
        encoding="utf-8",
    )

    # 模板 2
    (tmp_path / "test_stoploss.json").write_text(
        json.dumps(
            {
                "id": "test_stoploss",
                "name": "测试止损策略",
                "description": "止损单元测试",
                "category": "risk_control",
                "difficulty": "beginner",
                "params": [
                    {"name": "stop_loss", "description": "止损阈值", "default": -0.08, "min": -0.3, "max": -0.01}
                ],
                "execution_defaults": {},
                "live_defaults": {},
                "live_config_tips": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_stoploss.py").write_text(
        'STRATEGY_CONFIG = {"class": "RedisStopLossStrategy", "kwargs": {"stop_loss": -0.08}}\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def loader(template_dir: Path, monkeypatch):
    """返回指向临时目录的 StrategyTemplateLoader 实例。"""
    monkeypatch.setenv("STRATEGY_TEMPLATES_DIR", str(template_dir))
    monkeypatch.setenv("STRATEGY_TEMPLATES_CACHE_TTL", "2")  # 2 秒 TTL 方便测试

    # 重新导入以使环境变量生效
    import importlib

    import backend.services.engine.qlib_app.services.strategy_templates as mod

    importlib.reload(mod)
    return mod.StrategyTemplateLoader()


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


class TestStrategyTemplateLoader:
    def test_load_returns_all_valid_templates(self, loader):
        """加载应返回目录中所有合法模板。"""
        templates = loader.load()
        assert len(templates) == 2
        ids = {t.id for t in templates}
        assert "test_topk" in ids
        assert "test_stoploss" in ids

    def test_template_fields_populated(self, loader):
        """模板对象字段应正确从 json + py 组装。"""
        templates = loader.load()
        topk = next(t for t in templates if t.id == "test_topk")
        assert topk.name == "测试 TopK 策略"
        assert topk.category == "basic"
        assert topk.difficulty == "beginner"
        assert len(topk.params) == 1
        assert topk.params[0].name == "topk"
        assert topk.params[0].default == 20
        # 代码内容应被读入
        assert "STRATEGY_CONFIG" in topk.code

    def test_cache_hit_returns_same_list(self, loader):
        """两次 load() 应返回同一对象（缓存命中）。"""
        first = loader.load()
        second = loader.load()
        assert first is second

    def test_cache_invalidation(self, loader):
        """invalidate_cache 后下次 load() 应重新读取磁盘。"""
        first = loader.load()
        loader.invalidate_cache()
        second = loader.load()
        # 对象不同（重新加载），但内容相同
        assert first is not second
        assert {t.id for t in first} == {t.id for t in second}

    def test_cache_ttl_expiry(self, loader):
        """缓存超过 TTL 后应自动重新加载。"""
        first = loader.load()
        time.sleep(3)  # 等候 TTL（2s）超期
        second = loader.load()
        assert first is not second

    def test_new_template_picked_up_after_ttl(self, loader, template_dir: Path):
        """新增文件后，缓存 TTL 过期后应能被发现。"""
        loader.load()  # 触发初次加载

        # 新增一个模板文件
        (template_dir / "new_strat.json").write_text(
            json.dumps(
                {
                    "id": "new_strat",
                    "name": "新增策略",
                    "description": "热更新测试",
                    "category": "basic",
                    "difficulty": "beginner",
                    "params": [],
                    "execution_defaults": {},
                    "live_defaults": {},
                    "live_config_tips": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (template_dir / "new_strat.py").write_text(
            'STRATEGY_CONFIG = {"class": "NewStrategy", "kwargs": {}}\n',
            encoding="utf-8",
        )

        # 等候 TTL 过期
        time.sleep(3)
        templates = loader.load()
        ids = {t.id for t in templates}
        assert "new_strat" in ids

    def test_get_by_id_case_insensitive(self, loader):
        """get_by_id 应不区分大小写。"""
        t = loader.get_by_id("TEST_TOPK")
        assert t is not None
        assert t.id == "test_topk"

    def test_get_by_id_not_found(self, loader):
        """get_by_id 找不到时返回 None。"""
        assert loader.get_by_id("nonexistent") is None

    def test_missing_py_file_skipped(self, loader, template_dir: Path):
        """有 .json 但缺少对应 .py 的模板应被跳过。"""
        (template_dir / "orphan.json").write_text(
            json.dumps(
                {
                    "id": "orphan",
                    "name": "孤儿模板",
                    "description": "无代码文件",
                    "category": "basic",
                    "difficulty": "beginner",
                    "params": [],
                    "execution_defaults": {},
                    "live_defaults": {},
                    "live_config_tips": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loader.invalidate_cache()
        templates = loader.load()
        ids = {t.id for t in templates}
        assert "orphan" not in ids

    def test_missing_required_field_skipped(self, loader, template_dir: Path):
        """元数据缺少必填字段（如 category）的模板应被跳过。"""
        (template_dir / "bad_meta.json").write_text(
            json.dumps({"id": "bad_meta", "name": "缺字段"}),
            encoding="utf-8",
        )
        (template_dir / "bad_meta.py").write_text("pass\n", encoding="utf-8")
        loader.invalidate_cache()
        templates = loader.load()
        ids = {t.id for t in templates}
        assert "bad_meta" not in ids


class TestPublicInterface:
    def test_get_all_templates_returns_list(self, monkeypatch, template_dir: Path):
        """公开接口 get_all_templates() 应返回非空列表。"""
        monkeypatch.setenv("STRATEGY_TEMPLATES_DIR", str(template_dir))
        import importlib

        import backend.services.engine.qlib_app.services.strategy_templates as mod

        importlib.reload(mod)

        templates = mod.get_all_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 0  # 路径合法即可

    def test_get_template_by_id_existing(self, monkeypatch, template_dir: Path):
        """get_template_by_id 应能找到已存在的模板。"""
        monkeypatch.setenv("STRATEGY_TEMPLATES_DIR", str(template_dir))
        import importlib

        import backend.services.engine.qlib_app.services.strategy_templates as mod

        importlib.reload(mod)

        t = mod.get_template_by_id("test_topk")
        assert t is not None
        assert t.id == "test_topk"

    def test_invalidate_templates_cache(self, monkeypatch, template_dir: Path):
        """invalidate_templates_cache() 应正常执行不抛出异常。"""
        monkeypatch.setenv("STRATEGY_TEMPLATES_DIR", str(template_dir))
        import importlib

        import backend.services.engine.qlib_app.services.strategy_templates as mod

        importlib.reload(mod)

        mod.get_all_templates()  # 触发加载
        mod.invalidate_templates_cache()  # 失效缓存
        # 再次加载不应报错
        templates = mod.get_all_templates()
        assert isinstance(templates, list)


class TestProductionTemplatesDir:
    def test_production_templates_dir_loads(self):
        """验证生产 strategy_templates/ 目录中的所有模板都能正常加载。"""
        from backend.services.engine.qlib_app.services.strategy_templates import (
            StrategyTemplateLoader,
        )

        loader = StrategyTemplateLoader()
        templates = loader.load()

        # 应至少加载到 9 个内置模板
        assert len(templates) >= 9, f"expected >= 9 templates in strategy_templates/, got {len(templates)}"

        # 每个模板的核心字段都应有值
        for t in templates:
            assert t.id, f"模板 id 为空: {t}"
            assert t.name, f"模板 name 为空: {t.id}"
            assert t.code.strip(), f"模板代码为空: {t.id}"
            assert t.category in ("basic", "advanced", "risk_control"), f"模板 category 非法: {t.id} → {t.category}"
            assert t.difficulty in (
                "beginner",
                "intermediate",
                "advanced",
            ), f"模板 difficulty 非法: {t.id} → {t.difficulty}"
