# CredEx SDK

**The trust layer for AI agents. Consensus verification, persistent memory, and XRPL anchoring — in one `pip install`.**

Every AI agent hallucinates. CredEx fixes that by routing your agent's outputs through 5 independent verifier agents for consensus, storing results in persistent memory that survives restarts, and anchoring proofs to the XRP Ledger.

Works like Sentry for errors or Datadog for observability: install the SDK, and your agent's actions are automatically instrumented. No per-action effort required.

## Quick Start

```bash
pip install credex-sdk
```

```python
import credex

# Zero-friction — no API key needed. Auto-provisions on first use.
credex.init()

# Verify a claim
result = credex.check("The speed of light is 299,792,458 m/s")
print(result["verdict"])      # "TRUE"
print(result["confidence"])   # 1.0
print(result["xrpl_txid"])   # XRPL proof hash

# Store a memory
credex.store("User prefers Python over JavaScript", category="preference")

# Search memory across sessions
results = credex.search("user language preferences")
```

That's it. Three lines to verify, store, and search. No API key management, no infrastructure, no configuration.

### How Zero-Friction Works

When you call `credex.init()` with no arguments, the SDK:

1. Checks for a `CREDEX_API_KEY` environment variable
2. Checks `~/.credex/credentials.json` for a saved key
3. If neither exists, auto-provisions a free-tier key from the server (50 interactions, 14-day trial)
4. Saves the key locally so subsequent runs just work

You can always pass an explicit key: `credex.init(api_key="credex_...")`.

## Integration Options

### Patch OpenAI (Zero-Code Change)

```python
import credex
credex.init()
credex.patch_openai()  # ← One line. Done.

from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is quantum computing?"}]
)
# ✓ Output verified by 5 agents, stored in memory, anchored to XRPL
```

### Patch Anthropic

```python
import credex
credex.init()
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

### LangChain

```python
import credex
from credex.integrations.langchain import CredExHandler

credex.init()
handler = CredExHandler()

# Every LLM call, tool use, and agent action is captured
chain.invoke(input, config={"callbacks": [handler]})
```

### CrewAI

```python
import credex
from credex.integrations.crewai import credex_step_callback, CredExVerifyTool

credex.init()

# Option 1: Auto-verify every agent step
crew = Crew(
    agents=[...],
    tasks=[...],
    step_callback=credex_step_callback,
)

# Option 2: Give agents a verification tool
agent = Agent(
    role="Fact-checker",
    tools=[CredExVerifyTool()],
    ...
)
```

### AutoGen

```python
import credex
from credex.integrations.autogen import credex_message_hook, credex_verify_tool

credex.init()

# Option 1: Auto-verify outgoing messages
agent.register_hook("process_message_before_send", credex_message_hook)

# Option 2: Register as callable tool
from autogen import register_function
register_function(
    credex_verify_tool,
    caller=assistant,
    executor=executor,
    name="credex_verify",
    description="Verify a claim using CredEx consensus",
)
```

### Decorators (Any Framework)

```python
import credex
credex.init()

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

### Direct Client

```python
from credex import CredExClient

with CredExClient() as client:
    # Verify
    result = client.verify(
        claim="The XRPL processes 1,500 TPS with 3-5s finality",
        domain="crypto",
    )
    print(result["verdict"])  # TRUE/FALSE/MIXED

    # Store a memory
    client.memory_store(content="Important finding", importance=0.8)

    # Search memories
    memories = client.memory_search("findings from last session")

    # Get trust score
    score = client.trust_score()

    # Anchor to XRPL
    client.anchor()
```

## Why CredEx?

| Feature | CredEx | LangChain Memory | Mem0 | Zep |
|---------|--------|-----------------|------|-----|
| Multi-agent consensus verification | ✅ 5 independent verifiers | ❌ | ❌ | ❌ |
| Persistent across restarts | ✅ | ❌ (in-memory default) | ✅ | ✅ |
| Immutable proof (blockchain) | ✅ XRPL anchoring | ❌ | ❌ | ❌ |
| Trust scoring | ✅ Compounding reputation | ❌ | ❌ | ❌ |
| Framework agnostic | ✅ OpenAI, Anthropic, LangChain, CrewAI, AutoGen | LangChain only | ✅ | ✅ |
| Zero-friction setup | ✅ No API key needed | ✅ | ❌ | ❌ |

**The key difference:** CredEx doesn't just store what your agent said — it verifies whether it's true. Five independent AI models vote on every output. That consensus, anchored to a public ledger, is proof that can't be faked or dismissed.

## Configuration

```python
credex.init(
    api_key="credex_...",          # Optional — auto-provisions if omitted
    verify_level="milestones",     # "all", "milestones", "sample", "none"
    auto_anchor=True,              # Anchor verified results to XRPL
    auto_memory=True,              # Store results in persistent memory
    sample_rate=0.1,               # For verify_level="sample"
    verbose=False,                 # Print SDK activity to stderr
    agent_name="my-agent",         # Name in CredEx logs
)
```

### Verify Levels

| Level | Behavior | Use Case |
|-------|----------|----------|
| `"all"` | Verify every action | Maximum trust, higher latency |
| `"milestones"` | Verify decorated calls and completions | Balanced (default) |
| `"sample"` | Randomly verify N% of actions | High-volume, cost-sensitive |
| `"none"` | Memory only, no verification | Logging without verification |

## How It Works

```
Your Agent Code
      ↓
CredEx SDK (intercepts LLM calls / actions)
      ↓ JSON-RPC over HTTPS
CredEx Platform
      ├── 5 Verifier Agents (consensus vote: GPT-4.1, Gemini, Claude, Grok, Haiku)
      ├── Persistent Memory (consensus-verified, searchable)
      └── XRPL Anchoring (Merkle root → immutable proof)
      ↓
Original response returned unchanged
```

The SDK never modifies your agent's responses. It observes the output, routes it to CredEx for verification and storage, and returns the original response to your code.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CREDEX_API_KEY` | Your CredEx API key (alternative to passing in code) |
| `CREDEX_URL` | CredEx server URL (default: https://credexai.live) |
| `CREDEX_AGENT_NAME` | Agent name for CredEx logs |

## Optional Dependencies

```bash
pip install credex-sdk[openai]      # OpenAI integration
pip install credex-sdk[anthropic]   # Anthropic integration
pip install credex-sdk[langchain]   # LangChain integration
pip install credex-sdk[crewai]      # CrewAI integration
pip install credex-sdk[all]         # Everything
```

## Get an API Key

You don't need one to start — `credex.init()` auto-provisions a free-tier key.

For full access:
1. Go to [credexai.live](https://credexai.live)
2. Sign up / sign in
3. Navigate to Settings → API Keys
4. Generate a key (starts with `credex_`)

Or register programmatically via the [agent auth protocol](https://credexai.live/.well-known/auth.md).

## Links

- **Platform:** [credexai.live](https://credexai.live)
- **Auth Protocol:** [credexai.live/.well-known/auth.md](https://credexai.live/.well-known/auth.md)
- **GitHub:** [github.com/credexai-labs/credex-sdk-python](https://github.com/credexai-labs/credex-sdk-python)

## License

MIT
