"""
CredEx SDK Configuration — global state and initialization.

Supports zero-friction mode: call credex.init() with no arguments,
and the SDK will auto-provision a free-tier API key behind the scenes.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

VerifyLevel = Literal["all", "milestones", "sample", "none"]

# ─── Credentials file ──────────────────────────────────────────────────
CREDEX_DIR = Path.home() / ".credex"
CREDENTIALS_FILE = CREDEX_DIR / "credentials.json"


def _machine_fingerprint() -> str:
    """Generate a stable machine fingerprint for idempotent provisioning."""
    parts = [
        platform.node(),       # hostname
        os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        platform.system(),
        platform.machine(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _load_credentials() -> Optional[dict]:
    """Load saved credentials from ~/.credex/credentials.json"""
    try:
        if CREDENTIALS_FILE.exists():
            data = json.loads(CREDENTIALS_FILE.read_text())
            if data.get("api_key", "").startswith("credex_"):
                return data
    except (json.JSONDecodeError, OSError, PermissionError):
        pass
    return None


def _save_credentials(api_key: str, agent_id: str, user_id: str, endpoint: str) -> None:
    """Save credentials to ~/.credex/credentials.json"""
    try:
        CREDEX_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps({
            "api_key": api_key,
            "agent_id": agent_id,
            "user_id": user_id,
            "endpoint": endpoint,
            "fingerprint": _machine_fingerprint(),
        }, indent=2))
        # Restrict permissions on credentials file
        try:
            CREDENTIALS_FILE.chmod(0o600)
        except OSError:
            pass  # Windows may not support chmod
    except (OSError, PermissionError) as e:
        print(f"[credex] Warning: could not save credentials to {CREDENTIALS_FILE}: {e}", file=sys.stderr)


def _auto_provision(base_url: str, agent_name: str, verbose: bool) -> Optional[dict]:
    """
    Auto-provision a free-tier API key from the CredEx server.
    
    Returns dict with api_key, agent_id, user_id or None on failure.
    """
    import httpx  # Already a dependency

    url = f"{base_url.rstrip('/')}/api/v1/sdk/provision"
    payload = {
        "fingerprint": _machine_fingerprint(),
        "agent_name": agent_name or "sdk-agent",
        "sdk_version": "0.3.0",
    }

    if verbose:
        print(f"[credex] Auto-provisioning free API key from {base_url}...", file=sys.stderr)

    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        
        if resp.status_code == 429:
            data = resp.json()
            print(
                f"[credex] Rate limited. Try again in {data.get('retry_after_seconds', 60)}s.",
                file=sys.stderr,
            )
            return None

        if resp.status_code in (200, 201):
            data = resp.json()
            api_key = data.get("api_key", "")
            agent_id = data.get("agent_id", "")
            user_id = data.get("user_id", "")
            limits = data.get("limits", {})

            if api_key.startswith("credex_"):
                _save_credentials(api_key, agent_id, user_id, base_url)
                
                if verbose:
                    status = "Resumed existing" if data.get("provisioned") == "existing" else "Created new"
                    print(
                        f"[credex] {status} free-tier account. "
                        f"{limits.get('interactions', 15)} free interactions included. {limits.get('upgrade_note', '')}",
                        file=sys.stderr,
                    )
                return data

        # Non-200 response
        if verbose:
            print(f"[credex] Auto-provision failed (HTTP {resp.status_code}). Pass api_key= explicitly.", file=sys.stderr)
        return None

    except Exception as e:
        if verbose:
            print(f"[credex] Auto-provision failed: {e}. Pass api_key= explicitly.", file=sys.stderr)
        return None


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

    Zero-friction mode: call with no arguments. The SDK will:
    1. Check CREDEX_API_KEY env var
    2. Check ~/.credex/credentials.json for a saved key
    3. Auto-provision a free-tier key from the server (free calls, 14-day trial)

    The provisioned key is saved locally so subsequent runs just work.

    Args:
        api_key: Your CredEx API key (credex_...). Optional — auto-provisions if omitted.
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

    resolved_key = api_key or os.environ.get("CREDEX_API_KEY", "")
    resolved_url = base_url

    # ─── Auto-resolve API key if not provided ───────────────────────────
    if not resolved_key:
        # Step 1: Check saved credentials
        creds = _load_credentials()
        if creds:
            resolved_key = creds["api_key"]
            # Use saved endpoint if base_url wasn't explicitly changed
            if base_url == "https://credexai.live" and creds.get("endpoint"):
                resolved_url = creds["endpoint"]
            if verbose:
                print(f"[credex] Using saved credentials from {CREDENTIALS_FILE}", file=sys.stderr)
        else:
            # Step 2: Auto-provision from server
            result = _auto_provision(resolved_url, agent_name, verbose)
            if result:
                resolved_key = result["api_key"]
            else:
                print(
                    "[credex] No API key found. Set CREDEX_API_KEY env var, "
                    "pass api_key= to init(), or ensure network access for auto-provisioning.",
                    file=sys.stderr,
                )

    _config = CredExConfig(
        api_key=resolved_key,
        base_url=resolved_url,
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
