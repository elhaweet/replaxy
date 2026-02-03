"""
Optional Mem0 memory layer for conversation memory.
Used by both agents.py (env/config) and orchestrator_agent.py (on_user_turn_completed).
"""
import logging
import os

logger = logging.getLogger("agent")

MEM0_API_KEY = os.environ.get("MEM0_API_KEY", "").strip()
mem0_client = None
if MEM0_API_KEY:
    try:
        from mem0 import AsyncMemoryClient
        mem0_client = AsyncMemoryClient()
        logger.info("Mem0 memory layer enabled")
    except Exception as e:
        logger.warning("Mem0 client init failed, memory disabled: %s", e)
        mem0_client = None
