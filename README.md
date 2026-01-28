# Replaxy

Multi-agent voice AI built with [LiveKit Agents](https://github.com/livekit/agents). **Tom** (starter) hands off to **Sarah** (support) or **James** (booking); both can return to Tom or end the call. The `replaxy` agent uses **explicit dispatch** — it must be dispatched to a room (CLI, API, token, or SIP) and does not auto-join by room name.

## Tutorial

[![Replaxy Tutorial](https://img.youtube.com/vi/3FnatxfYt_k/maxresdefault.jpg)](https://youtu.be/3FnatxfYt_k)

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

Copy `.env.example` to `.env` and set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. For booking/calendar integration via Zapier MCP, optionally set `MCP_SERVER_URL` (e.g. `https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN`). Optionally:

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

## CLI Reference

### Agent — `uv run python src/agents.py [command]`

| Command | Description |
|---------|-------------|
| `download-files` | Fetch Silero VAD and turn-detector assets. Run once before `console`, `dev`, or `start`. |
| `console` | Run in-terminal with a mocked room; no LiveKit. |
| `dev` | Connect to LiveKit for local testing (default if no command). |
| `start` | Production worker; connects to LiveKit and processes jobs. |

### Dispatch — `uv run python scripts/dispatch_agent.py`

Dispatches `replaxy` to a room via the Agent Dispatch API. Requires `LIVEKIT_*` in `.env`.

| Option | Description |
|--------|-------------|
| `-r`, `--room` | Room name (required). Created if missing. |
| `-a`, `--agent-name` | Agent name (default: `replaxy`). |
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
| `lk dispatch create --agent-name replaxy --room ROOM [--metadata '{}']` | Dispatch `replaxy` to a room. |

---

## Dispatch and testing

Because dispatch is explicit, connect only **after** dispatching:

1. **Dispatch**: `lk dispatch create --agent-name replaxy --room my-room` or `uv run python scripts/dispatch_agent.py -r my-room`
2. **Connect**: [Agents Playground](https://agents-playground.livekit.io/) or your frontend — join the same room.

For token-based dispatch, use `RoomAgentDispatch` with `agent_name="replaxy"` in `RoomConfiguration`. For SIP, use [SIP dispatch rules](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/).

---

## Deploy

```bash
lk agent deploy
```

Uses the project `Dockerfile`; `download-files` runs at build time, and the container runs `uv run src/agents.py start`.

---

## License

MIT — see [LICENSE](LICENSE).
