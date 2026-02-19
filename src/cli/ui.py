"""
Centralized UI rendering for the Replaxy CLI.

All styled output goes through this module. No inline print styling elsewhere.
Supports --no-color mode for CI environments.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ── Brand palette ────────────────────────────────────────────────────────────
PRIMARY   = "bright_cyan"
SUCCESS   = "bright_green"
WARNING   = "yellow"
ERROR_COL = "red"
INFO      = "grey70"
DIM       = "grey42"
ACCENT    = "cyan"

VERSION = "1.0.0"
TAGLINE = "Executive Voice Orchestration Framework"

# ── ASCII logo ────────────────────────────────────────────────────────────────
LOGO = r"""
  ██████╗ ███████╗██████╗ ██╗      █████╗ ██╗  ██╗██╗   ██╗
  ██╔══██╗██╔════╝██╔══██╗██║     ██╔══██╗╚██╗██╔╝╚██╗ ██╔╝
  ██████╔╝█████╗  ██████╔╝██║     ███████║ ╚███╔╝  ╚████╔╝
  ██╔══██╗██╔══╝  ██╔═══╝ ██║     ██╔══██║ ██╔██╗   ╚██╔╝
  ██║  ██║███████╗██║     ███████╗██║  ██║██╔╝ ██╗   ██║
  ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝
"""

LOGO_COMPACT = r"""  Replaxy"""


class UI:
    """All styled output for the Replaxy CLI. Instantiate with no_color=True to strip ANSI."""

    def __init__(self, no_color: bool = False) -> None:
        self.no_color = no_color
        self.console = Console(no_color=no_color, highlight=False)

    # ── Logo ──────────────────────────────────────────────────────────────────

    def logo(self, compact: bool = False) -> None:
        """Render the ASCII logo, version, and tagline."""
        if compact:
            self.console.print()
            self.console.print(
                f"  [bold {PRIMARY}]Replaxy[/] [bold]v{VERSION}[/]  [{DIM}]{TAGLINE}[/]"
            )
            self.console.print()
            return

        logo_text = Text(LOGO, style=f"bold {PRIMARY}")
        self.console.print(logo_text)
        version_line = Text()
        version_line.append(f"  Replaxy v{VERSION}", style=f"bold {PRIMARY}")
        version_line.append(f"  –  {TAGLINE}", style=DIM)
        self.console.print(version_line)
        self.console.print()

    # ── Section headers ───────────────────────────────────────────────────────

    def section(self, title: str) -> None:
        """Render a section header in primary color."""
        self.console.print()
        if self.no_color:
            self.console.print(f"=== {title} ===")
        else:
            rule_text = Text(f" {title} ", style=f"bold {PRIMARY}")
            self.console.rule(rule_text, style=ACCENT)
        self.console.print()

    # ── Standard messages ─────────────────────────────────────────────────────

    def success(self, msg: str) -> None:
        if self.no_color:
            self.console.print(f"[OK] {msg}")
        else:
            self.console.print(f"  [{SUCCESS}]✔[/]  {msg}")

    def warning(self, msg: str) -> None:
        if self.no_color:
            self.console.print(f"[WARN] {msg}")
        else:
            self.console.print(f"  [{WARNING}]![/]  [{WARNING}]{msg}[/]")

    def info(self, msg: str) -> None:
        if self.no_color:
            self.console.print(f"  {msg}")
        else:
            self.console.print(f"  [{INFO}]{msg}[/]")

    def dim(self, msg: str) -> None:
        self.console.print(f"  [{DIM}]{msg}[/]" if not self.no_color else f"  {msg}")

    # ── Error output ──────────────────────────────────────────────────────────

    def error(self, msg: str, action: Optional[str] = None) -> None:
        """Single structured error with optional action hint."""
        if self.no_color:
            self.console.print(f"[ERROR] {msg}")
            if action:
                self.console.print(f"  Action: {action}")
        else:
            self.console.print(f"  [{ERROR_COL}][ERROR][/]  {msg}")
            if action:
                self.console.print(f"  [{ACCENT}]Action:[/]  {action}")

    def error_list(self, errors: List[str], title: str = "Configuration Errors") -> None:
        """Render a numbered list of errors under a heading."""
        if self.no_color:
            self.console.print(f"\n{title}:\n")
            for i, e in enumerate(errors, 1):
                self.console.print(f"  {i}. {e}")
            self.console.print()
            return

        panel_body = Text()
        for i, e in enumerate(errors, 1):
            panel_body.append(f"  {i}. ", style=DIM)
            panel_body.append(f"{e}\n", style="white")

        self.console.print(
            Panel(
                panel_body,
                title=f"[bold {ERROR_COL}] {title} [/]",
                border_style=ERROR_COL,
                padding=(1, 2),
            )
        )

    # ── Validation result ─────────────────────────────────────────────────────

    def validation_ok(self) -> None:
        if self.no_color:
            self.console.print("\n  All checks passed.\n")
        else:
            self.console.print(
                Panel(
                    f"[{SUCCESS}]All checks passed.[/]",
                    border_style=SUCCESS,
                    padding=(0, 2),
                )
            )

    # ── Doctor status table ───────────────────────────────────────────────────

    def doctor_table(self, results: Sequence[Tuple[str, str, str]]) -> None:
        """
        Render doctor status table.
        results: list of (service_name, status_label, detail)
        status_label: "ok" | "warn" | "fail"
        """
        if self.no_color:
            self.console.print()
            for name, status, detail in results:
                tag = "OK" if status == "ok" else ("WARN" if status == "warn" else "FAIL")
                line = f"  {name:<16} [{tag}]"
                if detail:
                    line += f"  {detail}"
                self.console.print(line)
            self.console.print()
            return

        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style=f"bold {PRIMARY}",
            padding=(0, 2),
        )
        table.add_column("Integration", style="bold", min_width=16)
        table.add_column("Status", min_width=8)
        table.add_column("Detail", style=DIM)

        for name, status, detail in results:
            if status == "ok":
                badge = Text("✔  Connected", style=SUCCESS)
            elif status == "warn":
                badge = Text("!  Warning", style=WARNING)
            else:
                badge = Text("✘  Failed", style=ERROR_COL)
            table.add_row(name, badge, detail or "")

        self.console.print()
        self.console.print(table)
        self.console.print()

    # ── Run banner ────────────────────────────────────────────────────────────

    def run_banner(self, mode: str) -> None:
        """Show the launch banner before starting the agent subprocess."""
        label = "dev" if mode == "dev" else "production"
        if self.no_color:
            self.console.print(f"\nStarting Replaxy agent [{label}]...\n")
        else:
            self.console.print(
                Panel(
                    f"  [{PRIMARY}]Starting Replaxy agent[/]  [{DIM}][{label}][/]",
                    border_style=ACCENT,
                    padding=(0, 2),
                )
            )
        self.console.print()

    # ── Setup confirmation block ──────────────────────────────────────────────

    def setup_complete(self, enabled: List[str]) -> None:
        """Show what was configured at end of setup."""
        if not enabled:
            self.info("No integrations enabled.")
            return
        body = "\n".join(f"  • {s}" for s in enabled)
        if self.no_color:
            self.console.print(f"\nSetup complete. Configured:\n{body}\n")
        else:
            self.console.print(
                Panel(
                    f"[{SUCCESS}]Setup complete.[/]\n\n[{DIM}]Configured:[/]\n{body}",
                    border_style=SUCCESS,
                    padding=(1, 2),
                )
            )

    # ── Low-level passthrough ─────────────────────────────────────────────────

    def print(self, *args, **kwargs) -> None:  # noqa: A003
        self.console.print(*args, **kwargs)
