"""
Rich-based TUI for ZWO EFW filter wheel control.
"""

import json
import os
import sys
import termios
import tty
from pathlib import Path
from typing import Dict, Optional

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from efw_sdk import EFWDevice, EFWError


CONFIG_FILE = Path("filters.json")

# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------


def load_config(slot_num: int) -> Dict[int, str]:
    """Load filter config from JSON file.

    Returns a dict mapping 1-based slot numbers to filter names.
    Missing file returns an empty dict.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_config(config: Dict[int, str]) -> None:
    """Save filter config to JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Interactive config entry
# ---------------------------------------------------------------------------


def prompt_filter_names(device: EFWDevice) -> Dict[int, str]:
    """Prompt the user to enter a name for each slot."""
    console = Console()
    console.print(
        "[bold yellow]This is the first time the device has been configured.[/bold yellow]"
    )
    console.print(f"Your filter wheel has [bold]{device.slot_num}[/bold] slot(s).")
    console.print("Please enter a name for each slot.")

    config: Dict[int, str] = {}

    for slot in range(1, device.slot_num + 1):
        name = Prompt.ask(
            f"  [bold]Slot {slot}[/bold] filter name",
            default="",
        )
        if name.strip():
            config[slot] = name.strip()
        console.print(f"  [dim]Slot {slot}: {'(empty)' if not name.strip() else name.strip()}[/dim]")

    return config


# ---------------------------------------------------------------------------
# TUI layout
# ---------------------------------------------------------------------------


class EFWFilterWheelUI:
    """Rich TUI for the filter wheel."""

    def __init__(self, device: EFWDevice, config: Dict[int, str]):
        self.device = device
        self.config = config
        self.console = Console()
        self._running = True
        self._current_slot = 0
        self._error: Optional[str] = None
        self._status: Optional[str] = None

    # -- Rendering --

    def _render(self) -> Panel:
        """Build the full TUI layout as a Rich Panel."""
        # Header
        device_name = self.device.device_name
        info_parts: list[str] = [
            f"Slots: {self.device.slot_num}",
            f"SDK: {self.device.sdk_version}",
        ]
        try:
            info_parts.append(f"Firmware: {self.device.firmware_version()}")
        except EFWError:
            pass

        header = (
            f"[bold]ZWO Filter Wheel Controller[/bold]  "
            f"[bold cyan]{device_name}[/bold cyan]"
        )
        info = f"[yellow]{'  |  '.join(info_parts)}[/yellow]"

        # Current position
        pos = self._current_slot
        slot_label = self.config.get(pos + 1, f"Slot {pos + 1}")
        bar_len = 20
        filled = int((pos + 1) / max(self.device.slot_num, 1) * bar_len)
        unfilled = bar_len - filled
        bar = f"[green]{'█' * filled}[/green][dim]{'░' * unfilled}[/dim]"

        # Filter list — build aligned rows dynamically as pure strings
        slots = list(range(1, self.device.slot_num + 1))
        cols = 2

        # Find the maximum text width for each column to align them perfectly
        col_widths = [0] * cols
        for i, s in enumerate(slots):
            c = i % cols
            name = self.config.get(s, f"Slot {s}")
            raw_len = len(f"{s}  {name}")
            if raw_len > col_widths[c]:
                col_widths[c] = raw_len

        # Build the strings with exact space padding
        filter_lines: list[str] = []
        for i in range(0, len(slots), cols):
            row_slots = slots[i : i + cols]
            cells = []
            for idx, s in enumerate(row_slots):
                name = self.config.get(s, f"Slot {s}")
                raw_text = f"{s}  {name}"

                # Add 4 spaces of gutter, except for the last item in the row
                pad_len = (col_widths[idx] - len(raw_text)) + 4 if idx < len(row_slots) - 1 else 0

                if s == pos + 1:
                    cells.append(f"[bold cyan]{raw_text}[/bold cyan]" + (" " * pad_len))
                else:
                    cells.append(raw_text + (" " * pad_len))

            filter_lines.append("".join(cells))

        # Commands
        cmd_parts = [
            f"[bold yellow]1–{min(self.device.slot_num, 9)}[/bold yellow] [dim]Move to slot[/dim]",
            "[bold yellow]s[/bold yellow] [dim]Save config[/dim]",
            "[bold yellow]r[/bold yellow] [dim]Reload[/dim]",
            "[bold yellow]q[/bold yellow] [dim]Quit[/dim]",
        ]

        # Status / error line (single separator — no double blank line)
        if self._error:
            msg_line = f"\n[bold red]⚠  {self._error}[/bold red]"
        elif self._status:
            msg_line = f"\n[bold green]✓  {self._status}[/bold green]"
        else:
            msg_line = ""

        content = (
            f"{header}\n"
            f"{info}\n"
            f"[bold green]Slot {pos + 1}[/bold green] — {slot_label}\n"
            f"{bar}  {pos + 1}/{self.device.slot_num}\n"
            f"[bold underline]Filters:[/bold underline]\n"
            + "\n".join(filter_lines)
            + f"\n{'  |  '.join(cmd_parts)}"
            + msg_line
        )

        return Panel(content, box=ROUNDED, expand=False)

    # -- Input handling --

    def _handle_key(self, key: str) -> str:
        """Process a keypress. Returns 'quit' or 'continue'."""
        if key in ("q", "Q"):
            return "quit"

        if key in ("s", "S"):
            save_config(self.config)
            self._status = "Config saved."
            self._error = None
            return "continue"

        if key in ("r", "R"):
            self.config = load_config(self.device.slot_num)
            self._status = "Config reloaded."
            self._error = None
            return "continue"

        if key.isdigit() and len(key) == 1:
            slot = int(key)
            if 1 <= slot <= self.device.slot_num:
                try:
                    self.device.set_position(slot - 1)
                    self._current_slot = slot - 1
                    self._status = f"Moved to Slot {slot}."
                    self._error = None
                except EFWError as e:
                    self._error = str(e)
                    self._status = None
                return "continue"

        self._error = f"Unknown key: {key!r}"
        self._status = None
        return "continue"

    # -- Main loop --

    def run(self) -> None:
        """Run the interactive TUI."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        self.console.clear()
        self.console.print(self._render())

        while self._running:
            # Enter raw mode only for the duration of the keypress read,
            # so that Rich always renders in normal (cooked) terminal mode
            # and newlines include a carriage return.
            tty.setraw(fd)
            try:
                key = os.read(fd, 1).decode("utf-8", errors="replace")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            action = self._handle_key(key)
            if action == "quit":
                self._running = False
            else:
                self.console.clear()
                self.console.print(self._render())
