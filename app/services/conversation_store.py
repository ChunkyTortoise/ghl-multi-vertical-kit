"""Conversation persistence — Redis with in-memory fallback.

Stores conversation history per contact_id so multi-turn demos
and webhook conversations survive across requests.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# TTL for Redis keys (24 hours)
_CONVERSATION_TTL = 86400

# In-memory fallback store
_memory_store: Dict[str, List[Dict[str, str]]] = {}

# Lazily-initialised Redis connection
_redis: Any = None
_redis_available: Optional[bool] = None


async def _get_redis() -> Any:
    """Return a Redis client or None if unavailable."""
    global _redis, _redis_available

    if _redis_available is False:
        return None

    if _redis is not None:
        return _redis

    try:
        import redis.asyncio as aioredis
        from app.config import settings

        if not getattr(settings, "redis_url", ""):
            _redis_available = False
            return None

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        _redis_available = True
        logger.info("Conversation store: using Redis")
        return _redis
    except Exception:
        _redis_available = False
        logger.info("Conversation store: Redis unavailable, using in-memory fallback")
        return None


def _key(contact_id: str) -> str:
    return f"conversation:{contact_id}"


async def get_history(contact_id: str) -> List[Dict[str, str]]:
    """Retrieve conversation history for a contact."""
    r = await _get_redis()
    if r is not None:
        raw = await r.get(_key(contact_id))
        if raw:
            return json.loads(raw)
        return []

    return list(_memory_store.get(contact_id, []))


async def append_message(
    contact_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Append a message and return the updated history."""
    from datetime import datetime

    history = await get_history(contact_id)
    msg: Dict[str, Any] = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if metadata:
        msg.update(metadata)
    history.append(msg)

    r = await _get_redis()
    if r is not None:
        await r.set(_key(contact_id), json.dumps(history), ex=_CONVERSATION_TTL)
    else:
        _memory_store[contact_id] = history

    return history


async def save_history(
    contact_id: str, history: List[Dict[str, str]]
) -> None:
    """Overwrite conversation history for a contact."""
    r = await _get_redis()
    if r is not None:
        await r.set(_key(contact_id), json.dumps(history), ex=_CONVERSATION_TTL)
    else:
        _memory_store[contact_id] = list(history)


async def clear_history(contact_id: str) -> None:
    """Delete conversation history for a contact."""
    r = await _get_redis()
    if r is not None:
        await r.delete(_key(contact_id))
    else:
        _memory_store.pop(contact_id, None)


async def get_all_active_contacts() -> List[str]:
    """List all contact IDs with active conversations."""
    r = await _get_redis()
    if r is not None:
        try:
            keys = await r.keys("conversation:*")
            return [k.replace("conversation:", "") for k in keys]
        except Exception as e:
            logger.warning(f"Redis keys failed: {e}")
            return []

    return list(_memory_store.keys())


def reset_memory_store() -> None:
    """Clear the in-memory store (useful in tests)."""
    _memory_store.clear()
