"""
CredEx SDK Configuration — global state and initialization.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Literal

VerifyLevel = Literal["all", "milestones", "sample", "none"]


@dataclass
class CredExConfig:
    """SDK configuration."""

    api_key: str = ""
    base_url: str = "https://credexai.live"
    verify_level: VerifyLevel = "milestones"
    auto_anchor: bool = True
    auto_memory: bool = True
    sample_rate: float = 0.1  # For verify_level="sample"
    timeout: float = 30.0
    verbose: bool = False
    agent_name: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.environ.get("CREDEX_API_KEY", "")
        if not self.base_url:
            self.base_url = os.environ.get("CREDEX_URL", "https://credexai.live")
        if not self.agent_name:
            self.agent_name = os.environ.get("CREDEX_AGENT_NAME", "sdk-agent")


# Global singleton
_config: Optional[CredExConfig] = None
_client = None


def init(
    api_key: str = "",
    base_url: str = "https://credexai.live",
    verify_level: VerifyLevel = "milestones",
    auto_anchor: bool = True,
    auto_memory: bool = True,
    sample_rate: float = 0.1,
    timeout: float = 30.0,
    verbose: bool = False,
    agent_name: str = "",
    tags: list[str] | None = None,
) -> "CredExConfig":
    """
    Initialize the CredEx SDK. Call once at startup.

    Args:
        api_key: Your CredEx API key (credex_...). Falls back to CREDEX_API_KEY env var.
        base_url: CredEx server URL. Default: https://credexai.live
        verify_level: When to verify — "all", "milestones", "sample", or "none".
        auto_anchor: Automatically anchor verified results to XRPL.
        auto_memory: Automatically store results in CredEx persistent memory.
        sample_rate: Fraction of actions to verify when verify_level="sample".
        timeout: HTTP timeout in seconds.
        verbose: Print SDK activity to stderr.
        agent_name: Name for this agent in CredEx logs.
        tags: Optional tags for organizing actions.

    Returns:
        The initialized CredExConfig.
    """
    global _config, _client

    _config = CredExConfig(
        api_key=api_key,
        base_url=base_url,
        verify_level=verify_level,
        auto_anchor=auto_anchor,
        auto_memory=auto_memory,
        sample_rate=sample_rate,
        timeout=timeout,
        verbose=verbose,
        agent_name=agent_name,
        tags=tags or [],
    )

    # Reset client so it picks up new config
    _client = None

    return _config


def get_config() -> CredExConfig:
    """Get the global config, auto-initializing from env vars if needed."""
    global _config
    if _config is None:
        _config = CredExConfig()
    return _config


def get_client():
    """Get the global CredExClient, creating it if needed."""
    global _client
    if _client is None:
        from credex.client import CredExClient
        _client = CredExClient(get_config())
    return _client
