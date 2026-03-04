"""Tests for app.services.bot_engine."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import PersonaConfig, VerticalConfig
from app.services.bot_engine import (
    _assess_qualification,
    _check_disqualification,
    _check_response_templates,
    _extract_keywords,
    _history_contains_keywords,
    build_system_prompt,
    generate_response,
)


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    def test_replaces_bot_name(self, sample_vertical: VerticalConfig) -> None:
        prompt = build_system_prompt(sample_vertical)
        assert "TestBot" in prompt
        assert "{bot_name}" not in prompt

    def test_replaces_tone(self, sample_vertical: VerticalConfig) -> None:
        prompt = build_system_prompt(sample_vertical)
        assert "friendly" in prompt
        assert "{tone}" not in prompt

    def test_replaces_questions(self, sample_vertical: VerticalConfig) -> None:
        prompt = build_system_prompt(sample_vertical)
        assert "What service do you need?" in prompt
        assert "What is your budget?" in prompt
        assert "{questions}" not in prompt

    def test_questions_are_numbered(self, sample_vertical: VerticalConfig) -> None:
        prompt = build_system_prompt(sample_vertical)
        assert "1. What service" in prompt
        assert "2. What is your budget" in prompt

    def test_replaces_disqualification(self, sample_vertical: VerticalConfig) -> None:
        prompt = build_system_prompt(sample_vertical)
        assert "Budget under minimum threshold" in prompt
        assert "{disqualification}" not in prompt

    def test_empty_questions(self) -> None:
        v = VerticalConfig(
            name="empty", persona=PersonaConfig(name="Bot"),
            system_prompt="Questions:\n{questions}\nEnd",
        )
        prompt = build_system_prompt(v)
        assert "Questions:\n\nEnd" in prompt


# ---------------------------------------------------------------------------
# _check_response_templates
# ---------------------------------------------------------------------------

class TestResponseTemplates:
    def test_match_exact(self, sample_vertical: VerticalConfig) -> None:
        assert _check_response_templates("stop", sample_vertical) == "Okay, stopping. Take care!"

    def test_match_case_insensitive(self, sample_vertical: VerticalConfig) -> None:
        assert _check_response_templates("STOP", sample_vertical) is not None

    def test_match_substring(self, sample_vertical: VerticalConfig) -> None:
        assert _check_response_templates("please stop messaging me", sample_vertical) is not None

    def test_no_match(self, sample_vertical: VerticalConfig) -> None:
        assert _check_response_templates("I want to buy a house", sample_vertical) is None

    def test_empty_templates(self) -> None:
        v = VerticalConfig(name="t", persona=PersonaConfig(name="B"), response_templates={})
        assert _check_response_templates("stop", v) is None


# ---------------------------------------------------------------------------
# _extract_keywords
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_extracts_long_words(self) -> None:
        kws = _extract_keywords("What is your budget range?")
        assert "budget" in kws
        assert "range" in kws  # 5 chars, not a stop word

    def test_filters_stop_words(self) -> None:
        kws = _extract_keywords("What would your timeline be?")
        assert "would" not in kws
        assert "your" not in kws
        assert "timeline" in kws

    def test_short_words_excluded(self) -> None:
        kws = _extract_keywords("Do you own a car?")
        assert "own" not in kws
        assert "car" not in kws

    def test_empty_string(self) -> None:
        assert _extract_keywords("") == []


# ---------------------------------------------------------------------------
# _history_contains_keywords
# ---------------------------------------------------------------------------

class TestHistoryContainsKeywords:
    def test_keyword_present_in_user_message(self) -> None:
        history = [{"role": "user", "content": "My budget is $500k"}]
        assert _history_contains_keywords(history, ["budget"]) is True

    def test_keyword_in_assistant_ignored(self) -> None:
        history = [{"role": "assistant", "content": "What is your budget?"}]
        assert _history_contains_keywords(history, ["budget"]) is False

    def test_no_match(self) -> None:
        history = [{"role": "user", "content": "Hello there"}]
        assert _history_contains_keywords(history, ["budget"]) is False

    def test_empty_history(self) -> None:
        assert _history_contains_keywords([], ["budget"]) is False

    def test_empty_keywords(self) -> None:
        history = [{"role": "user", "content": "anything"}]
        assert _history_contains_keywords(history, []) is False


# ---------------------------------------------------------------------------
# _assess_qualification
# ---------------------------------------------------------------------------

class TestAssessQualification:
    def test_no_questions_is_complete(self) -> None:
        v = VerticalConfig(name="t", persona=PersonaConfig(name="B"), qualification_questions=[])
        result = _assess_qualification([], v)
        assert result["complete"] is True
        assert result["total"] == 0

    def test_no_history_zero_answered(self, sample_vertical: VerticalConfig) -> None:
        result = _assess_qualification([], sample_vertical)
        assert result["answered"] == 0
        assert result["remaining"] == 3
        assert result["complete"] is False

    def test_partial_answers(self, sample_vertical: VerticalConfig) -> None:
        history = [
            {"role": "user", "content": "I need plumbing service"},
            {"role": "assistant", "content": "Great, what's your budget?"},
        ]
        result = _assess_qualification(history, sample_vertical)
        assert result["answered"] >= 1
        assert result["complete"] is False

    def test_all_answered(self, sample_vertical: VerticalConfig) -> None:
        history = [
            {"role": "user", "content": "I need plumbing service"},
            {"role": "user", "content": "My budget is $5000"},
            {"role": "user", "content": "My timeline is next week"},
        ]
        result = _assess_qualification(history, sample_vertical)
        assert result["answered"] == 3
        assert result["complete"] is True

    def test_remaining_questions_listed(self, sample_vertical: VerticalConfig) -> None:
        history = [{"role": "user", "content": "I need repair service"}]
        result = _assess_qualification(history, sample_vertical)
        assert len(result["remaining_questions"]) > 0


# ---------------------------------------------------------------------------
# _check_disqualification
# ---------------------------------------------------------------------------

class TestCheckDisqualification:
    def test_matching_criterion(self, sample_vertical: VerticalConfig) -> None:
        result = _check_disqualification(
            "My budget is under the minimum threshold",
            sample_vertical,
        )
        assert result is not None
        assert "minimum" in result.lower() or "budget" in result.lower()

    def test_no_match(self, sample_vertical: VerticalConfig) -> None:
        result = _check_disqualification("I'd like to buy a house", sample_vertical)
        assert result is None

    def test_empty_criteria(self) -> None:
        v = VerticalConfig(name="t", persona=PersonaConfig(name="B"), disqualification_criteria=[])
        assert _check_disqualification("anything", v) is None


# ---------------------------------------------------------------------------
# generate_response (mocked Claude)
# ---------------------------------------------------------------------------

class TestGenerateResponse:
    @pytest.mark.asyncio
    async def test_template_response_bypasses_claude(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        result = await generate_response(sample_vertical, "stop")
        assert result["response"] == "Okay, stopping. Take care!"
        assert result["model"] == "template"
        assert result["disqualified"] is False

    @pytest.mark.asyncio
    async def test_unsubscribe_template(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        result = await generate_response(sample_vertical, "unsubscribe")
        assert result["response"] == "Removed. Goodbye!"
        assert result["model"] == "template"

    @pytest.mark.asyncio
    async def test_claude_called_for_normal_message(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Sure, I can help with that!")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await generate_response(sample_vertical, "I need help with plumbing")

        assert result["response"] == "Sure, I can help with that!"
        assert result["model"] != "template"
        assert result["disqualified"] is False

    @pytest.mark.asyncio
    async def test_contact_info_injected(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Hi John!")]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await generate_response(
                sample_vertical, "Hello",
                contact_info={"name": "John", "email": "j@test.com"},
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "John" in call_kwargs["system"]
        assert "j@test.com" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_history_trimmed(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Response")]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        # 30 messages = 15 turns > 10 turn limit
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(30)
        ]

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            await generate_response(
                sample_vertical, "new message",
                conversation_history=long_history,
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        # 20 trimmed + 1 new = 21
        assert len(call_kwargs["messages"]) == 21

    @pytest.mark.asyncio
    async def test_claude_error_fallback(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        with patch("anthropic.AsyncAnthropic", side_effect=Exception("API down")):
            result = await generate_response(sample_vertical, "Hello")

        assert result["response"] == sample_vertical.persona.greeting
        assert result["model"] == "fallback"

    @pytest.mark.asyncio
    async def test_qualification_progress_returned(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        result = await generate_response(sample_vertical, "stop")
        progress = result["qualification_progress"]
        assert "total" in progress
        assert "answered" in progress
        assert "remaining" in progress

    @pytest.mark.asyncio
    async def test_disqualification_detected(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Sorry, not a fit.")]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await generate_response(
                sample_vertical,
                "My budget is under the minimum threshold and I can't go higher",
            )

        assert result["disqualified"] is True

    @pytest.mark.asyncio
    async def test_empty_history_defaults_to_list(
        self, sample_vertical: VerticalConfig,
    ) -> None:
        result = await generate_response(sample_vertical, "stop", conversation_history=None)
        assert result["response"] is not None
