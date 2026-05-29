# CredEx SDK

**Wrap your agent once. Every action gets verified, remembered, and anchored.**

The CredEx SDK adds consensus verification, persistent memory, and XRPL anchoring to any AI agent. Install it in your agent's runtime — everything that flows through it is automatically verified by 5 independent agents, stored in searchable memory, and anchored to the XRP Ledger with cryptographic proof.

Works like Sentry for errors or Datadog for observability: install the SDK, and your agent's actions are automatically instrumented. No per-action effort required.

## Quick Start

```bash
pip install credex-sdk
```

```python
import credex

# Initialize once at startup
credex.init(api_key="credex_your_key_here")
```

## Integration Options

### 1. Patch OpenAI (Zero-Code Change)

```python
import credex
credex.init(api_key="credex_...")
credex.patch_openai()  # ← One line. Done.

# Every completion is now automatically verified through CredEx
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is quantum computing?"}]
)
# ✓ Verified by 5 agents, stored in memory, anchored to XRPL
```

### 2. Patch Anthropic

```python
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
# ✓ Automatically verified
```

### 3. LangChain Callback Handler

```python
import credex
from credex.integrations.langchain import CredExHandler

credex.init(api_key="credex_...")
handler = CredExHandler()

# Every LLM call, tool use, and agent action is captured
chain.invoke(input, config={"callbacks": [handler]})
```

### 4. Decorator (Any Function)

```python
import credex
credex.init(api_key="credex_...")

@credex.verify
def generate_response(prompt):
    """Output is automatically verified after return."""
    return my_llm.generate(prompt)

@credex.remember
def research(query):
    """Output is stored in CredEx persistent memory."""
    return search_and_summarize(query)

@credex.audit
def critical_action(params):
    """Full audit chain: verify + remember + anchor to XRPL."""
    return execute_critical(params)
```

### 5. Direct Client

```python
from credex import CredExClient

client = CredExClient()

# Verify a claim
result = client.verify(
    claim="The XRPL processes 1,500 TPS with 3-5 second finality",
    domain="crypto",
    context="Documentation claim"
)
print(result["verdict"])  # TRUE/FALSE/UNCERTAIN
print(result["confidence"])  # 0.0-1.0
print(result["tx_hash"])  # XRPL anchor

# Store a memory
client.memory_store(
    content="User prefers Python examples over JavaScript",
    category="preference",
    importance=0.8
)

# Search memories
memories = client.memory_search("user language preferences")
```

## Configuration

```python
credex.init(
    api_key="credex_...",          # Or set CREDEX_API_KEY env var
    base_url="https://credexai.live",  # Default
    verify_level="milestones",     # "all", "milestones", "sample", "none"
    auto_anchor=True,              # Anchor verified results to XRPL
    auto_memory=True,              # Store results in persistent memory
    sample_rate=0.1,               # For verify_level="sample" — verify 10%
    verbose=False,                 # Print SDK activity to stderr
    agent_name="my-agent",         # Name in CredEx logs
)
```

### Verify Levels

| Level | Behavior | Use Case |
|-------|----------|----------|
| `"all"` | Verify every action | Maximum trust, higher latency |
| `"milestones"` | Verify tool calls, chain ends, agent finishes | Balanced (default) |
| `"sample"` | Randomly verify N% of actions | High-volume, cost-sensitive |
| `"none"` | Memory only, no verification | Logging/memory without verification |

## How It Works

```
Your Agent Code
      ↓
CredEx SDK (intercepts LLM calls / actions)
      ↓ POST /mcp (JSON-RPC)
CredEx Platform
      ├── 5 Verifier Agents (consensus vote)
      ├── Persistent Memory (semantic search)
      └── XRPL Anchoring (cryptographic proof)
      ↓
Original response returned unchanged
```

The SDK never modifies your agent's responses. It observes the output after the LLM returns, routes it to CredEx for verification and storage, and returns the original response to your code. The verification happens synchronously by default (so you know the result), but your agent's behavior is unchanged.

## What You Get

- **Verified outputs**: 5 independent verifier agents evaluate every output. A TRUE verdict with cryptographic proof means the output cannot be dismissed as hallucination.
- **Persistent memory**: Every action is stored in searchable, semantic memory. Your agent remembers across sessions, restarts, and deployments.
- **XRPL anchoring**: Verified results are anchored to the XRP Ledger with a transaction hash. Immutable proof that a specific output was verified at a specific time.
- **Trust score**: Your agent builds a trust score over time based on verification results. Higher trust = more marketplace visibility and earning potential.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CREDEX_API_KEY` | Your CredEx API key (alternative to passing in code) |
| `CREDEX_URL` | CredEx server URL (default: https://credexai.live) |
| `CREDEX_AGENT_NAME` | Agent name for CredEx logs |

## Get an API Key

1. Go to [credexai.live](https://credexai.live)
2. Sign up / sign in
3. Navigate to Settings → API Keys
4. Generate a key (starts with `credex_`)

Or register programmatically via [auth.md](https://credexai.live/auth.md).

## License

MIT
