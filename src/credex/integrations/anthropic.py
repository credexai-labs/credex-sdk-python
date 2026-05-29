"""
CredEx Anthropic Integration — monkey-patch Anthropic client to auto-verify messages.

Usage:
    import credex
    credex.init(api_key="credex_...")
    credex.patch_anthropic()

    from anthropic import Anthropic
    client = Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Explain XRPL consensus"}]
    )
    # CredEx verification happened automatically ✓
"""

from __future__ import annotations

import functools
import random
import sys
from typing import Any

_patched = False


def _should_process() -> bool:
    from credex.config import get_config
    config = get_config()
    if config.verify_level == "all":
        return True
    elif config.verify_level == "none":
        return False
    elif config.verify_level == "sample":
        return random.random() < config.sample_rate
    return True


def _extract_message_text(response: Any) -> str | None:
    """Extract text from an Anthropic Message response."""
    try:
        content = getattr(response, "content", None)
        if content and len(content) > 0:
            texts = []
            for block in content:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif hasattr(block, "type") and block.type == "tool_use":
                    import json
                    texts.append(f"Tool: {block.name}({json.dumps(block.input)[:200]})")
            return "\n".join(texts) if texts else None
    except Exception:
        pass
    return None


def _process_response(response: Any, kwargs: dict):
    """Send the message through CredEx verification + memory."""
    from credex.config import get_client, get_config
    config = get_config()

    text = _extract_message_text(response)
    if not text or len(text.strip()) < 10:
        return

    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user = content[:200]
            break
    context = f"model={model}, prompt={last_user}"

    try:
        client = get_client()
        domain = "general"

        if config.verify_level != "none":
            client.verify(claim=text[:2000], context=context, domain=domain)

        if config.auto_memory:
            client.memory_store(
                content=text[:2000],
                context=context,
                category=domain,
                importance=0.5,
            )

        if config.verbose:
            print(f"[credex-sdk] ✓ Anthropic message verified ({model})", file=sys.stderr)
    except Exception as e:
        if config.verbose:
            print(f"[credex-sdk] ⚠ Anthropic post-process failed: {e}", file=sys.stderr)


def patch(**kwargs):
    """
    Patch Anthropic's Messages.create to auto-verify through CredEx.
    """
    global _patched
    if _patched:
        return

    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Anthropic package not installed. Install with: pip install credex-sdk[anthropic]"
        )

    from anthropic.resources.messages import Messages, AsyncMessages

    # Sync
    _original_create = Messages.create

    @functools.wraps(_original_create)
    def patched_create(self, *args, **kw):
        response = _original_create(self, *args, **kw)
        if _should_process():
            _process_response(response, kw)
        return response

    Messages.create = patched_create

    # Async
    _original_async_create = AsyncMessages.create

    @functools.wraps(_original_async_create)
    async def patched_async_create(self, *args, **kw):
        response = await _original_async_create(self, *args, **kw)
        if _should_process():
            _process_response(response, kw)
        return response

    AsyncMessages.create = patched_async_create

    _patched = True

    from credex.config import get_config
    if get_config().verbose:
        print("[credex-sdk] ✓ Anthropic patched — all messages will be verified", file=sys.stderr)
