"""
Validate lk-mav.config.yaml and .env for enabled integrations.
Structured errors; no secrets in messages.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config_loader import config_exists, load_config
from .env import env_path, read_env


REQUIRED_TOP_LEVEL = {"project", "assistant", "roles", "memory", "integrations", "handoff_rules"}

INTEGRATION_ENV_MAP = {
    "livekit": ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"],
    "mem0": ["MEM0_API_KEY"],
    "zapier_mcp": ["MCP_SERVER_URL"],
}


def validate_config_integrity(data: Dict[str, Any]) -> List[str]:
    """Check config schema. Return list of error messages (empty if valid)."""
    errors: List[str] = []
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"Config missing required sections: {', '.join(sorted(missing))}")

    if "roles" in data and not isinstance(data["roles"], list):
        errors.append("Config 'roles' must be a list")

    if "memory" in data and isinstance(data["memory"], dict):
        mem = data["memory"]
        if mem.get("enabled") and not mem.get("type") and data.get("integrations", {}).get("mem0", {}).get("enabled"):
            pass  # mem0 enabled is consistent
        if mem.get("enabled") and mem.get("type") not in (None, "mem0"):
            errors.append("Config memory.type must be null or 'mem0' when memory.enabled is true")

    integrations = data.get("integrations") or {}
    if not isinstance(integrations, dict):
        errors.append("Config 'integrations' must be an object")

    handoff = data.get("handoff_rules")
    if handoff is not None and not isinstance(handoff, dict):
        errors.append("Config 'handoff_rules' must be an object")
    if isinstance(handoff, dict) and "mode" not in handoff:
        errors.append("Config 'handoff_rules' must have 'mode'")

    return errors


def validate_integration_env(
    data: Dict[str, Any],
    env: Optional[Dict[str, str]] = None,
    env_path_override: Optional[Path] = None,
) -> List[str]:
    """Check that enabled integrations have required env vars set and non-empty."""
    errors: List[str] = []
    if env is None:
        env = read_env(env_path_override or env_path())

    integrations = data.get("integrations") or {}
    for key, required_vars in INTEGRATION_ENV_MAP.items():
        sub = integrations.get(key)
        if isinstance(sub, dict) and sub.get("enabled"):
            for var in required_vars:
                value = (env.get(var) or "").strip()
                if not value:
                    errors.append(
                        f"{key.replace('_', ' ').title()} enabled but {var} missing or empty. Run: lk-mav setup"
                    )
    return errors


def validate_all(
    config_path_override: Optional[Path] = None,
    env_path_override: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    """
    Run all validations. Returns (success, list of error messages).
    Config must exist; if missing, returns (False, ["Config not found..."]).
    """
    errors: List[str] = []
    if not config_exists(config_path_override):
        errors.append("lk-mav.config.yaml not found. Run: lk-mav init")
        return False, errors
    try:
        data = load_config(config_path_override)
    except Exception as e:
        errors.append(f"Invalid config: {e}")
        return False, errors

    errors.extend(validate_config_integrity(data))
    errors.extend(validate_integration_env(data, env_path=env_path_override))
    return len(errors) == 0, errors
