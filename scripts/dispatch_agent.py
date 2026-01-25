"""
Explicitly dispatch the replaxy agent to a room via the AgentDispatchService API.

Use this when the agent is configured with agent_name (explicit dispatch):
the agent will NOT join rooms automatically and must be explicitly dispatched.

Requires LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in .env or the environment.

Usage:
  uv run python scripts/dispatch_agent.py --room my-room
  uv run python scripts/dispatch_agent.py --room my-room --metadata '{"user_name": "Alice"}'
  uv run python scripts/dispatch_agent.py --room my-room --agent-name replaxy --list
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")
load_dotenv(".env.local")

DEFAULT_AGENT_NAME = "replaxy"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly dispatch the agent to a room")
    parser.add_argument("--room", "-r", required=True, help="Room name (created if it does not exist)")
    parser.add_argument(
        "--agent-name",
        "-a",
        default=DEFAULT_AGENT_NAME,
        help=f"Agent name (must match @server.rtc_session(agent_name=...) in agents.py). Default: {DEFAULT_AGENT_NAME}",
    )
    parser.add_argument(
        "--metadata",
        "-m",
        default="",
        help='Optional JSON string passed to the agent as job metadata, e.g. \'{"user_id": "123", "user_name": "Alice"}\'',
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List dispatches for the room after creating (and do not create if only --list is implied)",
    )
    parser.add_argument("--no-create", action="store_true", help="Only list dispatches; do not create one")
    args = parser.parse_args()

    if not all((os.getenv("LIVEKIT_URL"), os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))):
        raise SystemExit(
            "Missing LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET. "
            "Set them in .env or the environment."
        )

    lkapi = api.LiveKitAPI()

    try:
        if not args.no_create:
            req = api.CreateAgentDispatchRequest(
                agent_name=args.agent_name,
                room=args.room,
                metadata=args.metadata or None,
            )
            dispatch = await lkapi.agent_dispatch.create_dispatch(req)
            print("Created dispatch:", dispatch)

        if args.list or args.no_create:
            dispatches = await lkapi.agent_dispatch.list_dispatch(room_name=args.room)
            print(f"Dispatches in room {args.room!r}: {len(dispatches)}")
            for d in dispatches:
                print(" ", d)
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
