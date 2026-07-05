#!/usr/bin/env python3
"""
ZWO Filter Wheel Controller

A terminal UI for controlling ZWO electronic filter wheels.
Calibrates on startup and manages filter slot configuration via a JSON file.

Usage:
    python main.py
"""

import sys
import signal

from rich.console import Console

from efw_sdk import EFWDevice, EFWError
from efw_ui import EFWFilterWheelUI, load_config, prompt_filter_names, save_config


console = Console()


def main() -> None:
    # Graceful shutdown on Ctrl+C
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    # --- Discover devices ---
    console.print("[bold]ZWO Filter Wheel Controller[/bold]")

    device_ids = EFWDevice.discover()
    if not device_ids:
        console.print("[bold red]No EFW device found.[/bold red]")
        console.print("  Ensure the filter wheel is connected and powered.")
        sys.exit(1)

    console.print(f"  Found [bold]{len(device_ids)}[/bold] device(s).")
    for did in device_ids:
        console.print(f"    Device ID: {did}")

    device_id = device_ids[0]
    console.print(f"  Opening device {device_id} ...")

    device = EFWDevice()
    try:
        device.open(device_id)
    except EFWError as e:
        console.print(f"[bold red]Failed to open device: {e}[/bold red]")
        sys.exit(1)

    console.print(
        f"  Device: [bold cyan]{device.device_name}[/bold cyan]  "
        f"Slots: [bold]{device.slot_num}[/bold]  "
        f"Firmware: [dim]{device.firmware_version()}[/dim]"
    )

    # --- Load / prompt for filter config ---
    config = load_config(device.slot_num)

    missing = [s for s in range(1, device.slot_num + 1) if s not in config]
    if missing:
        console.print(f"[bold yellow]{len(missing)} slot(s) without filter names.[/bold yellow]")
        config = prompt_filter_names(device)
        save_config(config)

    # --- Run TUI ---
    console.print("[dim]Starting interactive mode. Press q to quit.[/dim]")

    try:
        ui = EFWFilterWheelUI(device, config)
        ui.run()
    finally:
        device.close()
        console.print("[dim]Device closed.[/dim]")


if __name__ == "__main__":
    main()
