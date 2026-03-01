# LiveKit Multi-Agent Voice (LK-MAV)

Multi-agent voice AI built with [LiveKit Agents](https://github.com/livekit/agents). **Tom** (starter) hands off to **Sarah** (support) or **James** (booking); both can return to Tom or end the call. The `lk-mav` agent uses **explicit dispatch** — it must be dispatched to a room (CLI, API, token, or SIP) and does not auto-join by room name.

## Tutorial

[![LK-MAV Tutorial](https://img.youtube.com/vi/3FnatxfYt_k/maxresdefault.jpg)](https://youtu.be/3FnatxfYt_k)

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [LiveKit CLI](https://docs.livekit.io/home/cli/cli-setup)
- [LiveKit Cloud](https://cloud.livekit.io/) (or self-hosted LiveKit)

---

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env` and set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. For booking/calendar integration via Zapier MCP, optionally set `MCP_SERVER_URL` (e.g. `https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN`). For conversation memory, optionally set `MEM0_API_KEY` (see [Mem0](https://app.mem0.ai)). Optionally:

```bash
lk cloud auth
lk app env -w -d .env
```

One-time agent registration (writes `livekit.toml`):

```bash
lk agent create
```

Download models (Silero VAD, turn detector) before first run:

```bash
uv run python src/agents.py download-files
```

---

## LK-MAV CLI

After `uv sync`, the `lk-mav` command is available for setup, credentials, validation, and run. **Do not modify internal source files**; use the CLI and config only.

| Command | Description |
|---------|-------------|
| `lk-mav init` | Create `lk-mav.config.yaml` and `.env` template in the current directory. Use `--force` to overwrite existing config. |
| `lk-mav setup` | Interactive setup: enable LiveKit, Mem0, Zapier MCP; collect credentials and write them to `.env`; update config. Use `--force` to overwrite existing .env values. |
| `lk-mav validate` | Check config integrity and that enabled integrations have required env vars. Exits non-zero on failure. |
| `lk-mav run` | Load `.env` and config, run validation, then start the agent. Fails if validation fails. Use `--dev` for local LiveKit testing. |
| `lk-mav doctor` | Test connectivity for enabled integrations (LiveKit, Mem0, Zapier MCP). No secrets in output. |

**Workflow**

```bash
lk-mav init
lk-mav setup    # answer prompts; credentials stored in .env
lk-mav validate
lk-mav run      # or lk-mav run --dev
lk-mav doctor   # optional: check integration health
```

All customization happens through the CLI, `lk-mav.config.yaml`, and `.env`. Secrets stay in `.env` only.

---

## Configuration

You can customize agents without changing code by using a **config file**. Secrets stay in `.env`; the config file holds only non-secret options (prompts, voices, which agents are enabled, and toggles for memory and MCP).

1. Copy the example config: `cp config/agents.example.yaml config/agents.yaml` (or set `AGENTS_CONFIG_PATH` in `.env` to your file path).
2. Edit `config/agents.yaml`:
   - **session**: LLM model, STT model, default TTS, `default_timezone`, and flags `mcp_enabled` and `memory_enabled`. When `mcp_enabled` is false, MCP is not attached even if `MCP_SERVER_URL` is set in `.env`. When `memory_enabled` is false, Mem0 is not used even if `MEM0_API_KEY` is set.
   - **agents**: List of agents. One must have `role: starter` and list specialist ids in `handoff_to` (e.g. `[booking, consultant]`). Each agent has `id`, `name`, `role`, `instructions`, `tts` (model + voice), and optionally `memory_enabled` / `mcp_enabled`. Specialists can use `agent_type: booking` (adds time tools and MCP-focused behavior) or `generic`. For booking instructions you can use placeholders `{appointment_topic}`, `{now_utc}`, `{default_timezone}`; for consultant use `{topic}`.
3. Run the agent as usual. If no config file is found, built-in defaults are used (current hardcoded prompts and agents).

---

## CLI Reference

### Agent — `uv run python src/agents.py [command]`

| Command | Description |
|---------|-------------|
| `download-files` | Fetch Silero VAD and turn-detector assets. Run once before `console`, `dev`, or `start`. |
| `console` | Run in-terminal with a mocked room; no LiveKit. |
| `dev` | Connect to LiveKit for local testing (default if no command). |
| `start` | Production worker; connects to LiveKit and processes jobs. |

### Dispatch — `uv run python scripts/dispatch_agent.py`

Dispatches `lk-mav` to a room via the Agent Dispatch API. Requires `LIVEKIT_*` in `.env`.

| Option | Description |
|--------|-------------|
| `-r`, `--room` | Room name (required). Created if missing. |
| `-a`, `--agent-name` | Agent name (default: `lk-mav`). |
| `-m`, `--metadata` | JSON string for `ctx.job.metadata`, e.g. `'{"user_name":"Alice"}'`. |
| `-l`, `--list` | After creating, list dispatches in the room. |
| `--no-create` | Only list dispatches; do not create one. |

**Examples**

```bash
uv run python scripts/dispatch_agent.py -r my-room
uv run python scripts/dispatch_agent.py -r my-room -m '{"user_name":"Alice"}' -l
uv run python scripts/dispatch_agent.py -r my-room --no-create
```

### LiveKit CLI — `lk`

**Cloud & auth**

| Command | Description |
|---------|-------------|
| `lk cloud auth` | Sign in and link LiveKit Cloud. |
| `lk app env -w -d .env` | Write LiveKit env vars to `.env`. |

**Agent (LiveKit Cloud)**

| Command | Description |
|---------|-------------|
| `lk agent create [--region R] [--secrets K=V] [--secrets-file F]` | Register agent, create `livekit.toml`. |
| `lk agent deploy` | Build and deploy. |
| `lk agent status` | Agent status and health. |
| `lk agent logs` | Stream logs. |
| `lk agent update` | Update config without redeploy. |
| `lk agent restart` | Restart instances. |
| `lk agent rollback` | Revert to previous version. |
| `lk agent list` | List agents. |
| `lk agent secrets` | List secrets. |
| `lk agent update-secrets K=V [--secrets-file F]` | Update secrets and restart. |
| `lk agent config` | Generate `livekit.toml`. |
| `lk agent delete` | Remove agent. |

**Dispatch**

| Command | Description |
|---------|-------------|
| `lk dispatch create --agent-name lk-mav --room ROOM [--metadata '{}']` | Dispatch `lk-mav` to a room. |

---

## Dispatch and testing

Because dispatch is explicit, connect only **after** dispatching:

1. **Dispatch**: `lk dispatch create --agent-name lk-mav --room my-room` or `uv run python scripts/dispatch_agent.py -r my-room`
2. **Connect**: [Agents Playground](https://agents-playground.livekit.io/) or your frontend — join the same room.

For token-based dispatch, use `RoomAgentDispatch` with `agent_name="lk-mav"` in `RoomConfiguration`. For SIP, use [SIP dispatch rules](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/).

---

## Deploy

```bash
lk agent deploy
```

Uses the project `Dockerfile`; `download-files` runs at build time, and the container runs `uv run src/agents.py start`.

---

## License

MIT — see [LICENSE](LICENSE).
