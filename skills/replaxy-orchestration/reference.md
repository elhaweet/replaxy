# Replaxy — Reference

## Config Dataclasses (`src/config.py`)

```python
@dataclass
class TTSConfig:
    model: str          # e.g. "cartesia/sonic-3"
    voice: str          # Cartesia voice UUID

@dataclass
class SessionConfig:
    llm_model: str              # e.g. "openai/gpt-4.1-mini"
    stt_model: str              # e.g. "assemblyai/universal-streaming"
    stt_language: str           # e.g. "en"
    default_tts: TTSConfig
    default_timezone: str       # e.g. "UTC"
    mcp_enabled: bool
    memory_enabled: bool

@dataclass
class AgentConfig:
    id: str
    name: str
    role: str           # "starter" | "specialist"
    instructions: str   # may contain {placeholders} for runtime injection
    tts: TTSConfig
    handoff_to: List[str]       # agent IDs (starter only)
    agent_type: str     # "generic" | "booking"
    memory_enabled: bool
    mcp_enabled: bool

@dataclass
class AgentsConfig:
    session: SessionConfig
    agents: List[AgentConfig]
    _by_id: Dict[str, AgentConfig]

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]: ...
    def get_starter(self) -> Optional[AgentConfig]: ...
```

## agents.yaml Schema

```yaml
session:
  llm_model: openai/gpt-4.1-mini
  stt_model: assemblyai/universal-streaming
  stt_language: en
  default_tts:
    model: cartesia/sonic-3
    voice: <uuid>
  default_timezone: UTC
  mcp_enabled: true
  memory_enabled: true

agents:
  - id: starter
    name: Main Assistant
    role: starter           # exactly one required
    instructions: |
      Your system prompt here.
    tts:
      model: cartesia/sonic-3
      voice: <uuid>
    handoff_to:
      - consultant
      - booking

  - id: consultant
    name: Consultant
    role: specialist
    agent_type: generic
    instructions: |
      Your domain prompt. Use {topic} for injection.
    tts:
      model: cartesia/sonic-3
      voice: <uuid>
    memory_enabled: true
    mcp_enabled: false

  - id: booking
    name: Booking Agent
    role: specialist
    agent_type: booking
    instructions: |
      Booking prompt. Use {appointment_topic}, {now_utc}, {default_timezone}.
    tts:
      model: cartesia/sonic-3
      voice: <uuid>
    memory_enabled: true
    mcp_enabled: true
```

### Validation Rules

- Exactly one agent with `role: starter`.
- All `handoff_to` IDs must exist in the agents list.
- Every agent must have a non-empty `id`.

---

## replaxy.config.yaml Schema (CLI-level)

```yaml
project:
  name: replaxy-project
  version: 0.1.0

assistant:
  name: Main Assistant
  tone: professional
  language: en

roles: []

memory:
  enabled: false
  type: null            # "mem0" when enabled

integrations:
  livekit:
    enabled: false
  mem0:
    enabled: false
  zapier_mcp:
    enabled: false

handoff_rules:
  mode: keyword         # "keyword" | "intent" | "priority"
  rules: []
```

### Integration → Required Env Vars

| Integration key | Required env vars |
|-----------------|-------------------|
| `livekit` | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| `mem0` | `MEM0_API_KEY` |
| `zapier_mcp` | `MCP_SERVER_URL` |

---

## OrchestratorAgent Lifecycle Hooks

| Method | When called | What it does |
|--------|-------------|--------------|
| `on_enter()` | Agent becomes active | Restores context, logs entry, calls `generate_reply()` |
| `on_exit(reason)` | Agent hands off or ends | Saves context, logs duration |
| `on_user_turn_completed()` | After each user message | Mem0 add + search + RAG inject |
| `end_conversation()` | `@function_tool` | Goodbye message, room deletion, session cleanup |

---

## Session Context Keys

| Key | Type | Description |
|-----|------|-------------|
| `current_agent` | str | Name of the currently active agent class |
| `previous_agent` | str | Name of the agent that handed off |
| `handoff_count` | int | Total number of handoffs this session |
| `handoff_history` | list | Last N handoff events with timestamps |
| `last_handoff` | dict | Most recent handoff event |
| `handoff_errors` | list | Any handoff failures |
| `agent_entries` | list | All agent entry events |
| `agent_exits` | list | All agent exit events |
| `conversation_history` | list | Turn-by-turn conversation log |
| `mem0_user_id` | str | User identifier for Mem0 queries |

---

## Mem0 API Notes

```python
# Add (write) — always wrap in try/except
await mem0_client.add(
    [{"role": "user", "content": user_text}],
    user_id=mem0_user_id,
)

# Search (read) — v2 API requires filters dict
await mem0_client.search(
    query_text,
    filters={"AND": [{"user_id": mem0_user_id}]},
)

# Doctor check (read-only health check)
await mem0_client.search(
    "health check",
    filters={"AND": [{"user_id": "__doctor__"}]},
)
```

---

## CLI Module Map

| Module | Key exports |
|--------|-------------|
| `src/cli/__init__.py` | `app` (Typer), `init`, `setup`, `validate`, `run`, `doctor` |
| `src/cli/ui.py` | `UI(no_color)` class — all styled output |
| `src/cli/config_loader.py` | `load_config()`, `save_config()`, `config_exists()` |
| `src/cli/env.py` | `read_env()`, `append_env(force=)`, `create_env_template()` |
| `src/cli/validators.py` | `validate_all() -> (bool, list[str])` |

### `--no-color` flag

Available on every subcommand as a direct parameter. Pass it to `_ui(no_color)` — do NOT use the global callback pattern. Both positions work:

```bash
replaxy --no-color doctor     # global (callback)
replaxy doctor --no-color     # per-command parameter
```

---

## Dispatch Script

```bash
# Explicit dispatch (when agent_name is set in agents.py)
uv run python scripts/dispatch_agent.py --room my-room
uv run python scripts/dispatch_agent.py --room my-room --metadata '{"user_name": "Alice"}'
uv run python scripts/dispatch_agent.py --room my-room --list
```

Requires `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` in `.env`.

---

## Common Failure Modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `load_config()` returns None | `config/agents.yaml` missing or malformed | Copy from `config/agents.example.yaml`, fix YAML |
| Mem0 search 400 error | Missing `filters` dict | Use `filters={"AND": [{"user_id": ...}]}` |
| Agent handoff loops | Circular `handoff_to` or missing `call_starter_agent` | Check `handoff_to` lists; ensure specialist calls `call_starter_agent` |
| `--no-color` rejected | Used as subcommand option before the fix | Flag is now on each subcommand — pass after subcommand name |
| `replaxy run` fails validation | Enabled integration missing env var | Run `replaxy setup` or manually fill `.env` |
| Context lost across handoffs | `session.userdata` not set (console mode) | Falls back to `self._session_context` automatically |
