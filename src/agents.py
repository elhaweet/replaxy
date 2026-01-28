import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    mcp,
    room_io,
)
from livekit.agents.llm import ToolError, function_tool
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from orchestrator_agent import OrchestratorAgent

logger = logging.getLogger("agent")

# Load environment variables from .env.local (preferred) or .env
load_dotenv(".env")  # Fall back to .env if .env.local doesn't exist

# MCP server URL (e.g. Zapier); must be set in .env for MCP integration
# Format: https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "").strip()

# Agent name for explicit dispatch. When set, automatic dispatch is disabled;
# the agent must be explicitly dispatched via API, CLI, token, or SIP.
AGENT_NAME = "replaxy"


class StarterAgent(OrchestratorAgent):
    def __init__(self, job_metadata: Optional[dict] = None) -> None:
        instructions = """You are a helpful voice AI assistant. The user is interacting with you via voice, even if you perceive the conversation as text.
            Only speak in english. Greet the user by saying my name is Tom.
            If the user wants to book an appointment call the tool call_booking_agent to connect to James the booking agent.
            If the user has a technical issue call the tool call_support_agent to connect to Sarah the support agent.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor."""
        if job_metadata and job_metadata.get("user_name"):
            instructions += f"\nThe user's name is {job_metadata['user_name']}. Use it when appropriate."
        super().__init__(
            instructions=instructions,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice="5ee9feff-1265-424a-9d7f-8e4d431a12c7"
            ),
        )

    @function_tool
    async def call_support_agent(self, topic: str):
        """
        Called when the user has a technical issue

        Args:
            topic: A detailed description of the technical issue the user is experiencing
        """
        # Validate handoff before proceeding
        if not self._validate_handoff("SupportAgent", {"topic": topic}):
            return None, "I'm having trouble transferring you right now. Let me help you with that issue instead."
        
        try:
            # Log exit before handoff
            await self.on_exit(reason="handoff")
            
            # Session will automatically manage chat context for the new agent
            support_agent = SupportAgent(topic=topic)
            
            # Log the handoff
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="SupportAgent",
                reason="technical_issue",
                context_passed={"topic": topic}
            )
            
            return support_agent, f"Transferring you to Sarah, our technical support specialist. She'll help you with: {topic}."
        except Exception as e:
            return self._handle_handoff_error(e, "SupportAgent")

    @function_tool
    async def call_booking_agent(self, appointment_topic: str):
        """
        Called when the user wants to book an appointment

        Args:
            appointment_topic: A detailed description of the appointment type, date, time preferences, and any other relevant details
        """
        # Validate handoff before proceeding
        if not self._validate_handoff("BookingAgent", {"appointment_topic": appointment_topic}):
            return None, "I'm having trouble transferring you right now. Let me help you with that booking instead."
        
        try:
            # Log exit before handoff
            await self.on_exit(reason="handoff")
            
            # Session will automatically manage chat context for the new agent
            booking_agent = BookingAgent(appointment_topic=appointment_topic)
            
            # Log the handoff
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="BookingAgent",
                reason="appointment_booking",
                context_passed={"appointment_topic": appointment_topic}
            )
            
            return booking_agent, f"Transferring you to James, our booking specialist. He'll help you schedule: {appointment_topic}."
        except Exception as e:
            return self._handle_handoff_error(e, "BookingAgent")


class SupportAgent(OrchestratorAgent):
    def __init__(self, topic: str) -> None:
        super().__init__(
            instructions=f"""You are a support voice AI assistant only speak english.
            Greet the user by saying your name is Sarah.
            The user has been transferred to you with the following technical issue: {topic}. Acknowledge this issue naturally when greeting the user and show that you understand their problem.
            When the issue is resolved, ask the user if they want to talk to Tom again. If they do, call the tool call_starter_agent to transfer them back to Tom.
            If not end the conversation with the tool end_conversation.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.""",
            # Sarah's voice - ensure this is a feminine voice ID
            # To find available voices, check the LiveKit TTS documentation or Cartesia's voice list
            tts=inference.TTS(
                model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"  # Verify this is a feminine voice
            ),
        )

    @function_tool
    async def call_starter_agent(self):
        """
        Called when the user wants to talk to Tom again
        """
        # Validate handoff before proceeding
        if not self._validate_handoff("StarterAgent"):
            return None, "I'm having trouble transferring you right now. How else can I help you?"
        
        try:
            # Log exit before handoff
            await self.on_exit(reason="handoff")
            
            # Session will automatically manage chat context for the new agent
            starter_agent = StarterAgent()
            
            # Log the handoff
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="StarterAgent",
                reason="return_to_starter",
                context_passed={}
            )
            
            return starter_agent, "Transferring you back to Tom."
        except Exception as e:
            return self._handle_handoff_error(e, "StarterAgent")


class BookingAgent(OrchestratorAgent):
    def __init__(self, appointment_topic: str) -> None:
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        instructions = f"""You are a booking voice AI assistant only speak english.
            Greet the user by saying your name is James.
            The topic of the booking is {appointment_topic}. Acknowledge this topic naturally when greeting the user.

            Current date and time (UTC): {now_utc}. Use this when the user says "today", "tomorrow", "yesterday", or "next week".

            Your role:
            - Help users check their existing appointments (e.g. list upcoming appointments, see details).
            - Help users book new appointments (e.g. suggest times, confirm booking).

            You have access to MCP tools from the connected server. Use them whenever the user asks to check or book appointments. Call the appropriate tool with the parameters the user provides (name, date, time, reason, etc.), then summarize the result in short, clear speech.

            When the user asks for the time in a city or timezone (e.g. Cairo, New York), or to book in another timezone, use the get_current_time and convert_time tools and state the timezone clearly.

            When the booking was successful, ask the user if they want to talk to Tom again. If they do, call the tool call_starter_agent to transfer them back to Tom.
            If not end the conversation with the tool end_conversation.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            Keep responses brief and natural for voice: one or two sentences when possible. Confirm what you did (e.g. "I've booked you for Tuesday at 3 PM") and ask if they need anything else."""
        super().__init__(
            instructions=instructions,
            # James's voice - ensure this is a masculine voice ID
            # To find available voices, check the LiveKit TTS documentation or Cartesia's voice list
            tts=inference.TTS(
                model="cartesia/sonic-3", voice="79f8b5fb-2cc8-479a-80df-29f7a7cf1a3e"  # Verify this is a masculine voice
            ),
        )

    @function_tool
    async def get_current_time(self, timezone_name: str) -> str:
        """
        Get the current date and time in a specific timezone. Use IANA timezone names (e.g. America/New_York, Africa/Cairo, Europe/London).

        Args:
            timezone_name: IANA timezone name (e.g. America/New_York, Africa/Cairo)
        """
        try:
            tz = ZoneInfo(timezone_name)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            raise ToolError(f"Invalid timezone or error: {e}") from e

    @function_tool
    async def convert_time(
        self,
        source_timezone: str,
        time_str: str,
        target_timezone: str,
    ) -> str:
        """
        Convert a time from one timezone to another. Use IANA timezone names. Time can be HH:MM or YYYY-MM-DD HH:MM; if only time is given, today's date in the source timezone is used.

        Args:
            source_timezone: IANA timezone name for the source (e.g. America/New_York)
            time_str: Time to convert (e.g. 14:30 or 2026-01-25 14:30)
            target_timezone: IANA timezone name for the target (e.g. Africa/Cairo)
        """
        try:
            src_tz = ZoneInfo(source_timezone)
            tgt_tz = ZoneInfo(target_timezone)
            time_str = time_str.strip()
            if " " in time_str:
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=src_tz)
            else:
                today = datetime.now(src_tz).date()
                t = datetime.strptime(time_str, "%H:%M").time()
                dt = datetime.combine(today, t, tzinfo=src_tz)
            result = dt.astimezone(tgt_tz)
            return result.strftime("%Y-%m-%d %H:%M %Z")
        except ValueError as e:
            raise ToolError(f"Could not parse time (use HH:MM or YYYY-MM-DD HH:MM): {e}") from e
        except Exception as e:
            raise ToolError(f"Invalid timezone or error: {e}") from e

    @function_tool
    async def call_starter_agent(self):
        """
        Called when the user wants to talk to Tom again
        """
        # Validate handoff before proceeding
        if not self._validate_handoff("StarterAgent"):
            return None, "I'm having trouble transferring you right now. How else can I help you?"
        
        try:
            # Log exit before handoff
            await self.on_exit(reason="handoff")
            
            # Session will automatically manage chat context for the new agent
            starter_agent = StarterAgent()
            
            # Log the handoff
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="StarterAgent",
                reason="return_to_starter",
                context_passed={}
            )
            
            return starter_agent, "Transferring you back to Tom."
        except Exception as e:
            return self._handle_handoff_error(e, "StarterAgent")


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def my_agent(ctx: JobContext):
    # Parse job metadata from explicit dispatch (JSON string)
    job_metadata: dict = {}
    raw = getattr(getattr(ctx, "job", None), "metadata", None) or ""
    if raw and isinstance(raw, str) and raw.strip():
        try:
            job_metadata = json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
        **({"job_metadata": job_metadata} if job_metadata else {}),
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session_kwargs = {
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        "stt": inference.STT(model="assemblyai/universal-streaming", language="en"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        "llm": inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        "tts": inference.TTS(
            model="cartesia/sonic-3", voice="87286a8d-7ea7-4235-a41a-dd9fa6630feb"
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        "turn_detection": MultilingualModel(),
        "vad": ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        "preemptive_generation": True,
    }
    
    # Add MCP servers if MCP_SERVER_URL is configured
    # Zapier MCP uses streamable HTTP; auto-detect would default to SSE and fail.
    if MCP_SERVER_URL:
        session_kwargs["mcp_servers"] = [
            mcp.MCPServerHTTP(
                url=MCP_SERVER_URL,
                transport_type="streamable_http",
                client_session_timeout_seconds=60,
            ),
        ]
        logger.info("MCP integration enabled (Zapier)")
    else:
        logger.info("MCP integration disabled (MCP_SERVER_URL not set)")
    
    session = AgentSession(**session_kwargs)

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=StarterAgent(job_metadata=job_metadata or None),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    import sys

    # Default to "dev" when no command is given (e.g. `python src/agents.py`)
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    cli.run_app(server)
