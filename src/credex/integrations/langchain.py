"""
CredEx LangChain Integration — callback handler that auto-routes actions through CredEx.

Usage:
    import credex
    from credex.integrations.langchain import CredExHandler

    credex.init(api_key="credex_...")

    handler = CredExHandler()

    # Works with any LangChain chain, agent, or tool
    chain.invoke(input, config={"callbacks": [handler]})

    # Or set globally
    from langchain_core.globals import set_llm_cache
    # ... use handler in RunnableConfig

Events captured:
    - on_llm_end: Every LLM completion → verified + stored
    - on_chain_end: Chain outputs → stored in memory
    - on_tool_end: Tool results → verified (tool outputs are high-value)
    - on_agent_finish: Final agent answer → verified + anchored
"""

from __future__ import annotations

import random
import sys
from typing import Any, Optional
from uuid import UUID


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


try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    # Provide a stub so the module can be imported without langchain
    class BaseCallbackHandler:
        pass


class CredExHandler(BaseCallbackHandler):
    """
    LangChain callback handler that routes actions through CredEx.

    Intercepts LLM completions, tool results, chain outputs, and agent
    finishes. Each event is verified and/or stored in CredEx memory
    based on the configured verify_level.
    """

    name = "credex"

    def __init__(
        self,
        verify_llm: bool = True,
        verify_tools: bool = True,
        verify_chains: bool = False,
        remember_all: bool = True,
        domain: str = "general",
    ):
        """
        Args:
            verify_llm: Verify LLM completions (default True).
            verify_tools: Verify tool outputs (default True).
            verify_chains: Verify chain outputs (default False — usually redundant with LLM).
            remember_all: Store all events in CredEx memory (default True).
            domain: Domain hint for verification.
        """
        super().__init__()
        self.verify_llm = verify_llm
        self.verify_tools = verify_tools
        self.verify_chains = verify_chains
        self.remember_all = remember_all
        self.domain = domain

    def _process(self, content: str, context: str, do_verify: bool, importance: float = 0.5):
        """Route content through CredEx."""
        if not content or len(content.strip()) < 10:
            return
        if not _should_process():
            return

        from credex.config import get_client, get_config
        config = get_config()

        try:
            client = get_client()
            text = content[:2000]

            if do_verify and config.verify_level != "none":
                client.verify(claim=text, context=context, domain=self.domain)

            if self.remember_all and config.auto_memory:
                client.memory_store(
                    content=text,
                    context=context,
                    category=self.domain,
                    importance=importance,
                )

            if config.verbose:
                action = "verified + stored" if do_verify else "stored"
                print(f"[credex-sdk] ✓ LangChain event {action}", file=sys.stderr)
        except Exception as e:
            from credex.config import get_config
            if get_config().verbose:
                print(f"[credex-sdk] ⚠ LangChain callback failed: {e}", file=sys.stderr)

    # ─── LLM Events ────────────────────────────────────────────────────

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when an LLM finishes generating."""
        try:
            # LangChain LLMResult has .generations list
            generations = getattr(response, "generations", [])
            for gen_list in generations:
                for gen in gen_list:
                    text = getattr(gen, "text", "") or ""
                    if hasattr(gen, "message"):
                        msg = gen.message
                        text = getattr(msg, "content", text) or text
                    if text:
                        model = kwargs.get("name", "llm")
                        self._process(text, f"langchain.llm.{model}", self.verify_llm)
        except Exception:
            pass

    # ─── Tool Events ────────────────────────────────────────────────────

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when a tool finishes."""
        name = kwargs.get("name", "tool")
        self._process(str(output), f"langchain.tool.{name}", self.verify_tools, importance=0.7)

    # ─── Chain Events ───────────────────────────────────────────────────

    def on_chain_end(self, outputs: dict, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when a chain finishes."""
        if not self.verify_chains and not self.remember_all:
            return
        try:
            # Extract output text
            text = ""
            if isinstance(outputs, dict):
                for key in ("output", "text", "result", "answer", "response"):
                    if key in outputs:
                        text = str(outputs[key])
                        break
                if not text:
                    text = str(outputs)[:500]
            elif isinstance(outputs, str):
                text = outputs
            else:
                text = str(outputs)[:500]

            name = kwargs.get("name", "chain")
            self._process(text, f"langchain.chain.{name}", self.verify_chains, importance=0.6)
        except Exception:
            pass

    # ─── Agent Events ───────────────────────────────────────────────────

    def on_agent_finish(self, finish, *, run_id: UUID, **kwargs: Any) -> None:
        """Called when an agent finishes — always verify the final answer."""
        try:
            output = getattr(finish, "return_values", {})
            text = output.get("output", "") if isinstance(output, dict) else str(output)
            self._process(text, "langchain.agent.finish", True, importance=0.9)
        except Exception:
            pass
