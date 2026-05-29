"""
CredEx OpenAI Integration — monkey-patch OpenAI client to auto-verify completions.

Usage:
    import credex
    credex.init(api_key="credex_...")
    credex.patch_openai()

    # Now every OpenAI completion is automatically verified through CredEx
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "What is quantum computing?"}]
    )
    # CredEx verification happened automatically ✓

How it works:
    1. Patches OpenAI's chat.completions.create (sync + async)
    2. After each completion, extracts the assistant message
    3. Routes it to CredEx for verification + memory storage
    4. Returns the original response unchanged — zero impact on your code
"""

from __future__ import annotations

import functools
import random
import sys
from typing import Any

_patched = False


def _should_process() -> bool:
    """Check if we should verify this request based on config."""
    from credex.config import get_config
    config = get_config()
    if config.verify_level == "all":
        return True
    elif config.verify_level == "none":
        return False
    elif config.verify_level == "sample":
        return random.random() < config.sample_rate
    elif config.verify_level == "milestones":
        return True  # Every completion is a milestone
    return True


def _extract_completion_text(response: Any) -> str | None:
    """Extract text from an OpenAI ChatCompletion response."""
    try:
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            message = choices[0].message
            if hasattr(message, "content") and message.content:
                return message.content
            # Tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                import json
                calls = []
                for tc in message.tool_calls:
                    calls.append(f"{tc.function.name}({tc.function.arguments})")
                return "Tool calls: " + "; ".join(calls)
    except Exception:
        pass
    return None


def _extract_context(kwargs: dict) -> str:
    """Build context string from the request parameters."""
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user = content[:200]
            break
    return f"model={model}, prompt={last_user}"


def _process_response(response: Any, context: str, model: str):
    """Send the completion through CredEx verification + memory."""
    from credex.config import get_client, get_config
    config = get_config()
    text = _extract_completion_text(response)
    if not text or len(text.strip()) < 10:
        return  # Skip trivial responses

    try:
        client = get_client()

        # Determine domain from model
        domain = "general"
        if "code" in model.lower() or "codex" in model.lower():
            domain = "code"

        # Verify
        if config.verify_level != "none":
            client.verify(claim=text[:2000], context=context, domain=domain)

        # Store in memory
        if config.auto_memory:
            client.memory_store(
                content=text[:2000],
                context=context,
                category=domain,
                importance=0.5,
            )

        if config.verbose:
            print(f"[credex-sdk] ✓ OpenAI completion verified ({model})", file=sys.stderr)

    except Exception as e:
        if config.verbose:
            print(f"[credex-sdk] ⚠ OpenAI post-process failed: {e}", file=sys.stderr)


def patch(**kwargs):
    """
    Patch OpenAI's ChatCompletions.create to auto-verify through CredEx.

    Call once after credex.init(). Works with both sync and async clients.
    """
    global _patched
    if _patched:
        return

    try:
        import openai
    except ImportError:
        raise ImportError(
            "OpenAI package not installed. Install with: pip install credex-sdk[openai]"
        )

    from openai.resources.chat.completions import Completions, AsyncCompletions

    # ─── Patch sync create ──────────────────────────────────────────────

    _original_create = Completions.create

    @functools.wraps(_original_create)
    def patched_create(self, *args, **kw):
        response = _original_create(self, *args, **kw)
        if _should_process():
            model = kw.get("model", "unknown")
            context = _extract_context(kw)
            _process_response(response, context, model)
        return response

    Completions.create = patched_create

    # ─── Patch async create ─────────────────────────────────────────────

    _original_async_create = AsyncCompletions.create

    @functools.wraps(_original_async_create)
    async def patched_async_create(self, *args, **kw):
        response = await _original_async_create(self, *args, **kw)
        if _should_process():
            model = kw.get("model", "unknown")
            context = _extract_context(kw)
            _process_response(response, context, model)
        return response

    AsyncCompletions.create = patched_async_create

    _patched = True

    from credex.config import get_config
    if get_config().verbose:
        print("[credex-sdk] ✓ OpenAI patched — all completions will be verified", file=sys.stderr)
