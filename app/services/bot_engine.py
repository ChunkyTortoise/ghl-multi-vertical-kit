"""Core bot engine — vertical-agnostic conversation handler.

Given a ``VerticalConfig`` and a user message, this module builds a Claude
prompt, tracks qualification progress, and returns a response.  Swapping
verticals requires only changing the YAML config — no code changes.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models import VerticalConfig

logger = logging.getLogger(__name__)

# Maximum conversation history turns kept (user+assistant pairs)
_MAX_HISTORY_TURNS = 10


def build_system_prompt(vertical: VerticalConfig) -> str:
    """Render the system prompt for Claude from the vertical config.

    The vertical YAML ``system_prompt`` is treated as a template.  The
    following placeholders are expanded:

    - ``{bot_name}`` — persona name
    - ``{tone}`` — persona tone
    - ``{questions}`` — numbered qualification questions
    - ``{disqualification}`` — bullet list of disqualification criteria
    """
    questions_block = "\n".join(
        f"  {i}. {q}" for i, q in enumerate(vertical.qualification_questions, 1)
    )
    disqualification_block = "\n".join(
        f"  - {c}" for c in vertical.disqualification_criteria
    )

    prompt = vertical.system_prompt
    prompt = prompt.replace("{bot_name}", vertical.persona.name)
    prompt = prompt.replace("{tone}", vertical.persona.tone)
    prompt = prompt.replace("{questions}", questions_block)
    prompt = prompt.replace("{disqualification}", disqualification_block)
    return prompt


def _check_response_templates(
    message: str, vertical: VerticalConfig,
) -> Optional[str]:
    """Return a canned response if ``message`` matches a template trigger."""
    lower = message.lower().strip()
    for trigger, response in vertical.response_templates.items():
        if trigger.lower() in lower:
            return response
    return None


def _assess_qualification(
    history: List[Dict[str, str]],
    vertical: VerticalConfig,
) -> Dict[str, Any]:
    """Estimate how many qualification questions have been addressed.

    This is a lightweight heuristic: for each qualification question we
    check whether any *user* message in the history contains keywords
    from that question.  It doesn't replace LLM-based analysis, but
    gives the caller a quick progress snapshot.
    """
    total = len(vertical.qualification_questions)
    if total == 0:
        return {"total": 0, "answered": 0, "remaining": 0, "complete": True}

    answered = 0
    remaining_questions: List[str] = []

    for question in vertical.qualification_questions:
        keywords = _extract_keywords(question)
        if _history_contains_keywords(history, keywords):
            answered += 1
        else:
            remaining_questions.append(question)

    return {
        "total": total,
        "answered": answered,
        "remaining": total - answered,
        "remaining_questions": remaining_questions,
        "complete": answered >= total,
    }


def _extract_keywords(question: str) -> List[str]:
    """Pull meaningful keywords (>= 4 chars) from a question."""
    stop = {"what", "when", "where", "which", "your", "have", "does", "this", "that", "with", "from", "about", "would", "could", "should", "they", "them", "their", "been", "will"}
    words = re.findall(r"[a-zA-Z]{4,}", question.lower())
    return [w for w in words if w not in stop]


def _history_contains_keywords(
    history: List[Dict[str, str]], keywords: List[str],
) -> bool:
    """True if any *user* message in history contains >= 1 keyword."""
    user_text = " ".join(
        m.get("content", "").lower() for m in history if m.get("role") == "user"
    )
    return any(kw in user_text for kw in keywords)


def _check_disqualification(
    message: str, vertical: VerticalConfig,
) -> Optional[str]:
    """Return the matching disqualification reason, or None."""
    lower = message.lower()
    for criterion in vertical.disqualification_criteria:
        keywords = _extract_keywords(criterion)
        if keywords and all(kw in lower for kw in keywords):
            return criterion
    return None


async def generate_response(
    vertical: VerticalConfig,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    contact_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a bot response for a user message.

    Args:
        vertical: Loaded ``VerticalConfig``.
        user_message: The incoming message text.
        conversation_history: Prior ``[{"role": ..., "content": ...}, ...]``.
        contact_info: Optional dict with name/email/phone for personalisation.

    Returns:
        Dict with ``response``, ``model``, ``qualification_progress``, and
        ``disqualified`` (bool).
    """
    history = list(conversation_history or [])

    # 1. Check for canned response templates
    template_response = _check_response_templates(user_message, vertical)
    if template_response:
        return {
            "response": template_response,
            "model": "template",
            "qualification_progress": _assess_qualification(history, vertical),
            "disqualified": False,
        }

    # 2. Check disqualification
    disqualified_reason = _check_disqualification(user_message, vertical)

    # 3. Build Claude prompt
    system_prompt = build_system_prompt(vertical)

    # Inject contact context if available
    if contact_info:
        parts = []
        if contact_info.get("name"):
            parts.append(f"Contact name: {contact_info['name']}")
        if contact_info.get("email"):
            parts.append(f"Email: {contact_info['email']}")
        if contact_info.get("phone"):
            parts.append(f"Phone: {contact_info['phone']}")
        if parts:
            system_prompt += "\n\nCurrent contact info:\n" + "\n".join(parts)

    if disqualified_reason:
        system_prompt += (
            f"\n\nIMPORTANT: The user has indicated: '{disqualified_reason}'. "
            "Politely let them know this may not be the right fit and wish them well."
        )

    # 4. Trim history
    if len(history) > _MAX_HISTORY_TURNS * 2:
        history = history[-(_MAX_HISTORY_TURNS * 2):]

    messages = history + [{"role": "user", "content": user_message}]

    # 5. Call Claude
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            system=system_prompt,
            messages=messages,
        )
        content = resp.content[0].text
        model_used = settings.claude_model
    except Exception as exc:
        logger.error("Claude API error: %s", exc)
        content = vertical.persona.greeting
        model_used = "fallback"

    return {
        "response": content,
        "model": model_used,
        "qualification_progress": _assess_qualification(
            history + [{"role": "user", "content": user_message}],
            vertical,
        ),
        "disqualified": disqualified_reason is not None,
    }
