"""
Load and validate the agents config file (YAML).
When the file is missing, load_config() returns None; callers use built-in defaults.
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent")

# Default path relative to current working directory (project root when running uv run python src/agents.py)
DEFAULT_CONFIG_PATH = "config/agents.yaml"


@dataclass
class TTSConfig:
    model: str
    voice: str


@dataclass
class SessionConfig:
    llm_model: str
    stt_model: str
    stt_language: str
    default_tts: TTSConfig
    default_timezone: str
    mcp_enabled: bool
    memory_enabled: bool


@dataclass
class AgentConfig:
    id: str
    name: str
    role: str  # "starter" | "specialist"
    instructions: str
    tts: TTSConfig
    handoff_to: List[str] = field(default_factory=list)  # only for starter
    agent_type: str = "generic"  # "generic" | "booking" for specialist
    memory_enabled: bool = True
    mcp_enabled: bool = True


@dataclass
class AgentsConfig:
    session: SessionConfig
    agents: List[AgentConfig]
    _by_id: Dict[str, AgentConfig] = field(default_factory=dict, repr=False)

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        return self._by_id.get(agent_id)

    def get_starter(self) -> Optional[AgentConfig]:
        for a in self.agents:
            if a.role == "starter":
                return a
        return None


def _parse_tts(raw: Any) -> TTSConfig:
    if not isinstance(raw, dict):
        raise ValueError("tts must be an object with model and voice")
    return TTSConfig(
        model=str(raw.get("model", "cartesia/sonic-3")),
        voice=str(raw.get("voice", "")),
    )


def _parse_session(raw: Any) -> SessionConfig:
    """Parse a session block (the object under session: in YAML)."""
    if not isinstance(raw, dict):
        raise ValueError("session must be an object")
    s = raw
    default_tts = s.get("default_tts") or {}
    if isinstance(default_tts, dict):
        tts = TTSConfig(
            model=str(default_tts.get("model", "cartesia/sonic-3")),
            voice=str(default_tts.get("voice", "87286a8d-7ea7-4235-a41a-dd9fa6630feb")),
        )
    else:
        tts = _parse_tts(default_tts)
    return SessionConfig(
        llm_model=str(s.get("llm_model", "openai/gpt-4.1-mini")),
        stt_model=str(s.get("stt_model", "assemblyai/universal-streaming")),
        stt_language=str(s.get("stt_language", "en")),
        default_tts=tts,
        default_timezone=str(s.get("default_timezone", "UTC")),
        mcp_enabled=bool(s.get("mcp_enabled", True)),
        memory_enabled=bool(s.get("memory_enabled", True)),
    )


def _parse_agent(raw: Any) -> AgentConfig:
    if not isinstance(raw, dict):
        raise ValueError("each agent must be an object")
    tts_raw = raw.get("tts") or {}
    tts = _parse_tts(tts_raw) if isinstance(tts_raw, dict) else _parse_tts({"model": "cartesia/sonic-3", "voice": raw.get("voice", "")})
    handoff_to = raw.get("handoff_to")
    if isinstance(handoff_to, list):
        handoff_to = [str(x) for x in handoff_to]
    else:
        handoff_to = []
    return AgentConfig(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        role=str(raw.get("role", "specialist")),
        instructions=str(raw.get("instructions", "")),
        tts=tts,
        handoff_to=handoff_to,
        agent_type=str(raw.get("agent_type", "generic")),
        memory_enabled=bool(raw.get("memory_enabled", True)),
        mcp_enabled=bool(raw.get("mcp_enabled", True)),
    )


def _validate(config: AgentsConfig) -> None:
    if not config.agents:
        raise ValueError("config must define at least one agent")
    starters = [a for a in config.agents if a.role == "starter"]
    if len(starters) != 1:
        raise ValueError("config must have exactly one agent with role: starter")
    ids = {a.id for a in config.agents}
    for a in config.agents:
        if not a.id:
            raise ValueError("each agent must have an id")
        config._by_id[a.id] = a
        for target in a.handoff_to:
            if target not in ids:
                raise ValueError(f"agent {a.id} handoff_to references unknown agent id: {target}")


def load_config() -> Optional[AgentsConfig]:
    """
    Load agents config from AGENTS_CONFIG_PATH or config/agents.yaml.
    Returns None if the file is missing or invalid (logs and returns None so callers use defaults).
    """
    path_str = os.environ.get("AGENTS_CONFIG_PATH", "").strip() or DEFAULT_CONFIG_PATH
    path = Path(path_str)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        logger.debug("Agents config file not found at %s, using built-in defaults", path)
        return None
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load agents config from %s: %s", path, e)
        return None
    if not data:
        return None
    try:
        if not isinstance(data, dict):
            raise ValueError("config root must be an object")
        session = _parse_session(data.get("session", {}))
        agents_raw = data.get("agents", [])
        if not isinstance(agents_raw, list):
            raise ValueError("config.agents must be a list")
        agents = [_parse_agent(a) for a in agents_raw]
        config = AgentsConfig(session=session, agents=agents)
        _validate(config)
        logger.info("Loaded agents config from %s (%d agents)", path, len(agents))
        return config
    except Exception as e:
        logger.warning("Invalid agents config in %s: %s", path, e)
        return None
