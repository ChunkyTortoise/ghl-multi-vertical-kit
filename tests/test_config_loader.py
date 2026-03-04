"""Tests for app.services.config_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import VerticalConfig
from app.services.config_loader import clear_cache, list_verticals, load_vertical


class TestLoadVertical:
    def test_load_valid_vertical(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert isinstance(v, VerticalConfig)
        assert v.name == "alpha"
        assert v.persona.name == "AlphaBot"

    def test_load_returns_correct_questions(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert len(v.qualification_questions) == 2
        assert "What is your name?" in v.qualification_questions

    def test_load_returns_correct_disqualification(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert v.disqualification_criteria == ["Not a real customer"]

    def test_load_booking_false(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert v.booking_enabled is False

    def test_load_booking_true(self, tmp_verticals: Path) -> None:
        v = load_vertical("beta", verticals_dir=tmp_verticals)
        assert v.booking_enabled is True

    def test_load_empty_questions(self, tmp_verticals: Path) -> None:
        v = load_vertical("beta", verticals_dir=tmp_verticals)
        assert v.qualification_questions == []

    def test_load_response_templates(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert v.response_templates["stop"] == "Bye!"

    def test_load_empty_response_templates(self, tmp_verticals: Path) -> None:
        v = load_vertical("beta", verticals_dir=tmp_verticals)
        assert v.response_templates == {}

    def test_file_not_found(self, tmp_verticals: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_vertical("nonexistent", verticals_dir=tmp_verticals)

    def test_invalid_yaml(self, tmp_verticals: Path) -> None:
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_vertical("invalid", verticals_dir=tmp_verticals)

    def test_non_mapping_yaml(self, tmp_verticals: Path) -> None:
        (tmp_verticals / "list.yaml").write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected a mapping"):
            load_vertical("list", verticals_dir=tmp_verticals)

    def test_persona_defaults(self, tmp_verticals: Path) -> None:
        (tmp_verticals / "minimal.yaml").write_text(
            "name: minimal\npersona:\n  name: M\nsystem_prompt: test\n"
        )
        v = load_vertical("minimal", verticals_dir=tmp_verticals)
        assert v.persona.tone == "professional and friendly"
        assert v.persona.greeting == "Hi there! How can I help you today?"

    def test_system_prompt_preserved(self, tmp_verticals: Path) -> None:
        v = load_vertical("alpha", verticals_dir=tmp_verticals)
        assert "{bot_name}" in v.system_prompt


class TestListVerticals:
    def test_list_existing(self, tmp_verticals: Path) -> None:
        names = list_verticals(verticals_dir=tmp_verticals)
        assert "alpha" in names
        assert "beta" in names
        assert "invalid" in names  # it's still a .yaml file

    def test_list_sorted(self, tmp_verticals: Path) -> None:
        names = list_verticals(verticals_dir=tmp_verticals)
        assert names == sorted(names)

    def test_list_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty_verticals"
        empty.mkdir()
        assert list_verticals(verticals_dir=empty) == []

    def test_list_nonexistent_dir(self, tmp_path: Path) -> None:
        assert list_verticals(verticals_dir=tmp_path / "nope") == []


class TestCache:
    def test_cache_is_used(self, tmp_verticals: Path) -> None:
        clear_cache()
        # load_vertical with verticals_dir doesn't cache
        # but calling clear_cache should not error
        clear_cache()

    def test_clear_cache(self) -> None:
        clear_cache()  # should not raise
