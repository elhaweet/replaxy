---
name: lk-mav-orchestration
description: Guides development on the LiveKit Multi-Agent Voice (LK-MAV) project — a CLI-first, config-driven multi-agent orchestration system built on LiveKit Agents. Use when working on agent routing logic, handoff rules, session context, Mem0 memory integration, CLI commands, YAML configuration, or any code inside src/agents.py, src/orchestrator_agent.py, src/config.py, or src/cli/. Also use when adding new agents, modifying delegation logic, or debugging integration behavior.
---

# LK-MAV Orchestration Skill

LiveKit Multi-Agent Voice (LK-MAV) is a **structured multi-agent execution environment** — not a free-form autonomous framework. All behavior is defined by configuration and enforced through predictable routing logic.

## Architecture at a Glance

```
User → StarterAgent (orchestrator) → ConsultantAgent | BookingAgent
                ↑___________________________________|
```

- **StarterAgent** — entry point, router, and orchestrator. Regains control after every specialist call.
- **ConsultantAgent** — handles product/service knowledge queries.
- **BookingAgent** — handles scheduling, appointments, timezone handling.
- **OrchestratorAgent** — base class for all agents; provides Mem0 wiring, session context, handoff validation, and lifecycle hooks.

## Key Files

| File | Purpose |
|------|---------|
| `src/agents.py` | Agent class definitions + `my_agent()` session entrypoint |
| `src/orchestrator_agent.py` | Base class with Mem0, context, handoff, lifecycle |
| `src/config.py` | Loads and validates `config/agents.yaml` into typed dataclasses |
| `src/memory.py` | Initializes `mem0ai.AsyncMemoryClient` from `MEM0_API_KEY` |
| `src/cli/__init__.py` | Typer CLI: `init`, `setup`, `validate`, `run`, `doctor` |
| `src/cli/ui.py` | Branded terminal output (Rich-based) |
| `src/cli/validators.py` | Config + env var integrity checks |
| `src/cli/config_loader.py` | Load/save `lk-mav.config.yaml` |
| `src/cli/env.py` | Read/write `.env` safely |
| `config/agents.yaml` | Runtime agent definitions (prompts, TTS, handoff targets) |
| `lk-mav.config.yaml` | CLI-level project config (integration toggles, no secrets) |
| `scripts/dispatch_agent.py` | Explicit LiveKit room dispatch via AgentDispatchService |

## Delegation Rules (Never Bypass)

1. **StarterAgent decides** which specialist to call based on `handoff_to` in `config/agents.yaml`.
2. Specialists complete their domain task and return control to StarterAgent via `call_starter_agent()`.
3. No agent may delegate to an agent not listed in its `handoff_to` config.
4. No new agent types may be created dynamically at runtime.
5. Circular handoff detection is logged (last 5 handoffs tracked in session context).

## Configuration Chain

```
lk-mav.config.yaml     → CLI-level toggles (memory.enabled, integrations.*.enabled)
config/agents.yaml      → Runtime agent behavior (instructions, TTS voice, handoff targets)
.env                    → All secrets (never in YAML)
```

`load_config()` in `src/config.py` reads `config/agents.yaml` (or `AGENTS_CONFIG_PATH` env var). Returns `None` on missing/invalid file — callers fall back to hardcoded defaults. Never throw; always degrade gracefully.

## Memory Integration (Mem0)

- Controlled by `session.memory_enabled` in `config/agents.yaml` AND `memory.enabled` in `lk-mav.config.yaml`.
- `OrchestratorAgent.on_user_turn_completed()` handles: add message → search memories → inject RAG context.
- Mem0 v2 search requires `filters={"AND": [{"user_id": "..."}]}` — not bare `user_id`.
- All Mem0 calls are wrapped in try/except; failures are logged as warnings, never crash the agent.

## Session Context (Persists Across Handoffs)

Stored in `session.userdata.orchestration_context` (falls back to `self._session_context` in console mode).

Key fields: `current_agent`, `previous_agent`, `handoff_count`, `handoff_history`, `mem0_user_id`, `conversation_history`.

Use `_get_session_context()`, `_update_session_context()` — never access `session.userdata` directly.

## CLI Commands

```bash
uv run lk-mav init          # create lk-mav.config.yaml + .env template
uv run lk-mav setup         # interactive credential collection
uv run lk-mav validate      # check config + env completeness
uv run lk-mav run [--dev]   # validate then launch src/agents.py
uv run lk-mav doctor        # live connectivity tests
```

`--no-color` works on every subcommand (CI-safe).

## Adding a New Specialist Agent

1. Add the agent class extending `OrchestratorAgent` in `src/agents.py`.
2. Add a `call_<new_agent>` function tool on `StarterAgent`.
3. Add the new agent's entry to `config/agents.yaml` with a unique `id` and `role: specialist`.
4. Add that `id` to the starter agent's `handoff_to` list in the YAML.
5. Implement `call_starter_agent()` on the new specialist to return control.

Do NOT modify routing logic or add agents outside this pattern.

## What Must Never Change

- Agents must not create or invoke other agents not declared in config.
- Secrets must never be written to YAML files.
- `lk-mav run` must always validate before launching — no silent starts.
- `OrchestratorAgent` base class must remain the single source for Mem0, context, and handoff logic.

## Additional Resources

- For dataclass schemas and validation rules, see [reference.md](reference.md)
