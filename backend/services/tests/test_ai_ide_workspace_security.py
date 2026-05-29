"""
test_ai_ide_workspace_security.py - AI-IDE 工作区边界与 CORS 基线测试
"""

from fastapi.testclient import TestClient

from backend.services.ai_ide.app import main as ai_ide_main
from backend.services.ai_ide.app.api import workspace as workspace_api


class TestAIIDEWorkspaceSecurity:
    def setup_method(self):
        self.client = TestClient(ai_ide_main.app)

    def test_create_file_outside_workspace_forbidden(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace_api, "CURRENT_ROOT", str(tmp_path))
        response = self.client.post(
            "/api/v1/files/create/file",
            json={"name": "../escape.py", "dir": ""},
        )
        assert response.status_code == 403

    def test_save_content_outside_workspace_forbidden(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace_api, "CURRENT_ROOT", str(tmp_path))
        response = self.client.post(
            "/api/v1/files/create/file",
            json={"name": "escape.py", "dir": "../../"},
        )
        assert response.status_code == 403

    def test_save_content_inside_workspace_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr(workspace_api, "CURRENT_ROOT", str(tmp_path))
        response = self.client.post(
            "/api/v1/files/scripts/ok.py",
            json={"content": "print('ok')"},
        )
        assert response.status_code == 200
        assert (tmp_path / "scripts" / "ok.py").read_text(encoding="utf-8") == "print('ok')"

    def test_cors_allow_origins_not_wildcard(self):
        cors_layers = [m for m in ai_ide_main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
        assert len(cors_layers) > 0
        assert "*" not in cors_layers[0].options.get("allow_origins", [])
