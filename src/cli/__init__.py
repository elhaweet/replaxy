"""
Replaxy CLI – setup, credentials, validation, run.
All output goes through src/cli/ui.py. No inline styling here.
"""
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer

from .config_loader import (
    DEFAULT_CONFIG,
    config_exists,
    config_path,
    load_config,
    save_config,
)
from .env import append_env, create_env_template, env_path, read_env
from .ui import UI
from .validators import validate_all

# ── App definition ────────────────────────────────────────────────────────────

app = typer.Typer(
    name="replaxy",
    help="Executive Voice Orchestration Framework.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

def _ui(no_color: bool = False) -> UI:
    return UI(no_color=no_color)


def _cwd() -> Path:
    return Path.cwd()


_NO_COLOR_OPTION = typer.Option(False, "--no-color", help="Disable colors and emojis (CI-safe).")


@app.callback()
def main() -> None:
    """Executive Voice Orchestration Framework."""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _prompt_yn(ui: UI, msg: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    try:
        raw = typer.prompt(f"  {msg} [{default_str}]", default="y" if default else "n")
        r = raw.strip().lower()
        if not r:
            return default
        return r in ("y", "yes", "1")
    except Exception:
        return default


def _prompt_secret(msg: str, default: str = "") -> str:
    return typer.prompt(f"  {msg}", default=default, hide_input=True).strip()


def _prompt_text(msg: str, default: str = "") -> str:
    return typer.prompt(f"  {msg}", default=default).strip()


def _url_ok(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


# ── replaxy init ──────────────────────────────────────────────────────────────


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config."),
    no_color: bool = _NO_COLOR_OPTION,
) -> None:
    """Initialize a new Replaxy project (creates replaxy.config.yaml and .env template)."""
    ui = _ui(no_color)
    ui.logo()
    ui.section("Initialize Project")

    cfg_p = config_path(_cwd())
    env_p = env_path(_cwd())

    if cfg_p.exists() and not force:
        ui.error(
            "replaxy.config.yaml already exists.",
            action="Use --force to overwrite: replaxy init --force",
        )
        raise typer.Exit(1)

    save_config(DEFAULT_CONFIG, cfg_p)
    ui.success(f"Created {cfg_p.name}")

    if not env_p.exists():
        create_env_template(env_p)
        ui.success(f"Created {env_p.name} (template with placeholders)")
    else:
        ui.dim(f"{env_p.name} already exists — skipping.")

    ui.console.print()
    ui.info("Next step:  replaxy setup")
    ui.console.print()


# ── replaxy setup ─────────────────────────────────────────────────────────────


@app.command()
def setup(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing .env values."),
    no_color: bool = _NO_COLOR_OPTION,
) -> None:
    """Interactive setup: configure integrations and store credentials in .env."""
    ui = _ui(no_color)
    ui.logo(compact=True)
    ui.section("Integration Setup")

    cwd = _cwd()
    cfg_p = config_path(cwd)
    env_p = env_path(cwd)

    if not config_exists(cfg_p):
        ui.error("replaxy.config.yaml not found.", action="Run: replaxy init")
        raise typer.Exit(1)

    data = load_config(cfg_p)
    existing_env = read_env(env_p)
    configured: List[str] = []

    # ── LiveKit ──────────────────────────────────────────────────────────────
    ui.info("LiveKit provides the real-time voice infrastructure.")
    if _prompt_yn(ui, "Enable LiveKit?", default=True):
        ui.console.print()
        url = _prompt_text("LIVEKIT_URL", default=existing_env.get("LIVEKIT_URL", ""))
        if not _url_ok(url):
            ui.error("LIVEKIT_URL must be a valid http(s) URL.")
            raise typer.Exit(1)
        api_key = _prompt_secret("LIVEKIT_API_KEY", default=existing_env.get("LIVEKIT_API_KEY", ""))
        api_secret = _prompt_secret("LIVEKIT_API_SECRET", default=existing_env.get("LIVEKIT_API_SECRET", ""))
        if not api_key or not api_secret:
            ui.error("LIVEKIT_API_KEY and LIVEKIT_API_SECRET cannot be empty.")
            raise typer.Exit(1)
        append_env(
            {"LIVEKIT_URL": url, "LIVEKIT_API_KEY": api_key, "LIVEKIT_API_SECRET": api_secret},
            env_p, force=force, cwd=cwd,
        )
        data.setdefault("integrations", {})["livekit"] = {"enabled": True}
        configured.append("LiveKit")
        ui.success("LiveKit credentials saved.")
    else:
        data.setdefault("integrations", {})["livekit"] = {"enabled": False}

    ui.console.print()

    # ── Mem0 ─────────────────────────────────────────────────────────────────
    ui.info("Mem0 enables persistent conversation memory across sessions.")
    if _prompt_yn(ui, "Enable Mem0 memory?", default=False):
        ui.console.print()
        mem0_key = _prompt_secret("MEM0_API_KEY", default=existing_env.get("MEM0_API_KEY", ""))
        if not mem0_key:
            ui.error("MEM0_API_KEY cannot be empty.")
            raise typer.Exit(1)
        mem0_project = _prompt_text("MEM0_PROJECT_ID (optional, press Enter to skip)",
                                    default=existing_env.get("MEM0_PROJECT_ID", ""))
        to_set = {"MEM0_API_KEY": mem0_key}
        if mem0_project:
            to_set["MEM0_PROJECT_ID"] = mem0_project
        append_env(to_set, env_p, force=force, cwd=cwd)
        data["memory"] = {"enabled": True, "type": "mem0"}
        data.setdefault("integrations", {})["mem0"] = {"enabled": True}
        configured.append("Mem0 Memory")
        ui.success("Mem0 credentials saved.")
    else:
        data["memory"] = {"enabled": False, "type": None}
        data.setdefault("integrations", {})["mem0"] = {"enabled": False}

    ui.console.print()

    # ── Zapier MCP ────────────────────────────────────────────────────────────
    ui.info("Zapier MCP enables calendar and booking tool integrations.")
    if _prompt_yn(ui, "Enable Zapier MCP?", default=False):
        ui.console.print()
        mcp_url = _prompt_text(
            "Zapier MCP URL  (e.g. https://mcp.zapier.com/api/v1/connect?token=...)",
            default=existing_env.get("MCP_SERVER_URL", ""),
        )
        if not mcp_url.strip():
            ui.error("MCP_SERVER_URL cannot be empty.")
            raise typer.Exit(1)
        append_env({"MCP_SERVER_URL": mcp_url.strip()}, env_p, force=force, cwd=cwd)
        data.setdefault("integrations", {})["zapier_mcp"] = {"enabled": True}
        configured.append("Zapier MCP")
        ui.success("Zapier MCP URL saved.")
    else:
        data.setdefault("integrations", {})["zapier_mcp"] = {"enabled": False}

    save_config(data, cfg_p)
    ui.console.print()
    ui.setup_complete(configured)
    ui.info("Next step:  replaxy validate")
    ui.console.print()


# ── replaxy validate ──────────────────────────────────────────────────────────


@app.command()
def validate(
    no_color: bool = _NO_COLOR_OPTION,
) -> None:
    """Check replaxy.config.yaml integrity and .env completeness for enabled integrations."""
    ui = _ui(no_color)
    ui.logo(compact=True)
    ui.section("Configuration Validation")

    ok, errors = validate_all(config_path(_cwd()), env_path(_cwd()))
    if ok:
        ui.validation_ok()
    else:
        ui.error_list(errors)
        ui.dim("Run: replaxy setup")
        ui.console.print()
        raise typer.Exit(1)


# ── replaxy run ───────────────────────────────────────────────────────────────


@app.command()
def run(
    dev: bool = typer.Option(False, "--dev", "-d", help="Run in dev mode (local LiveKit testing)."),
    no_color: bool = _NO_COLOR_OPTION,
) -> None:
    """Validate configuration, then start the Replaxy agent. Hard-stops on any error."""
    ui = _ui(no_color)
    ui.logo(compact=True)
    ui.section("Pre-flight Checks")

    cwd = _cwd()
    env_p = env_path(cwd)
    cfg_p = config_path(cwd)

    if not env_p.exists():
        ui.error(".env not found.", action="Run: replaxy init")
        raise typer.Exit(1)

    from dotenv import load_dotenv
    load_dotenv(env_p)

    if not config_exists(cfg_p):
        ui.error("replaxy.config.yaml not found.", action="Run: replaxy init")
        raise typer.Exit(1)

    ok, errors = validate_all(cfg_p, env_p)
    if not ok:
        ui.error_list(errors)
        ui.dim("Run: replaxy setup")
        ui.console.print()
        raise typer.Exit(1)

    ui.success("Configuration valid.")
    ui.console.print()
    mode = "dev" if dev else "production"
    ui.run_banner(mode)

    cmd = [sys.executable, "src/agents.py", "dev" if dev else "start"]
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        raise typer.Exit(e.returncode or 1)
    except FileNotFoundError:
        ui.error("src/agents.py not found.", action="Run from the project root directory.")
        raise typer.Exit(1)


# ── replaxy doctor ────────────────────────────────────────────────────────────


def _check_livekit(env: dict) -> tuple[str, str, str]:
    """Returns (service, status_label, detail)."""
    url = (env.get("LIVEKIT_URL") or "").strip()
    key = (env.get("LIVEKIT_API_KEY") or "").strip()
    secret = (env.get("LIVEKIT_API_SECRET") or "").strip()
    if not url or not key or not secret:
        return "LiveKit", "fail", "Missing credentials"
    try:
        import asyncio
        from livekit import api
        async def _ping():
            inst = api.LiveKitAPI(url=url, api_key=key, api_secret=secret)
            await inst.room.list_rooms(api.ListRoomsRequest())
            await inst.aclose()
        asyncio.run(_ping())
        return "LiveKit", "ok", ""
    except Exception as exc:
        return "LiveKit", "fail", str(exc)[:72]


def _check_mem0(env: dict) -> tuple[str, str, str]:
    key = (env.get("MEM0_API_KEY") or "").strip()
    if not key:
        return "Mem0", "fail", "MEM0_API_KEY not set"
    try:
        import asyncio
        from mem0 import AsyncMemoryClient
        async def _ping():
            client = AsyncMemoryClient()
            await client.search("health", filters={"AND": [{"user_id": "__doctor__"}]})
        asyncio.run(_ping())
        return "Mem0", "ok", ""
    except Exception as exc:
        return "Mem0", "fail", str(exc)[:72]


def _check_zapier(env: dict) -> tuple[str, str, str]:
    url = (env.get("MCP_SERVER_URL") or "").strip()
    if not url:
        return "Zapier MCP", "fail", "MCP_SERVER_URL not set"
    try:
        import urllib.request
        urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"), timeout=10
        )
        return "Zapier MCP", "ok", ""
    except Exception as exc:
        return "Zapier MCP", "fail", str(exc)[:72]


@app.command()
def doctor(
    no_color: bool = _NO_COLOR_OPTION,
) -> None:
    """Test connectivity for all enabled integrations. Does not crash on failure."""
    ui = _ui(no_color)
    ui.logo(compact=True)
    ui.section("Integration Health Check")

    if not config_exists(config_path(_cwd())):
        ui.error("replaxy.config.yaml not found.", action="Run: replaxy init")
        raise typer.Exit(1)

    data = load_config(config_path(_cwd()))
    env = read_env(env_path(_cwd()))
    integrations = data.get("integrations") or {}
    results = []

    if integrations.get("livekit", {}).get("enabled"):
        ui.dim("Checking LiveKit...")
        results.append(_check_livekit(env))

    if integrations.get("mem0", {}).get("enabled"):
        ui.dim("Checking Mem0...")
        results.append(_check_mem0(env))

    if integrations.get("zapier_mcp", {}).get("enabled"):
        ui.dim("Checking Zapier MCP...")
        results.append(_check_zapier(env))

    if not results:
        ui.warning("No integrations enabled.")
        ui.info("Run: replaxy setup")
        ui.console.print()
        return

    ui.doctor_table(results)
    any_fail = any(s == "fail" for _, s, _ in results)
    if any_fail:
        ui.dim("Some checks failed. Run: replaxy setup to update credentials.")
    else:
        ui.success("All integrations are healthy.")
    ui.console.print()
