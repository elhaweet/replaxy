import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env before any module that reads MEM0_API_KEY (e.g. memory, orchestrator_agent)
load_dotenv(".env")

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

from config import load_config
from config import AgentsConfig
from orchestrator_agent import OrchestratorAgent

logger = logging.getLogger("agent")

# MCP server URL (e.g. Zapier); must be set in .env for MCP integration
# Format: https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "").strip()

# Default timezone for bookings when user does not specify. Defaults to UTC; set BOOKING_DEFAULT_TIMEZONE in .env to override.
BOOKING_DEFAULT_TIMEZONE = (os.environ.get("BOOKING_DEFAULT_TIMEZONE") or "UTC").strip()

# Agent name for explicit dispatch. When set, automatic dispatch is disabled;
# the agent must be explicitly dispatched via API, CLI, token, or SIP.
AGENT_NAME = "lk-mav"


class StarterAgent(OrchestratorAgent):
    def __init__(
        self,
        config: Optional[AgentsConfig] = None,
        job_metadata: Optional[dict] = None,
        mem0_user_id: Optional[str] = None,
        memory_enabled: bool = True,
    ) -> None:
        self._config = config
        self._mem0_user_id = mem0_user_id
        if config:
            starter = config.get_starter()
            if not starter:
                raise ValueError("Config has no starter agent")
            instructions = starter.instructions.strip()
            tts = inference.TTS(model=starter.tts.model, voice=starter.tts.voice)
        else:
            instructions = """You are the general manager's voice assistant. You support the GM with scheduling, consultant engagements, and other executive tasks. Only speak in English. Greet the user by introducing yourself as their assistant (e.g. "I'm your assistant").
            When the GM wants to book an event or meeting, call the tool call_booking_agent and say only the transfer message that the tool returns.
            When the GM needs to schedule consultant meetings or has questions about consultant engagements, call the tool call_consultant_agent and say only the transfer message that the tool returns.
            When you call call_booking_agent or call_consultant_agent, say only the transfer message. Do not add follow-up questions because you are leaving the conversation.
            Your responses are concise, professional, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You can use remembered context from past turns to personalize replies."""
            tts = inference.TTS(
                model="cartesia/sonic-3", voice="5ee9feff-1265-424a-9d7f-8e4d431a12c7"
            )
        if job_metadata and job_metadata.get("user_name"):
            instructions += f"\nThe user's name is {job_metadata['user_name']}. Use it when appropriate."
        super().__init__(
            instructions=instructions,
            tts=tts,
            memory_enabled=memory_enabled,
        )

    async def on_enter(self):
        if self._mem0_user_id is not None:
            self._update_session_context({"mem0_user_id": self._mem0_user_id})
        await super().on_enter()

    def _handoff_to(self) -> list:
        """Return list of specialist agent ids the starter can hand off to."""
        if self._config:
            starter = self._config.get_starter()
            return list(starter.handoff_to) if starter else []
        return ["booking", "consultant"]

    @function_tool
    async def call_consultant_agent(self, topic: str):
        """
        Called when the GM needs to schedule consultant meetings or has questions about consultant engagements.

        Args:
            topic: A description of the consultant-related request (e.g. scheduling a consultant meeting, questions about an engagement)
        """
        if self._config and "consultant" not in self._handoff_to():
            return None, "I'm having trouble transferring you right now. Let me help you with that instead."
        consultant_cfg = self._config.get_agent("consultant") if self._config else None
        memory_enabled = self._config.session.memory_enabled if self._config else True
        if not self._validate_handoff("ConsultantAgent", {"topic": topic}):
            return None, "I'm having trouble transferring you right now. Let me help you with that instead."
        try:
            await self.on_exit(reason="handoff")
            consultant_agent = ConsultantAgent(
                topic=topic,
                config=self._config,
                agent_config=consultant_cfg,
                memory_enabled=memory_enabled,
            )
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="ConsultantAgent",
                reason="consultant_request",
                context_passed={"topic": topic},
            )
            return consultant_agent, f"Transferring you to your consultant liaison. They'll help you with: {topic}."
        except Exception as e:
            return self._handle_handoff_error(e, "ConsultantAgent")

    @function_tool
    async def call_booking_agent(self, appointment_topic: str):
        """
        Called when the user wants to book an appointment

        Args:
            appointment_topic: A detailed description of the appointment type, date, time preferences, and any other relevant details
        """
        if self._config and "booking" not in self._handoff_to():
            return None, "I'm having trouble transferring you right now. Let me help you with that booking instead."
        booking_cfg = self._config.get_agent("booking") if self._config else None
        memory_enabled = self._config.session.memory_enabled if self._config else True
        default_tz = self._config.session.default_timezone if self._config else BOOKING_DEFAULT_TIMEZONE
        if not self._validate_handoff("BookingAgent", {"appointment_topic": appointment_topic}):
            return None, "I'm having trouble transferring you right now. Let me help you with that booking instead."
        try:
            await self.on_exit(reason="handoff")
            booking_agent = BookingAgent(
                appointment_topic=appointment_topic,
                config=self._config,
                agent_config=booking_cfg,
                default_timezone=default_tz,
                memory_enabled=memory_enabled,
            )
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="BookingAgent",
                reason="appointment_booking",
                context_passed={"appointment_topic": appointment_topic},
            )
            return booking_agent, f"Transferring you to your scheduling assistant. They'll help you with: {appointment_topic}."
        except Exception as e:
            return self._handle_handoff_error(e, "BookingAgent")


class ConsultantAgent(OrchestratorAgent):
    def __init__(
        self,
        topic: str,
        config: Optional[AgentsConfig] = None,
        agent_config: Optional[Any] = None,
        memory_enabled: bool = True,
    ) -> None:
        if agent_config:
            instructions = agent_config.instructions.strip().format(topic=topic)
            tts = inference.TTS(model=agent_config.tts.model, voice=agent_config.tts.voice)
        else:
            instructions = f"""You are the GM's consultant liaison. You help schedule consultant meetings and answer questions about consultant engagements. Only speak in English. Greet the user and state your role.
            The user was transferred to you with the following request: {topic}. Acknowledge it naturally and help them (schedule a consultant meeting or answer engagement questions).
            When done, ask if they want to return to their main assistant. If yes, call the tool call_starter_agent to transfer them back. If not, end the conversation with the tool end_conversation.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You can use remembered context from past turns to personalize replies."""
            tts = inference.TTS(
                model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
            )
        self._config = config  # None when using built-in defaults
        super().__init__(instructions=instructions, tts=tts, memory_enabled=memory_enabled)

    @function_tool
    async def call_starter_agent(self):
        """
        Called when the GM wants to return to their main assistant.
        """
        if not self._validate_handoff("StarterAgent"):
            return None, "I'm having trouble transferring you right now. How else can I help you?"
        try:
            await self.on_exit(reason="handoff")
            memory_enabled = self._config.session.memory_enabled if self._config else True
            starter_agent = StarterAgent(
                config=self._config,
                memory_enabled=memory_enabled,
            )
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="StarterAgent",
                reason="return_to_starter",
                context_passed={},
            )
            return starter_agent, "Transferring you back to your assistant."
        except Exception as e:
            return self._handle_handoff_error(e, "StarterAgent")


class BookingAgent(OrchestratorAgent):
    def __init__(
        self,
        appointment_topic: str,
        config: Optional[AgentsConfig] = None,
        agent_config: Optional[Any] = None,
        default_timezone: Optional[str] = None,
        memory_enabled: bool = True,
    ) -> None:
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        tz = default_timezone or BOOKING_DEFAULT_TIMEZONE
        if agent_config:
            instructions = agent_config.instructions.strip().format(
                appointment_topic=appointment_topic,
                now_utc=now_utc,
                default_timezone=tz,
            )
            tts = inference.TTS(model=agent_config.tts.model, voice=agent_config.tts.voice)
        else:
            instructions = f"""You are the GM's scheduling assistant. You manage the GM's calendar and events. Only speak in English.
            Greet the user and state your role. The topic of the booking is {appointment_topic}. Acknowledge this topic naturally when greeting the user.

            Current date and time (UTC): {now_utc}. Use this when the user says "today", "tomorrow", "yesterday", or "next week".

            Your role:
            - Help the GM check existing appointments (e.g. list upcoming appointments, see details).
            - Help the GM book new appointments (e.g. suggest times, confirm booking).

            You complete the booking here using MCP tools. Once the user has given date, time, and appointment type, call the MCP tools to check availability and create the booking. Do not say you are transferring the user back to the main assistant to complete the booking; the main assistant cannot book appointments. You complete the booking; then you may offer to transfer back to the main assistant.

            If the requested slot is occupied or a booking attempt fails because the slot is taken, tell the user that slot is occupied. Do not transfer them back to the main assistant. Use MCP tools to find another available slot on the same day, suggest it to the user, and if they agree, book it. If that slot is also taken or the user declines, keep searching and suggesting other free slots the same day until one is booked or the user asks for another day or to go back to the main assistant. Only after a successful booking, or if the user explicitly asks to return to the main assistant or try another day, offer to transfer back to the main assistant.

            Before creating any appointment, you must check availability for the requested date and time using MCP tools (e.g. list events in that time range or get free/busy). If the check shows the slot is already occupied, do not create an event; tell the user the slot is occupied and use MCP tools to find another free slot the same day and suggest it. Only when the availability check shows the slot is free should you call the MCP tool that creates the event. Never call only a "create event" or "quick add" tool without checking availability first.

            When calling MCP tools that create a calendar event, always specify the timezone for the event (e.g. via a timezone parameter if the tool has one, or by passing start and end in ISO 8601 with offset, e.g. 2026-02-01T15:00:00+02:00 for 3 PM in Israel). Do not send naive times like 2026-02-01T15:00:00 without timezone or offset.
            """ + (f" When the user does not specify a timezone, use {tz} for creating events." if tz else " If the user has not specified a timezone, use a sensible default (e.g. Asia/Jerusalem if the user is in Israel) or ask the user which timezone to use.") + """ You can use the get_current_time or convert_time tools to resolve times like "3 PM" in the user's timezone to an ISO time with offset before passing to the create tool.

            You have access to MCP tools from the connected server. Use them whenever the user asks to check or book appointments. Call the appropriate tool with the parameters the user provides (name, date, time, reason, etc.), then summarize the result in short, clear speech.

            When the user asks for the time in a city or timezone (e.g. Cairo, New York), or to book in another timezone, use the get_current_time and convert_time tools and state the timezone clearly.

            After you have successfully created the booking with MCP tools, confirm to the user and state the time in the user's timezone (e.g. "I've booked you for tomorrow at 3 PM Israel time"). Only then ask if they want to return to their main assistant; if yes, call call_starter_agent to transfer them back. If not, end the conversation with the tool end_conversation.

            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            Keep responses brief and natural for voice: one or two sentences when possible. Confirm what you did (e.g. "I've booked you for Tuesday at 3 PM") and ask if they need anything else.
            You can use remembered context from past turns to personalize replies."""
            tts = inference.TTS(
                model="cartesia/sonic-3", voice="79f8b5fb-2cc8-479a-80df-29f7a7cf1a3e"
            )
        self._config = config  # None when using built-in defaults
        super().__init__(instructions=instructions, tts=tts, memory_enabled=memory_enabled)

    @function_tool
    async def get_current_time(self, timezone_name: str) -> str:
        """
        Get the current date and time in a specific timezone. Use IANA timezone names (e.g. America/New_York, Africa/Cairo, Europe/London).

        Args:
            timezone_name: IANA timezone name (e.g. America/New_York, Africa/Cairo)
        """
        try:
            if timezone_name in ("UTC", "Etc/UTC"):
                now = datetime.now(timezone.utc)
                return now.strftime("%Y-%m-%d %H:%M:%S UTC")
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
            src_tz = timezone.utc if source_timezone in ("UTC", "Etc/UTC") else ZoneInfo(source_timezone)
            tgt_tz = timezone.utc if target_timezone in ("UTC", "Etc/UTC") else ZoneInfo(target_timezone)
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
        Called when the GM wants to return to their main assistant.
        """
        if not self._validate_handoff("StarterAgent"):
            return None, "I'm having trouble transferring you right now. How else can I help you?"
        try:
            await self.on_exit(reason="handoff")
            memory_enabled = self._config.session.memory_enabled if self._config else True
            starter_agent = StarterAgent(config=self._config, memory_enabled=memory_enabled)
            self._log_handoff(
                source_agent=self._agent_name,
                target_agent="StarterAgent",
                reason="return_to_starter",
                context_passed={},
            )
            return starter_agent, "Transferring you back to your assistant."
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

    ctx.log_context_fields = {
        "room": ctx.room.name,
        **({"job_metadata": job_metadata} if job_metadata else {}),
    }

    cfg = load_config()
    if cfg:
        session_cfg = cfg.session
        session_kwargs = {
            "stt": inference.STT(
                model=session_cfg.stt_model,
                language=session_cfg.stt_language,
            ),
            "llm": inference.LLM(model=session_cfg.llm_model),
            "tts": inference.TTS(
                model=session_cfg.default_tts.model,
                voice=session_cfg.default_tts.voice,
            ),
            "turn_detection": MultilingualModel(),
            "vad": ctx.proc.userdata["vad"],
            "preemptive_generation": True,
        }
        if session_cfg.mcp_enabled and MCP_SERVER_URL:
            session_kwargs["mcp_servers"] = [
                mcp.MCPServerHTTP(
                    url=MCP_SERVER_URL,
                    transport_type="streamable_http",
                    client_session_timeout_seconds=60,
                ),
            ]
            logger.info("MCP integration enabled (Zapier)")
        else:
            if not session_cfg.mcp_enabled:
                logger.info("MCP disabled by config (session.mcp_enabled: false)")
            else:
                logger.info("MCP integration disabled (MCP_SERVER_URL not set)")
    else:
        session_kwargs = {
            "stt": inference.STT(model="assemblyai/universal-streaming", language="en"),
            "llm": inference.LLM(model="openai/gpt-4.1-mini"),
            "tts": inference.TTS(
                model="cartesia/sonic-3", voice="87286a8d-7ea7-4235-a41a-dd9fa6630feb"
            ),
            "turn_detection": MultilingualModel(),
            "vad": ctx.proc.userdata["vad"],
            "preemptive_generation": True,
        }
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

    mem0_user_id = (job_metadata or {}).get("user_id") or (job_metadata or {}).get("user_name") or ctx.room.name
    if cfg:
        entry_agent = StarterAgent(
            config=cfg,
            job_metadata=job_metadata or None,
            mem0_user_id=mem0_user_id,
            memory_enabled=cfg.session.memory_enabled,
        )
    else:
        entry_agent = StarterAgent(
            job_metadata=job_metadata or None,
            mem0_user_id=mem0_user_id,
        )
    await session.start(
        agent=entry_agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    import sys

    # Default to "dev" when no command is given (e.g. `python src/agents.py`)
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    cli.run_app(server)
