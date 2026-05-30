"""
CredEx API Client — communicates with the CredEx MCP server via JSON-RPC.

All CredEx operations go through the MCP endpoint as JSON-RPC 2.0 calls.
Auth: Bearer token using the credex_ API key.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from typing import Any, Optional

import httpx

from credex.config import CredExConfig


class CredExError(Exception):
    """Error from the CredEx API."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"CredEx error {code}: {message}")


class CredExClient:
    """
    Client for the CredEx MCP server.

    Uses JSON-RPC 2.0 over HTTP POST to /mcp.
    """

    def __init__(self, config: Optional[CredExConfig] = None):
        if config is None:
            from credex.config import get_config
            config = get_config()
        self.config = config
        self._http = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
                "User-Agent": f"credex-sdk/0.3.0",
            },
        )
        self._request_id = 0
        self._agent_id: Optional[str] = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a CredEx MCP tool via JSON-RPC.

        Returns the parsed result text (JSON-decoded if possible).
        """
        request_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        if self.config.verbose:
            print(f"[credex-sdk] → {tool_name}({json.dumps(arguments)[:200]})", file=sys.stderr)

        start = time.monotonic()
        resp = self._http.post("/mcp", json=payload)
        elapsed = time.monotonic() - start

        if resp.status_code != 200:
            raise CredExError(-1, f"HTTP {resp.status_code}: {resp.text[:500]}")

        body = resp.json()

        if "error" in body:
            err = body["error"]
            raise CredExError(err.get("code", -1), err.get("message", "Unknown error"), err.get("data"))

        result = body.get("result", {})
        content = result.get("content", [])

        if self.config.verbose:
            print(f"[credex-sdk] ← {tool_name} ({elapsed:.2f}s)", file=sys.stderr)

        # Extract text from MCP content blocks
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        combined = "\n".join(texts)

        # Try JSON parse
        try:
            return json.loads(combined)
        except (json.JSONDecodeError, TypeError):
            return combined

    def _get_agent_id(self) -> str:
        """
        Get or auto-provision the hub_agents ID for this SDK instance.

        On first call, uses the credex_sdk_init tool to create or retrieve
        an SDK agent for the authenticated user. The agent_id is cached
        for all subsequent calls within this client instance.
        """
        if self._agent_id:
            return self._agent_id

        agent_name = self.config.agent_name or "sdk-agent"
        try:
            result = self._call_tool("credex_sdk_init", {
                "name": agent_name,
                "tags": self.config.tags,
            })
            if isinstance(result, dict) and result.get("agent_id"):
                self._agent_id = result["agent_id"]
                if self.config.verbose:
                    print(f"[credex-sdk] Agent ready: {self._agent_id} ({agent_name})", file=sys.stderr)
                return self._agent_id
        except CredExError as e:
            if self.config.verbose:
                print(f"[credex-sdk] Agent init failed: {e}", file=sys.stderr)
            raise

        raise CredExError(-1, "Could not provision an agent_id. Check your API key.")

    # ─── Core Verification ──────────────────────────────────────────────

    def verify(
        self,
        claim: str,
        context: str = "",
        domain: str = "general",
        source_agent: str = "",
    ) -> dict:
        """
        Submit a claim for multi-agent consensus verification.

        Args:
            claim: The statement or output to verify.
            context: Additional context for verifiers.
            domain: Domain hint (general, code, math, science, etc.)
            source_agent: Name of the agent that produced the claim.

        Returns:
            Dict with verdict, confidence, explanation, tx_hash, etc.
        """
        return self._call_tool("credex_verify", {
            "claim": claim,
            "context": f"[sdk:{self.config.agent_name}] {context}".strip(),
            "domain": domain,
            "source_agent": source_agent or self.config.agent_name,
        })

    # ─── Memory ─────────────────────────────────────────────────────────

    def memory_store(
        self,
        content: str,
        context: str = "",
        category: str = "general",
        importance: float = 0.5,
    ) -> dict:
        """
        Store content in CredEx persistent memory.

        Args:
            content: The content to remember.
            context: Context about when/why this was stored.
            category: Memory category (general, code, conversation, fact, etc.)
            importance: 0.0–1.0 importance score.

        Returns:
            Dict with memory_id, anchored status, etc.
        """
        agent_id = self._get_agent_id()
        return self._call_tool("credex_memory_store", {
            "agent_id": agent_id,
            "content": content,
            "context": context,
            "metadata": {"category": category, "importance": importance, "source": "credex-sdk"},
        })

    def memory_search(self, query: str, limit: int = 5) -> dict:
        """
        Search CredEx memory semantically.

        Args:
            query: Natural language search query.
            limit: Max results to return.

        Returns:
            Dict with matching memories.
        """
        agent_id = self._get_agent_id()
        return self._call_tool("credex_memory_search", {
            "query": query,
            "agent_id": agent_id,
            "limit": limit,
        })

    # ─── Trust & Anchoring ──────────────────────────────────────────────

    def trust_score(self, agent_id: str = "") -> dict:
        """Get trust score for an agent (defaults to current SDK agent)."""
        if not agent_id:
            agent_id = self._get_agent_id()
        return self._call_tool("credex_trust_score", {"agent_id": agent_id})

    def anchor(self) -> dict:
        """
        Anchor recent memory entries to XRPL.

        Computes a Merkle root of the agent's recent memory entries and anchors
        the proof on the XRP Ledger. Returns tx_hash, memo, and timestamp.

        Note: This anchors the current agent's memory entries (Patents 1-2).
        """
        agent_id = self._get_agent_id()
        return self._call_tool("credex_anchor", {
            "agent_id": agent_id,
        })

    # ─── Platform Stats ─────────────────────────────────────────────────

    def platform_stats(self) -> dict:
        """Get CredEx platform statistics."""
        return self._call_tool("credex_platform_stats", {})

    # ─── Marketplace ────────────────────────────────────────────────────

    def marketplace_browse(self, category: str = "", query: str = "") -> dict:
        """Browse the agent marketplace."""
        args = {}
        if category:
            args["category"] = category
        if query:
            args["query"] = query
        return self._call_tool("credex_marketplace_browse", args)

    # ─── Wallet ─────────────────────────────────────────────────────────

    def wallet_balance(self) -> dict:
        """Get CREDX wallet balance."""
        return self._call_tool("credex_wallet_balance", {})

    # ─── Convenience ────────────────────────────────────────────────────

    def verify_and_remember(
        self,
        content: str,
        context: str = "",
        domain: str = "general",
    ) -> dict:
        """
        Verify content AND store it in memory in one call.
        This is the most common pattern for the SDK middleware.

        Returns:
            Dict with both verification and memory results.
        """
        result = {"content": content}

        # Verify
        try:
            verification = self.verify(claim=content, context=context, domain=domain)
            result["verification"] = verification
        except CredExError as e:
            result["verification_error"] = str(e)

        # Store in memory
        try:
            memory = self.memory_store(
                content=content,
                context=context,
                category=domain,
                importance=0.7,
            )
            result["memory"] = memory
        except CredExError as e:
            result["memory_error"] = str(e)

        return result

    def close(self):
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
