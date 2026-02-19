"""
Load and save replaxy.config.yaml. No secrets in this file.
"""
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG_PATH = Path("replaxy.config.yaml")

DEFAULT_CONFIG: Dict[str, Any] = {
    "project": {
        "name": "replaxy-project",
        "version": "0.1.0",
    },
    "assistant": {
        "name": "Main Assistant",
        "tone": "professional",
        "language": "en",
    },
    "roles": [],
    "memory": {
        "enabled": False,
        "type": None,
    },
    "integrations": {
        "livekit": {"enabled": False},
        "mem0": {"enabled": False},
        "zapier_mcp": {"enabled": False},
    },
    "handoff_rules": {
        "mode": "keyword",
        "rules": [],
    },
}


def config_path(cwd: Optional[Path] = None) -> Path:
    p = cwd or Path.cwd()
    return p / DEFAULT_CONFIG_PATH.name


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load replaxy.config.yaml. Raises FileNotFoundError if missing."""
    p = path or config_path()
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}. Run: replaxy init")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("replaxy.config.yaml must be a YAML object")
    return data


def save_config(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Write replaxy.config.yaml."""
    p = path or config_path()
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def config_exists(path: Optional[Path] = None) -> bool:
    p = path or config_path()
    return p.exists()
