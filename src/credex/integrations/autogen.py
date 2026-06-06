"""
CredEx AutoGen Integration — message hook and tools for AutoGen agents.

Usage:
    import credex
    from credex.integrations.autogen import credex_message_hook, credex_verify_tool, credex_memory_tool

    credex.init()

    # Option 1: Message hook — auto-verify outgoing messages
    from autogen import ConversableAgent

    agent = ConversableAgent("assistant", ...)
    agent.register_hook("process_message_before_send", credex_message_hook)

    # Option 2: Register CredEx as callable tools
    from autogen import register_function

    register_function(
        credex_verify_tool,
        caller=assistant,
        executor=executor,
        name="credex_verify",
        description="Verify a claim using CredEx multi-agent consensus",
    )
"""

from __future__ import annotations

import sys
from typing import Any, Optional


def credex_message_hook(
    sender: Any,
    message: Any,
    recipient: Any,
    silent: bool,
) -> Any:
    """
    AutoGen message hook that routes outgoing messages through CredEx.

    Register with:
        agent.register_hook("process_message_before_send", credex_message_hook)

    The message is verified and stored but never modified — the original
    message is always returned unchanged.
    """
    from credex.config import get_client, get_config
    config = get_config()

    try:
        # Extract text content
        text = ""
        if isinstance(message, str):
            text = message
        elif isinstance(message, dict):
            text = message.get("content", "")
            if isinstance(text, list):
                # Multi-modal content blocks
                text = " ".join(
                    item.get("text", "") for item in text
                    if isinstance(item, dict) and item.get("type") == "text"
                )
        else:
            text = str(message)

        if not text or len(text.strip()) < 10:
            return message

        text = text[:2000]

        # Build context from sender/recipient
        sender_name = getattr(sender, "name", "agent") if sender else "agent"
        recipient_name = getattr(recipient, "name", "agent") if recipient else "agent"
        context = f"autogen.message {sender_name} → {recipient_name}"

        client = get_client()

        if config.verify_level != "none":
            client.verify(claim=text, context=context, domain="general")

        if config.auto_memory:
            client.memory_store(
                content=text,
                context=context,
                category="general",
                importance=0.5,
            )

        if config.verbose:
            print(f"[credex-sdk] ✓ AutoGen message verified ({sender_name})", file=sys.stderr)

    except Exception as e:
        if config.verbose:
            print(f"[credex-sdk] ⚠ AutoGen hook failed: {e}", file=sys.stderr)

    # Always return the original message unchanged
    return message


def credex_verify_tool(claim: str) -> str:
    """
    Verify a factual claim using CredEx multi-agent consensus.

    Register as an AutoGen tool:
        register_function(credex_verify_tool, caller=..., executor=...,
                          name="credex_verify",
                          description="Verify a claim using CredEx consensus")

    Args:
        claim: The statement to verify.

    Returns:
        A string with the verdict, confidence, and explanation.
    """
    from credex.config import get_client
    client = get_client()
    result = client.verify(claim=claim, context="autogen.tool", domain="general")
    if isinstance(result, dict):
        verdict = result.get("verdict", "UNKNOWN")
        confidence = result.get("confidence", 0)
        explanation = result.get("explanation", "")
        return f"Verdict: {verdict} (confidence: {confidence}). {explanation}"
    return str(result)


def credex_memory_tool(query: str) -> str:
    """
    Search the agent's persistent, consensus-verified memory.

    Register as an AutoGen tool:
        register_function(credex_memory_tool, caller=..., executor=...,
                          name="credex_memory_search",
                          description="Search persistent verified memory")

    Args:
        query: Natural language search query.

    Returns:
        Matching memories from previous sessions.
    """
    from credex.config import get_client
    client = get_client()
    result = client.memory_search(query=query, limit=5)
    if isinstance(result, dict):
        entries = result.get("entries", [])
        if not entries:
            return "No matching memories found."
        lines = []
        for entry in entries:
            content = entry.get("content", "")
            ts = entry.get("timestamp", "")
            lines.append(f"- [{ts}] {content}")
        return "\n".join(lines)
    return str(result)
