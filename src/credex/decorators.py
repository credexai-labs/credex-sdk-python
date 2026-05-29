"""
CredEx decorators — wrap any function to auto-verify, remember, or audit.

Usage:
    import credex

    credex.init(api_key="credex_...")

    @credex.verify
    def generate_response(prompt):
        return openai.chat(prompt)

    @credex.remember
    def research(query):
        return search_and_summarize(query)

    @credex.audit
    def critical_action(params):
        return execute(params)  # verify + remember + anchor
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import random
import sys
import time
from typing import Any, Callable, Optional

from credex.config import get_client, get_config


def _should_verify() -> bool:
    """Decide whether to verify based on verify_level config."""
    config = get_config()
    if config.verify_level == "all":
        return True
    elif config.verify_level == "none":
        return False
    elif config.verify_level == "sample":
        return random.random() < config.sample_rate
    elif config.verify_level == "milestones":
        # In decorator mode, treat every decorated call as a milestone
        return True
    return True


def _extract_output(result: Any) -> str:
    """Convert a function result to a string for verification."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        # Common patterns
        for key in ("content", "text", "response", "output", "message", "result"):
            if key in result and isinstance(result[key], str):
                return result[key]
        import json
        return json.dumps(result, default=str)[:2000]
    return str(result)[:2000]


def verify(
    fn: Optional[Callable] = None,
    *,
    domain: str = "general",
    context: str = "",
):
    """
    Decorator: auto-verify function output through CredEx consensus.

    Can be used bare (@credex.verify) or with args (@credex.verify(domain="code")).

    The function runs normally. After it returns, the output is sent to CredEx
    for multi-agent consensus verification in the background (non-blocking for
    sync functions, awaited for async).
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                if _should_verify():
                    try:
                        client = get_client()
                        output = _extract_output(result)
                        ctx = context or f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                        client.verify(claim=output, context=ctx, domain=domain)
                        if get_config().verbose:
                            print(f"[credex-sdk] ✓ verified {func.__name__}", file=sys.stderr)
                    except Exception as e:
                        if get_config().verbose:
                            print(f"[credex-sdk] ⚠ verify failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                if _should_verify():
                    try:
                        client = get_client()
                        output = _extract_output(result)
                        ctx = context or f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                        client.verify(claim=output, context=ctx, domain=domain)
                        if get_config().verbose:
                            print(f"[credex-sdk] ✓ verified {func.__name__}", file=sys.stderr)
                    except Exception as e:
                        if get_config().verbose:
                            print(f"[credex-sdk] ⚠ verify failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return sync_wrapper

    # Support both @credex.verify and @credex.verify(domain="code")
    if fn is not None:
        return decorator(fn)
    return decorator


def remember(
    fn: Optional[Callable] = None,
    *,
    category: str = "general",
    importance: float = 0.5,
):
    """
    Decorator: auto-store function output in CredEx persistent memory.

    The function result is stored as a memory with the given category and importance.
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                try:
                    client = get_client()
                    output = _extract_output(result)
                    ctx = f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                    client.memory_store(content=output, context=ctx, category=category, importance=importance)
                    if get_config().verbose:
                        print(f"[credex-sdk] 📝 remembered {func.__name__}", file=sys.stderr)
                except Exception as e:
                    if get_config().verbose:
                        print(f"[credex-sdk] ⚠ memory failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                try:
                    client = get_client()
                    output = _extract_output(result)
                    ctx = f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                    client.memory_store(content=output, context=ctx, category=category, importance=importance)
                    if get_config().verbose:
                        print(f"[credex-sdk] 📝 remembered {func.__name__}", file=sys.stderr)
                except Exception as e:
                    if get_config().verbose:
                        print(f"[credex-sdk] ⚠ memory failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return sync_wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


def audit(
    fn: Optional[Callable] = None,
    *,
    domain: str = "general",
    category: str = "general",
    importance: float = 0.8,
):
    """
    Decorator: full audit chain — verify + remember + anchor.

    This is the maximum-trust decorator. Every call to the wrapped function
    is verified by consensus, stored in persistent memory, and anchored to XRPL.
    Use for critical actions where you need a complete provenance trail.
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                output = _extract_output(result)
                ctx = f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                try:
                    client = get_client()
                    client.verify(claim=output, context=ctx, domain=domain)
                    client.memory_store(content=output, context=ctx, category=category, importance=importance)
                    if get_config().auto_anchor:
                        client.anchor()
                    if get_config().verbose:
                        print(f"[credex-sdk] 🔒 audited {func.__name__}", file=sys.stderr)
                except Exception as e:
                    if get_config().verbose:
                        print(f"[credex-sdk] ⚠ audit failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                output = _extract_output(result)
                ctx = f"{func.__name__}({', '.join(str(a)[:50] for a in args[:3])})"
                try:
                    client = get_client()
                    client.verify(claim=output, context=ctx, domain=domain)
                    client.memory_store(content=output, context=ctx, category=category, importance=importance)
                    if get_config().auto_anchor:
                        client.anchor()
                    if get_config().verbose:
                        print(f"[credex-sdk] 🔒 audited {func.__name__}", file=sys.stderr)
                except Exception as e:
                    if get_config().verbose:
                        print(f"[credex-sdk] ⚠ audit failed for {func.__name__}: {e}", file=sys.stderr)
                return result
            return sync_wrapper

    if fn is not None:
        return decorator(fn)
    return decorator
