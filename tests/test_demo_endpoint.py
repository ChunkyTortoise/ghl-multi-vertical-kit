"""Tests for /demo and /verticals endpoints + /health + webhook."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"

    def test_health_includes_vertical(self, client: TestClient) -> None:
        r = client.get("/health")
        assert "vertical" in r.json()

    def test_health_includes_ghl_configured(self, client: TestClient) -> None:
        r = client.get("/health")
        assert "ghl_configured" in r.json()

    def test_health_includes_environment(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.json()["environment"] == "development"


# ---------------------------------------------------------------------------
# /verticals
# ---------------------------------------------------------------------------

class TestListVerticals:
    def test_returns_list(self, client: TestClient) -> None:
        r = client.get("/verticals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_includes_real_estate(self, client: TestClient) -> None:
        r = client.get("/verticals")
        assert "real_estate" in r.json()

    def test_includes_home_services(self, client: TestClient) -> None:
        r = client.get("/verticals")
        assert "home_services" in r.json()

    def test_includes_legal(self, client: TestClient) -> None:
        r = client.get("/verticals")
        assert "legal" in r.json()


# ---------------------------------------------------------------------------
# /demo
# ---------------------------------------------------------------------------

class TestDemoEndpoint:
    def test_missing_user_message_422(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "real_estate"})
        assert r.status_code == 422

    def test_unknown_vertical_404(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "nonexistent", "user_message": "hi"})
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]

    def test_template_response(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "real_estate", "user_message": "stop"})
        assert r.status_code == 200
        data = r.json()
        assert "stop" in data["response"].lower() or "messaging" in data["response"].lower()
        assert data["vertical"] == "real_estate"

    def test_returns_bot_name(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "real_estate", "user_message": "stop"})
        assert r.json()["bot_name"] == "Alex"

    def test_home_services_template(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "home_services", "user_message": "how much"})
        assert r.status_code == 200
        assert "estimate" in r.json()["response"].lower()

    def test_legal_template(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "legal", "user_message": "how much"})
        assert r.status_code == 200
        assert "fees" in r.json()["response"].lower() or "attorney" in r.json()["response"].lower()

    def test_demo_with_history(self, client: TestClient) -> None:
        r = client.post("/demo", json={
            "vertical": "real_estate",
            "user_message": "stop",
            "conversation_history": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
        })
        assert r.status_code == 200

    def test_demo_with_contact_info(self, client: TestClient) -> None:
        r = client.post("/demo", json={
            "vertical": "real_estate",
            "user_message": "stop",
            "contact_info": {"name": "Jane", "email": "jane@test.com"},
        })
        assert r.status_code == 200

    def test_qualification_progress_returned(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "real_estate", "user_message": "stop"})
        data = r.json()
        assert "qualification_progress" in data
        assert "total" in data["qualification_progress"]

    def test_demo_response_model_field(self, client: TestClient) -> None:
        r = client.post("/demo", json={"vertical": "real_estate", "user_message": "stop"})
        assert "model" in r.json()


# ---------------------------------------------------------------------------
# /api/ghl/webhook
# ---------------------------------------------------------------------------

class TestWebhookEndpoint:
    def test_missing_contact_id(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={"body": "hello"})
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_empty_message_skipped(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={"contactId": "c123", "body": ""})
        assert r.json()["status"] == "skipped"

    def test_whitespace_message_skipped(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={"contactId": "c123", "body": "   "})
        assert r.json()["status"] == "skipped"

    def test_processes_valid_payload(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={
            "contactId": "c123",
            "body": "stop",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "processed"
        assert data["contact_id"] == "c123"

    def test_webhook_vertical_in_response(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={"contactId": "c123", "body": "stop"})
        assert r.json()["vertical"] == "real_estate"

    def test_webhook_long_message_truncated(self, client: TestClient) -> None:
        long_msg = "x" * 3000
        r = client.post("/api/ghl/webhook", json={"contactId": "c123", "body": long_msg})
        assert r.status_code == 200

    def test_webhook_alternate_field_names(self, client: TestClient) -> None:
        r = client.post("/api/ghl/webhook", json={
            "contact_id": "c456",
            "message": "stop",
        })
        assert r.status_code == 200
        assert r.json()["contact_id"] == "c456"


# ---------------------------------------------------------------------------
# Vertical YAML validation (integration with real files)
# ---------------------------------------------------------------------------

class TestRealVerticals:
    """Validate that all shipped YAML files load correctly."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        from app.services.config_loader import clear_cache
        clear_cache()

    def test_real_estate_loads(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("real_estate")
        assert v.name == "real_estate"
        assert len(v.qualification_questions) >= 5
        assert v.booking_enabled is True

    def test_home_services_loads(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("home_services")
        assert v.name == "home_services"
        assert len(v.qualification_questions) >= 5
        assert v.booking_enabled is True

    def test_legal_loads(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("legal")
        assert v.name == "legal"
        assert len(v.qualification_questions) >= 5
        assert v.booking_enabled is True

    def test_real_estate_has_response_templates(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("real_estate")
        assert "stop" in v.response_templates

    def test_legal_system_prompt_has_disclaimer(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("legal")
        assert "legal advice" in v.system_prompt.lower() or "attorney" in v.system_prompt.lower()

    def test_home_services_emergency_template(self) -> None:
        from app.services.config_loader import load_vertical
        v = load_vertical("home_services")
        assert "emergency" in v.response_templates
