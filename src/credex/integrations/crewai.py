"""
CredEx CrewAI Integration — step callback and tools for CrewAI agents.

Usage:
    import credex
    from credex.integrations.crewai import credex_step_callback, CredExVerifyTool, CredExMemoryTool

    credex.init()

    # Option 1: Step callback — auto-verify every agent step
    crew = Crew(
        agents=[...],
        tasks=[...],
        step_callback=credex_step_callback,
    )

    # Option 2: Give agents CredEx tools
    from crewai import Agent
    agent = Agent(
        role="Researcher",
        tools=[CredExVerifyTool(), CredExMemoryTool()],
        ...
    )
"""

from __future__ import annotations

import sys
from typing import Any

# Lazy import — provide stub if crewai isn't installed
try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:  # type: ignore[no-redef]
        """Stub when crewai is not installed."""
        name: str = ""
        description: str = ""

        def _run(self, *args: Any, **kwargs: Any) -> str:
            raise ImportError(
                "CrewAI not installed. Install with: pip install credex-sdk[crewai]"
            )


def credex_step_callback(step_output: Any) -> None:
    """
    CrewAI step callback that routes each agent step through CredEx.

    Pass this to ``Crew(step_callback=credex_step_callback)`` to
    automatically verify and store every agent action.

    Args:
        step_output: The step output object from CrewAI.
    """
    from credex.config import get_client, get_config
    config = get_config()

    try:
        # Extract text from step output
        text = ""
        if hasattr(step_output, "output"):
            text = str(step_output.output)
        elif hasattr(step_output, "result"):
            text = str(step_output.result)
        elif isinstance(step_output, str):
            text = step_output
        elif isinstance(step_output, dict):
            text = str(step_output.get("output", step_output.get("result", "")))
        else:
            text = str(step_output)

        if not text or len(text.strip()) < 10:
            return

        text = text[:2000]
        client = get_client()

        # Verify
        if config.verify_level != "none":
            client.verify(claim=text, context="crewai.step", domain="general")

        # Store in memory
        if config.auto_memory:
            client.memory_store(
                content=text,
                context="crewai.step",
                category="general",
                importance=0.5,
            )

        if config.verbose:
            print("[credex-sdk] ✓ CrewAI step verified", file=sys.stderr)

    except Exception as e:
        if config.verbose:
            print(f"[credex-sdk] ⚠ CrewAI step callback failed: {e}", file=sys.stderr)


class CredExVerifyTool(BaseTool):
    """
    CrewAI tool that lets agents verify claims through CredEx consensus.

    Add to an agent's tools list:
        agent = Agent(role="Fact-checker", tools=[CredExVerifyTool()])
    """

    name: str = "credex_verify"
    description: str = (
        "Verify a factual claim using CredEx multi-agent consensus. "
        "Input: the claim to verify as a string. "
        "Returns: verdict (TRUE/FALSE/MIXED), confidence, and explanation."
    )

    def _run(self, claim: str) -> str:
        from credex.config import get_client
        client = get_client()
        result = client.verify(claim=claim, context="crewai.tool", domain="general")
        if isinstance(result, dict):
            verdict = result.get("verdict", "UNKNOWN")
            confidence = result.get("confidence", 0)
            explanation = result.get("explanation", "")
            return f"Verdict: {verdict} (confidence: {confidence}). {explanation}"
        return str(result)


class CredExMemoryTool(BaseTool):
    """
    CrewAI tool that lets agents search CredEx persistent memory.

    Add to an agent's tools list:
        agent = Agent(role="Researcher", tools=[CredExMemoryTool()])
    """

    name: str = "credex_memory_search"
    description: str = (
        "Search the agent's persistent, consensus-verified memory. "
        "Input: a natural language search query. "
        "Returns: matching memories from previous sessions."
    )

    def _run(self, query: str) -> str:
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
