"""Shared fixtures for tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.models import VerticalConfig, PersonaConfig


@pytest.fixture
def sample_vertical() -> VerticalConfig:
    return VerticalConfig(
        name="test_vertical",
        persona=PersonaConfig(
            name="TestBot",
            tone="friendly",
            greeting="Hello! How can I help?",
        ),
        qualification_questions=[
            "What service do you need?",
            "What is your budget?",
            "What is your timeline?",
        ],
        disqualification_criteria=[
            "Budget under minimum threshold",
            "Outside service area and unwilling to relocate",
        ],
        booking_enabled=True,
        system_prompt=(
            "You are {bot_name}. Tone: {tone}.\n"
            "Questions:\n{questions}\n"
            "Disqualification:\n{disqualification}"
        ),
        response_templates={
            "stop": "Okay, stopping. Take care!",
            "unsubscribe": "Removed. Goodbye!",
        },
    )


@pytest.fixture
def tmp_verticals(tmp_path: Path) -> Path:
    """Create a temp verticals directory with sample YAML files."""
    v_dir = tmp_path / "verticals"
    v_dir.mkdir()

    (v_dir / "alpha.yaml").write_text(textwrap.dedent("""\
        name: alpha
        persona:
          name: AlphaBot
          tone: professional
          greeting: "Welcome!"
        qualification_questions:
          - "What is your name?"
          - "What do you need?"
        disqualification_criteria:
          - "Not a real customer"
        booking_enabled: false
        system_prompt: "You are {bot_name}. Ask: {questions}"
        response_templates:
          stop: "Bye!"
    """))

    (v_dir / "beta.yaml").write_text(textwrap.dedent("""\
        name: beta
        persona:
          name: BetaBot
          tone: casual
          greeting: "Hey there!"
        qualification_questions: []
        disqualification_criteria: []
        booking_enabled: true
        system_prompt: "You are {bot_name}, a casual assistant."
        response_templates: {}
    """))

    (v_dir / "invalid.yaml").write_text("not: [valid: yaml: {{")

    return v_dir


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from app.main import app
    with TestClient(app) as c:
        yield c
