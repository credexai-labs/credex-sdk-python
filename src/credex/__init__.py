"""
CredEx AI SDK — Wrap your agent once, every action gets verified, remembered, and anchored.

Usage:
    import credex

    # Zero-friction — no API key needed, auto-provisions on first use
    credex.init()

    # Verify a claim (one-liner)
    result = credex.check("The speed of light is 299,792,458 m/s")
    print(result["verdict"])  # TRUE

    # Store a memory
    credex.store("User prefers Python over JavaScript")

    # Search memory
    results = credex.search("user language preferences")

    # Patch OpenAI (auto-verify all completions)
    credex.patch_openai()

    # Or patch Anthropic
    credex.patch_anthropic()

    # Or use the decorator for any function
    @credex.verify
    def my_agent_action(input):
        return llm.generate(input)

    # Or use the LangChain callback
    from credex.integrations.langchain import CredExHandler
    chain.invoke(input, config={"callbacks": [CredExHandler()]})
"""

__version__ = "0.4.0"

from credex.client import CredExClient
from credex.config import CredExConfig, init, get_client

from credex.decorators import verify, remember, audit


# ─── Convenience one-liners ────────────────────────────────────────────


def check(
    claim: str,
    context: str = "",
    domain: str = "general",
    source_agent: str = "",
) -> dict:
    """
    Verify a claim through CredEx multi-agent consensus.

    Returns dict with verdict ("TRUE"/"FALSE"/"MIXED"), confidence (0-1),
    explanation, and xrpl_txid.

    Example:
        result = credex.check("The Earth orbits the Sun")
        print(result["verdict"])  # "TRUE"
    """
    return get_client().verify(
        claim=claim, context=context, domain=domain, source_agent=source_agent,
    )


def store(
    content: str,
    context: str = "",
    category: str = "general",
    importance: float = 0.5,
) -> dict:
    """
    Store content in CredEx persistent memory with consensus verification.

    Returns dict with memory_id, status, and consensus_details.

    Example:
        credex.store("User prefers dark mode", category="preference")
    """
    return get_client().memory_store(
        content=content, context=context, category=category, importance=importance,
    )


def search(query: str, limit: int = 5) -> dict:
    """
    Search CredEx memory semantically.

    Returns dict with matching memory entries.

    Example:
        results = credex.search("user preferences")
    """
    return get_client().memory_search(query=query, limit=limit)


# ─── Convenience patchers ──────────────────────────────────────────────


def patch_openai(**kwargs):
    """Patch the OpenAI client to auto-verify all completions through CredEx."""
    from credex.integrations.openai import patch
    return patch(**kwargs)


def patch_anthropic(**kwargs):
    """Patch the Anthropic client to auto-verify all messages through CredEx."""
    from credex.integrations.anthropic import patch
    return patch(**kwargs)


__all__ = [
    "init",
    "get_client",
    "check",
    "store",
    "search",
    "verify",
    "remember",
    "audit",
    "patch_openai",
    "patch_anthropic",
    "CredExClient",
    "CredExConfig",
]
