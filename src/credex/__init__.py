"""
CredEx AI SDK — Wrap your agent once, every action gets verified, remembered, and anchored.

Usage:
    import credex

    # Initialize
    credex.init(api_key="credex_...")

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

__version__ = "0.1.0"

from credex.client import CredExClient
from credex.config import CredExConfig, init, get_client
from credex.decorators import verify, remember, audit

# Convenience patchers
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
    "verify",
    "remember",
    "audit",
    "patch_openai",
    "patch_anthropic",
    "CredExClient",
    "CredExConfig",
]
