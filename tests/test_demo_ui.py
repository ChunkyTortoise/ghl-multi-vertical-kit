"""Tests for GET /demo/ui and GET /demo/config/{vertical} endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestDemoUI:
    def test_demo_ui_returns_200(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert r.status_code == 200

    def test_demo_ui_content_type_html(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "text/html" in r.headers["content-type"]

    def test_demo_ui_contains_vertical_selector(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "vertical-selector" in r.text

    def test_demo_ui_contains_chat_panel(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "chat-panel" in r.text

    def test_demo_ui_contains_user_input(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "user-input" in r.text

    def test_demo_ui_references_demo_api(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "/demo" in r.text

    def test_demo_ui_references_verticals_api(self, client: TestClient) -> None:
        r = client.get("/demo/ui")
        assert "/verticals" in r.text

    def test_demo_ui_not_in_openapi_schema(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        assert "/demo/ui" not in schema.get("paths", {})


class TestDemoConfig:
    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        from app.services.config_loader import clear_cache
        clear_cache()

    def test_config_real_estate_200(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        assert r.status_code == 200

    def test_config_real_estate_bot_name(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        assert r.json()["bot_name"] == "Alex"

    def test_config_real_estate_has_questions(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        data = r.json()
        assert "qualification_questions" in data
        assert len(data["qualification_questions"]) >= 5

    def test_config_home_services_bot_name(self, client: TestClient) -> None:
        r = client.get("/demo/config/home_services")
        assert r.status_code == 200
        assert r.json()["bot_name"] == "Sam"

    def test_config_legal_bot_name(self, client: TestClient) -> None:
        r = client.get("/demo/config/legal")
        assert r.status_code == 200
        assert r.json()["bot_name"] == "Jordan"

    def test_config_includes_rendered_prompt(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        data = r.json()
        assert "system_prompt_rendered" in data
        assert len(data["system_prompt_rendered"]) > 0

    def test_config_rendered_prompt_has_bot_name(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        rendered = r.json()["system_prompt_rendered"]
        assert "Alex" in rendered

    def test_config_includes_response_templates(self, client: TestClient) -> None:
        r = client.get("/demo/config/real_estate")
        data = r.json()
        assert "response_templates" in data
        assert "stop" in data["response_templates"]

    def test_config_unknown_vertical_404(self, client: TestClient) -> None:
        r = client.get("/demo/config/nonexistent")
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]

    def test_config_all_verticals_consistent(self, client: TestClient) -> None:
        required_keys = {
            "name", "bot_name", "tone", "greeting",
            "qualification_questions", "disqualification_criteria",
            "booking_enabled", "response_templates", "system_prompt_rendered",
        }
        for vertical in ("real_estate", "home_services", "legal"):
            r = client.get(f"/demo/config/{vertical}")
            assert r.status_code == 200, f"{vertical} returned {r.status_code}"
            data = r.json()
            missing = required_keys - set(data.keys())
            assert not missing, f"{vertical} missing keys: {missing}"
