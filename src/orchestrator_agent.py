import logging
from datetime import datetime
from typing import Any, Dict, Optional

from livekit.agents import Agent
from livekit.agents.job import get_job_context
from livekit.agents.llm import ChatContext, ChatMessage, function_tool
from livekit import api

from memory import mem0_client

logger = logging.getLogger("agent")


class OrchestratorAgent(Agent):
    """
    Base orchestrator agent that provides comprehensive orchestration capabilities
    for managing multi-agent systems including context tracking, handoff management,
    error handling, and lifecycle management.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._agent_start_time: Optional[datetime] = None
        self._agent_name: str = self.__class__.__name__

    # ==================== Lifecycle Management ====================

    async def on_enter(self):
        """Enhanced entry point with orchestration logging and context restoration."""
        self._agent_start_time = datetime.now()
        
        # Get session context
        session_context = self._get_session_context()
        
        # Log agent entry with full context
        job_ctx = get_job_context()
        room_name = job_ctx.room.name if job_ctx else "unknown"
        
        logger.info(
            f"Agent entered: {self._agent_name}",
            extra={
                "agent_name": self._agent_name,
                "room": room_name,
                "timestamp": self._agent_start_time.isoformat(),
                "previous_agent": session_context.get("previous_agent"),
                "handoff_count": session_context.get("handoff_count", 0),
            }
        )
        
        # Restore context if available
        if session_context.get("conversation_history"):
            logger.debug(
                f"Restored conversation history for {self._agent_name}",
                extra={"history_length": len(session_context.get("conversation_history", []))}
            )
        
        # Track agent entry in session context
        self._update_session_context({
            "current_agent": self._agent_name,
            "agent_entries": session_context.get("agent_entries", []) + [{
                "agent": self._agent_name,
                "timestamp": self._agent_start_time.isoformat(),
                "type": "entry"
            }]
        })
        
        # Automatically greet the user when entering the call
        self.session.generate_reply()

    async def on_exit(self, reason: str = "handoff"):
        """
        Enhanced exit point with context saving and orchestration logging.
        
        Args:
            reason: Reason for exit (handoff, end_conversation, error)
        """
        exit_time = datetime.now()
        duration = None
        if self._agent_start_time:
            duration = (exit_time - self._agent_start_time).total_seconds()
        
        # Get session context
        session_context = self._get_session_context()
        
        # Log agent exit with full context
        job_ctx = get_job_context()
        room_name = job_ctx.room.name if job_ctx else "unknown"
        
        logger.info(
            f"Agent exited: {self._agent_name}",
            extra={
                "agent_name": self._agent_name,
                "room": room_name,
                "timestamp": exit_time.isoformat(),
                "reason": reason,
                "duration_seconds": duration,
            }
        )
        
        # Save current context
        self._update_session_context({
            "previous_agent": self._agent_name,
            "agent_exits": session_context.get("agent_exits", []) + [{
                "agent": self._agent_name,
                "timestamp": exit_time.isoformat(),
                "reason": reason,
                "duration_seconds": duration,
                "type": "exit"
            }]
        })

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Mem0: add user message, search memories, inject RAG context before LLM reply."""
        if not mem0_client:
            await super().on_user_turn_completed(turn_ctx, new_message)
            return
        session_context = self._get_session_context()
        mem0_user_id = session_context.get("mem0_user_id")
        if not mem0_user_id:
            job_ctx = get_job_context()
            mem0_user_id = job_ctx.room.name if job_ctx else "unknown"
        user_text = getattr(new_message, "text_content", None) or ""
        if not user_text:
            await super().on_user_turn_completed(turn_ctx, new_message)
            return
        try:
            await mem0_client.add(
                [{"role": "user", "content": user_text}],
                user_id=mem0_user_id,
            )
        except Exception as e:
            logger.warning("Mem0 add failed: %s", e)
        try:
            # Mem0 v2 search API requires filters (e.g. AND + user_id); passing user_id alone can cause 400
            filters = {"AND": [{"user_id": mem0_user_id}]}
            search_results = await mem0_client.search(
                user_text,
                filters=filters,
            )
        except Exception as e:
            logger.warning("Mem0 search failed: %s", e)
            search_results = None
        if search_results and search_results.get("results"):
            context_parts = []
            for result in search_results.get("results", []):
                paragraph = result.get("memory") or result.get("text")
                if paragraph:
                    source = "mem0 Memories"
                    if "from [" in paragraph:
                        source = paragraph.split("from [")[1].split("]")[0]
                        paragraph = paragraph.split("]")[1].strip()
                    context_parts.append(f"Source: {source}\nContent: {paragraph}\n")
            if context_parts:
                full_context = "Relevant memories:\n\n" + "\n\n".join(context_parts)
                turn_ctx.add_message(role="assistant", content=full_context)
                await self.update_chat_ctx(turn_ctx)
        await super().on_user_turn_completed(turn_ctx, new_message)

    # ==================== Context and State Management ====================

    def _get_session_context(self) -> Dict[str, Any]:
        """Retrieve session-level context that persists across agent transitions."""
        try:
            if hasattr(self.session, "userdata") and self.session.userdata:
                return getattr(self.session.userdata, "orchestration_context", {})
        except ValueError:
            # userdata is not set (e.g. in console mode); use instance fallback
            pass
        return getattr(self, "_session_context", {})

    def _set_session_context(self, context: Dict[str, Any]):
        """Set session-level context that persists across agent transitions."""
        try:
            if hasattr(self.session, "userdata") and self.session.userdata:
                if not hasattr(self.session.userdata, "orchestration_context"):
                    self.session.userdata.orchestration_context = {}
                self.session.userdata.orchestration_context.update(context)
                return
        except ValueError:
            # userdata is not set (e.g. in console mode); use instance fallback
            pass
        if not hasattr(self, "_session_context"):
            self._session_context = {}
        self._session_context.update(context)

    def _update_session_context(self, updates: Dict[str, Any]):
        """Update session context with new values."""
        current = self._get_session_context()
        current.update(updates)
        self._set_session_context(current)

    def _add_to_conversation_history(self, entry: Dict[str, Any]):
        """Add an entry to the conversation history."""
        context = self._get_session_context()
        history = context.get("conversation_history", [])
        history.append({
            **entry,
            "timestamp": datetime.now().isoformat(),
            "agent": self._agent_name
        })
        self._update_session_context({"conversation_history": history})

    # ==================== Handoff Management ====================

    def _log_handoff(
        self,
        source_agent: str,
        target_agent: str,
        reason: str,
        context_passed: Optional[Dict[str, Any]] = None
    ):
        """
        Log handoff events with full context for monitoring and debugging.
        
        Args:
            source_agent: Name of the agent initiating the handoff
            target_agent: Name of the target agent
            reason: Reason for the handoff
            context_passed: Any context data passed during handoff
        """
        handoff_data = {
            "source_agent": source_agent,
            "target_agent": target_agent,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "context": context_passed or {},
        }
        
        # Get session context
        session_context = self._get_session_context()
        handoff_count = session_context.get("handoff_count", 0) + 1
        
        # Log handoff event
        job_ctx = get_job_context()
        room_name = job_ctx.room.name if job_ctx else "unknown"
        
        logger.info(
            f"Agent handoff: {source_agent} -> {target_agent}",
            extra={
                **handoff_data,
                "room": room_name,
                "handoff_count": handoff_count,
            }
        )
        
        # Update session context with handoff history
        handoff_history = session_context.get("handoff_history", [])
        handoff_history.append(handoff_data)
        
        self._update_session_context({
            "handoff_count": handoff_count,
            "handoff_history": handoff_history,
            "last_handoff": handoff_data,
        })

    def _validate_handoff(self, target_agent_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate a handoff request before execution.
        
        Args:
            target_agent_name: Name of the target agent
            context: Context data for the handoff
            
        Returns:
            True if handoff is valid, False otherwise
        """
        # Basic validation - can be extended with more complex rules
        if not target_agent_name:
            logger.warning("Handoff validation failed: target agent name is empty")
            return False
        
        # Check for circular handoff patterns (optional)
        session_context = self._get_session_context()
        recent_handoffs = session_context.get("handoff_history", [])[-5:]  # Last 5 handoffs
        
        # Prevent immediate back-and-forth handoffs (can be configured)
        if recent_handoffs:
            last_handoff = recent_handoffs[-1]
            if (last_handoff.get("target_agent") == self._agent_name and
                last_handoff.get("source_agent") == target_agent_name):
                logger.warning(
                    f"Handoff validation: Potential circular handoff detected "
                    f"({self._agent_name} <-> {target_agent_name})"
                )
                # Allow it but log warning
        
        return True

    # ==================== Error Handling ====================

    def _handle_handoff_error(self, error: Exception, target_agent_name: str, fallback_message: str = None) -> tuple:
        """
        Handle errors during agent handoffs with graceful fallback.
        
        Args:
            error: The exception that occurred
            target_agent_name: Name of the target agent that failed
            fallback_message: Custom fallback message
            
        Returns:
            Tuple of (None, error_message) to indicate failed handoff
        """
        job_ctx = get_job_context()
        room_name = job_ctx.room.name if job_ctx else "unknown"
        
        logger.error(
            f"Handoff failed: {self._agent_name} -> {target_agent_name}",
            extra={
                "agent_name": self._agent_name,
                "target_agent": target_agent_name,
                "room": room_name,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=True
        )
        
        # Track error in session context
        session_context = self._get_session_context()
        errors = session_context.get("handoff_errors", [])
        errors.append({
            "source_agent": self._agent_name,
            "target_agent": target_agent_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        })
        self._update_session_context({"handoff_errors": errors})
        
        # Return fallback response
        message = fallback_message or (
            "I apologize, but I'm having trouble transferring you right now. "
            "Let me help you with that instead."
        )
        return None, message

    # ==================== End Conversation ====================

    @function_tool
    async def end_conversation(self):
        """Enhanced end conversation with orchestration cleanup and metrics."""
        # Log exit before ending
        await self.on_exit(reason="end_conversation")
        
        # Get final session context for summary
        session_context = self._get_session_context()
        
        # Log conversation summary
        job_ctx = get_job_context()
        room_name = job_ctx.room.name if job_ctx else "unknown"
        
        conversation_summary = {
            "room": room_name,
            "total_handoffs": session_context.get("handoff_count", 0),
            "agents_used": list(set([
                entry.get("agent") 
                for entry in session_context.get("agent_entries", [])
            ])),
            "handoff_errors": len(session_context.get("handoff_errors", [])),
            "conversation_duration": None,
        }
        
        # Calculate total conversation duration if available
        agent_entries = session_context.get("agent_entries", [])
        agent_exits = session_context.get("agent_exits", [])
        if agent_entries and agent_exits:
            first_entry = agent_entries[0].get("timestamp")
            last_exit = agent_exits[-1].get("timestamp")
            if first_entry and last_exit:
                try:
                    start = datetime.fromisoformat(first_entry)
                    end = datetime.fromisoformat(last_exit)
                    conversation_summary["conversation_duration"] = (end - start).total_seconds()
                except (ValueError, TypeError):
                    pass
        
        logger.info(
            "Conversation ended",
            extra={
                **conversation_summary,
                "timestamp": datetime.now().isoformat(),
            }
        )
        
        # Interrupt current session
        self.session.interrupt()
        
        # Generate goodbye message
        await self.session.generate_reply(
            instructions="say goodbye", allow_interruptions=False
        )
        
        # Clean up room if applicable
        if job_ctx and job_ctx.room.name != "mock_room":
            try:
                await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))
                logger.debug(f"Deleted room: {job_ctx.room.name}")
            except api.TwirpError as e:
                # Room might not exist or already deleted, log and continue
                logger.warning(f"Could not delete room {job_ctx.room.name}: {e}")
        else:
            logger.debug("Skipping room deletion for mock_room (console mode)")
        
        # Clear session context (optional - might want to keep for analytics)
        # self._set_session_context({})
