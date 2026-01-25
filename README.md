<a href="https://livekit.io/">
  <img src="./.github/assets/livekit-mark.png" alt="LiveKit logo" width="100" height="100">
</a>

# LiveKit Agents Starter - Python

A complete starter project for building voice AI apps with [LiveKit Agents for Python](https://github.com/livekit/agents) and [LiveKit Cloud](https://cloud.livekit.io/).

The starter project includes:

- **Explicit agent dispatch** with a named agent (`replaxy`); dispatch via API, CLI, token, or SIP (no automatic room-name-based dispatch)
- A simple voice AI assistant, ready for extension and customization
- A voice AI pipeline with [models](https://docs.livekit.io/agents/models) from OpenAI, Cartesia, and AssemblyAI served through LiveKit Cloud
  - Easily integrate your preferred [LLM](https://docs.livekit.io/agents/models/llm/), [STT](https://docs.livekit.io/agents/models/stt/), and [TTS](https://docs.livekit.io/agents/models/tts/) instead, or swap to a realtime model like the [OpenAI Realtime API](https://docs.livekit.io/agents/models/realtime/openai)
- Eval suite based on the LiveKit Agents [testing & evaluation framework](https://docs.livekit.io/agents/build/testing/)
- [LiveKit Turn Detector](https://docs.livekit.io/agents/build/turns/turn-detector/) for contextually-aware speaker detection, with multilingual support
- [Background voice cancellation](https://docs.livekit.io/home/cloud/noise-cancellation/)
- Integrated [metrics and logging](https://docs.livekit.io/agents/build/metrics/)
- A Dockerfile ready for [production deployment](https://docs.livekit.io/agents/ops/deployment/)

This starter app is compatible with any [custom web/mobile frontend](https://docs.livekit.io/agents/start/frontend/) or [SIP-based telephony](https://docs.livekit.io/agents/start/telephony/).

## Coding agents and MCP

This project is designed to work with coding agents like [Cursor](https://www.cursor.com/) and [Claude Code](https://www.anthropic.com/claude-code). 

To get the most out of these tools, install the [LiveKit Docs MCP server](https://docs.livekit.io/mcp).

For Cursor, use this link:

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-light.svg)](https://cursor.com/en-US/install-mcp?name=livekit-docs&config=eyJ1cmwiOiJodHRwczovL2RvY3MubGl2ZWtpdC5pby9tY3AifQ%3D%3D)

For Claude Code, run this command:

```
claude mcp add --transport http livekit-docs https://docs.livekit.io/mcp
```

For Codex CLI, use this command to install the server:
```
codex mcp add --url https://docs.livekit.io/mcp livekit-docs
```

For Gemini CLI, use this command to install the server:
```
gemini mcp add --transport http livekit-docs https://docs.livekit.io/mcp
```

The project includes a complete [AGENTS.md](AGENTS.md) file for these assistants. You can modify this file for your needs. To learn more about this file, see [https://agents.md](https://agents.md).

## Installation

This repo does not include `livekit.toml`; create it with `lk agent create`. Follow these steps to install, authorize, create an agent, and deploy.

1. **LiveKit CLI** — [Install the LiveKit CLI](https://docs.livekit.io/home/cli/cli-setup).
2. **uv** — [Install uv](https://docs.astral.sh/uv/).
3. **Dependencies** — Clone the repo, then run `uv sync` (uses `uv.lock`).
4. **Authorize** — Sign in to LiveKit Cloud:
   ```bash
   lk cloud auth
   ```
5. **Create agent** (one-time) — Creates a new agent and writes `livekit.toml`:
   ```bash
   lk agent create [--region REGION] [--secrets KEY=VALUE] [--secrets-file FILE]
   ```
6. **Deploy** — Build and deploy:
   ```bash
   lk agent deploy
   ```

### lk agent commands

- `lk agent create [--region REGION] [--secrets KEY=VALUE] [--secrets-file FILE]`  
  → Creates a new agent in LiveKit Cloud (one-time setup).
- `lk agent deploy`  
  → Builds the Docker image and deploys a new version with zero downtime.
- `lk agent status`  
  → Shows current agent status, deployment state, and health.
- `lk agent logs`  
  → Streams real-time logs from agent instances.
- `lk agent update`  
  → Updates agent configuration without redeploying code.
- `lk agent restart`  
  → Restarts all running agent instances immediately.
- `lk agent rollback`  
  → Reverts the agent to the previous deployed version (paid plans).
- `lk agent list`  
  → Lists all agents in the project with their statuses.
- `lk agent secrets`  
  → Lists all secrets configured for the agent.
- `lk agent update-secrets KEY=VALUE [--secrets-file FILE]`  
  → Updates secrets and triggers a rolling restart.
- `lk agent config`  
  → Generates a `livekit.toml` configuration file.
- `lk agent delete`  
  → Permanently deletes the agent and its resources.

## Dev Setup

Clone the repository and install dependencies to a virtual environment:

```console
cd agent-starter-python
uv sync
```

Sign up for [LiveKit Cloud](https://cloud.livekit.io/) then set up the environment by copying `.env.example` to `.env.local` and filling in the required keys:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

You can load the LiveKit environment automatically using the [LiveKit CLI](https://docs.livekit.io/home/cli/cli-setup):

```bash
lk cloud auth
lk app env -w -d .env.local
```

## Run the agent

Before your first run, you must download certain models such as [Silero VAD](https://docs.livekit.io/agents/build/turns/vad/) and the [LiveKit turn detector](https://docs.livekit.io/agents/build/turns/turn-detector/):

```console
uv run python src/agents.py download-files
```

Next, run this command to speak to your agent directly in your terminal:

```console
uv run python src/agents.py console
```

To run the agent for use with a frontend or telephony, use the `dev` command:

```console
uv run python src/agents.py dev
```

In production, use the `start` command:

```console
uv run python src/agents.py start
```

## Frontend & Telephony

Get started quickly with our pre-built frontend starter apps, or add telephony support:

| Platform | Link | Description |
|----------|----------|-------------|
| **Web** | [`livekit-examples/agent-starter-react`](https://github.com/livekit-examples/agent-starter-react) | Web voice AI assistant with React & Next.js |
| **iOS/macOS** | [`livekit-examples/agent-starter-swift`](https://github.com/livekit-examples/agent-starter-swift) | Native iOS, macOS, and visionOS voice AI assistant |
| **Flutter** | [`livekit-examples/agent-starter-flutter`](https://github.com/livekit-examples/agent-starter-flutter) | Cross-platform voice AI assistant app |
| **React Native** | [`livekit-examples/voice-assistant-react-native`](https://github.com/livekit-examples/voice-assistant-react-native) | Native mobile app with React Native & Expo |
| **Android** | [`livekit-examples/agent-starter-android`](https://github.com/livekit-examples/agent-starter-android) | Native Android app with Kotlin & Jetpack Compose |
| **Web Embed** | [`livekit-examples/agent-starter-embed`](https://github.com/livekit-examples/agent-starter-embed) | Voice AI widget for any website |
| **Telephony** | [📚 Documentation](https://docs.livekit.io/agents/start/telephony/) | Add inbound or outbound calling to your agent |

For advanced customization, see the [complete frontend guide](https://docs.livekit.io/agents/start/frontend/).

## Tests and evals

This project includes a complete suite of evals, based on the LiveKit Agents [testing & evaluation framework](https://docs.livekit.io/agents/build/testing/). To run them, use `pytest`.

```console
uv run pytest
```

## Using this template repo for your own project

Once you've started your own project based on this repo, you should:

1. **Check in your `uv.lock`**: This file is currently untracked for the template, but you should commit it to your repository for reproducible builds and proper configuration management. (The same applies to `livekit.toml`, if you run your agents in LiveKit Cloud)

2. **Remove the git tracking test**: Delete the "Check files not tracked in git" step from `.github/workflows/tests.yml` since you'll now want this file to be tracked. These are just there for development purposes in the template repo itself.

3. **Add your own repository secrets**: You must [add secrets](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-what-your-workflow-does/using-secrets-in-github-actions) for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` so that the tests can run in CI.

## Deploying to production

This project is production-ready and includes a working `Dockerfile`. To deploy it to LiveKit Cloud or another environment, see the [deploying to production](https://docs.livekit.io/agents/ops/deployment/) guide.

Deploy with the LiveKit CLI:

```bash
lk agent deploy
```

## Explicit agent dispatch

This agent uses **explicit dispatch**: `agent_name` is set to `replaxy` in `@server.rtc_session(agent_name=AGENT_NAME)`. Automatic dispatch is **disabled**; the agent will **not** join rooms by room-name rules or prefixes. You must explicitly dispatch it using one of the methods below.

### 1. LiveKit CLI

```bash
lk dispatch create --agent-name replaxy --room my-room
lk dispatch create --agent-name replaxy --room my-room --metadata '{"user_name": "Alice"}'
```

The room is created if it does not exist.

### 2. Dispatch via API (Python)

Use the helper script (uses `LIVEKIT_*` from `.env`):

```bash
uv run python scripts/dispatch_agent.py --room my-room
uv run python scripts/dispatch_agent.py --room my-room --metadata '{"user_name": "Alice"}'
uv run python scripts/dispatch_agent.py --room my-room --list
```

Or call the AgentDispatchService in your own code:

```python
from livekit import api

lkapi = api.LiveKitAPI()
await lkapi.agent_dispatch.create_dispatch(
    api.CreateAgentDispatchRequest(
        agent_name="replaxy",
        room="my-room",
        metadata='{"user_id": "12345", "user_name": "Alice"}',
    )
)
await lkapi.aclose()
```

Job metadata is available in the agent as `ctx.job.metadata` (JSON string). This project parses it and passes `job_metadata` into the starter agent (e.g. `user_name` is used in instructions when provided).

### 3. Dispatch on participant connection (token)

Include `RoomAgentDispatch` in the participant’s token so the agent is dispatched when they join:

```python
from livekit.api import AccessToken, RoomAgentDispatch, RoomConfiguration, VideoGrants

token = (
    AccessToken()
    .with_identity("my_participant")
    .with_grants(VideoGrants(room_join=True, room="my-room"))
    .with_room_config(
        RoomConfiguration(
            agents=[RoomAgentDispatch(agent_name="replaxy", metadata='{"user_name": "Alice"}')],
        ),
    )
    .to_jwt()
)
```

### 4. SIP inbound calls

For telephony, use [SIP dispatch rules](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/) and set `room_config.agents` to explicitly dispatch `replaxy` into the call’s room.

---

## Test your deployed agent

Because dispatch is **explicit**, the agent will **not** join based on room name alone. First dispatch it (CLI, API, token, or SIP), then connect to the same room.

### 1. Agents Playground

1. **Dispatch** the agent (e.g. `lk dispatch create --agent-name replaxy --room my-room`).
2. Open [Agents Playground](https://agents-playground.livekit.io/), connect to LiveKit Cloud, and join the same room (`my-room`). The agent will be in the room.

### 2. Frontend starter (e.g. React)

1. **Dispatch** the agent to a room (API or token with `RoomAgentDispatch` as above).
2. In your app, create a token that allows joining that room and connect. The agent will be present.

## Self-hosted LiveKit

You can also self-host LiveKit instead of using LiveKit Cloud. See the [self-hosting](https://docs.livekit.io/home/self-hosting/) guide for more information. If you choose to self-host, you'll need to also use [model plugins](https://docs.livekit.io/agents/models/#plugins) instead of LiveKit Inference and will need to remove the [LiveKit Cloud noise cancellation](https://docs.livekit.io/home/cloud/noise-cancellation/) plugin.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
