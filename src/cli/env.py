"""
Read and update .env. Never print or log secret values. Never overwrite existing unless force=True.
"""
import re
from pathlib import Path
from typing import Dict, Optional

DEFAULT_ENV_PATH = Path(".env")


def env_path(cwd: Optional[Path] = None) -> Path:
    p = cwd or Path.cwd()
    return p / DEFAULT_ENV_PATH.name


def read_env(path: Optional[Path] = None) -> Dict[str, str]:
    """Read .env into a dict (key -> value). Comments and empty lines skipped."""
    p = path or env_path()
    result: Dict[str, str] = {}
    if not p.exists():
        return result
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if match:
                key, value = match.group(1), match.group(2).strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1].replace("\\'", "'")
                result[key] = value
    return result


def write_env(vars_dict: Dict[str, str], path: Optional[Path] = None) -> None:
    """Write .env from a dict. Overwrites the file."""
    p = path or env_path()
    lines = [f"{k}={v}\n" for k, v in sorted(vars_dict.items())]
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)


def append_env(
    new_vars: Dict[str, str],
    path: Optional[Path] = None,
    force: bool = False,
    cwd: Optional[Path] = None,
) -> None:
    """
    Append or update .env with new_vars. Create file if missing.
    If force=False, do not overwrite existing keys. If force=True, overwrite.
    """
    p = path or env_path(cwd)
    existing = read_env(p)
    for k, v in new_vars.items():
        if force or k not in existing:
            existing[k] = v
    write_env(existing, p)


def env_exists(path: Optional[Path] = None) -> bool:
    p = path or env_path()
    return p.exists()


# Template for new .env (commented placeholders only)
ENV_TEMPLATE = """# Replaxy – credentials (do not commit secrets)
# Run: replaxy setup

# LiveKit (required for voice agent)
# LIVEKIT_URL=
# LIVEKIT_API_KEY=
# LIVEKIT_API_SECRET=

# Zapier MCP (optional) – full URL e.g. https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN
# MCP_SERVER_URL=

# Mem0 (optional) – conversation memory
# MEM0_API_KEY=
"""


def create_env_template(path: Optional[Path] = None) -> None:
    """Create .env with commented placeholders only."""
    p = path or env_path()
    if p.exists():
        return
    with open(p, "w", encoding="utf-8") as f:
        f.write(ENV_TEMPLATE)
