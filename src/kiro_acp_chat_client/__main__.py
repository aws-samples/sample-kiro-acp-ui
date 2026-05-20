"""Entry point for the Kiro ACP Chat Client application."""

import argparse
import asyncio
import contextlib
import glob
import logging
import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path

from kiro_acp_chat_client import __version__
from kiro_acp_chat_client.acp_client import ACPClient
from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import PreferencesManager
from kiro_acp_chat_client.process_manager import ProcessManager
from kiro_acp_chat_client.ui import ChatUI

_MAX_LOG_FILES = 10


def _rotate_logs(log_dir: Path) -> None:
    """Delete oldest log files keeping only the 10 most recent."""
    pattern = str(log_dir / "kiro-acp-chat-*.log")
    log_files = sorted(glob.glob(pattern), reverse=True)  # newest first by filename
    for old_file in log_files[_MAX_LOG_FILES:]:
        with contextlib.suppress(OSError):
            Path(old_file).unlink()


# Application data directory: ~/.kiro-acp-chat/
# Uses the user's home directory so it works regardless of install method
# (uv tool install, pipx, pip install, or running from source).
_app_dir = Path.home() / ".kiro-acp-chat"
_log_dir = _app_dir / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / f"kiro-acp-chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
_preferences_file = _app_dir / "preferences.json"

_rotate_logs(_log_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    filename=str(_log_file),
    filemode="w",
)
# Also print the log file location to stderr so the user knows where to find it
print(f"Logging to: {_log_file}", file=sys.stderr)


async def run_app(cwd: str | None = None) -> None:
    """Run the application with asyncio driving the main loop.

    Creates all components, wires callbacks, and runs the asyncio
    event loop with periodic tkinter updates every 10ms.

    Args:
        cwd: Optional working directory for the ACP session. If provided,
             must be an existing directory. Defaults to os.getcwd().
    """
    # Validate cwd if provided
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.is_dir():
            print(f"Error: --cwd path does not exist: {cwd}", file=sys.stderr)
            sys.exit(1)
        effective_cwd = str(cwd_path.resolve())
    else:
        effective_cwd = os.getcwd()

    root = tk.Tk()

    # Create core components
    process_manager = ProcessManager()
    acp_client = ACPClient(process_manager)

    # Flag to signal the main loop to exit
    shutting_down = False

    def on_send(text: str) -> None:
        """Schedule controller.send_message() as an asyncio task."""
        asyncio.create_task(controller.send_message(text))

    def on_close() -> None:
        """Schedule shutdown and signal the main loop to exit."""
        nonlocal shutting_down
        shutting_down = True
        asyncio.create_task(controller.shutdown())

    def on_model_changed(model_id: str) -> None:
        """Schedule controller.on_model_changed() as an asyncio task."""
        asyncio.create_task(controller.on_model_changed(model_id))

    def on_mode_changed(mode_id: str) -> None:
        """Schedule controller.on_mode_changed() as an asyncio task."""
        asyncio.create_task(controller.on_mode_changed(mode_id))

    # Create UI and controller
    preferences_manager = PreferencesManager(str(_preferences_file))
    ui = ChatUI(root, on_send, on_close, on_model_changed, on_mode_changed)
    controller = ChatController(
        ui, acp_client, process_manager, preferences_manager, cwd=effective_cwd
    )

    # Schedule the controller startup (ACP init + session creation)
    asyncio.create_task(controller.start())

    # Main loop: pump tkinter events alongside asyncio
    while not shutting_down:
        try:
            root.update()
        except tk.TclError:
            # Window has been destroyed
            break
        await asyncio.sleep(0.01)  # 10ms tick


def main() -> None:
    """Entry point for the Kiro ACP Chat Client."""
    parser = argparse.ArgumentParser(prog="kiro-acp-chat")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"kiro-acp-chat {__version__}",
    )
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for ACP session")
    args = parser.parse_args()
    asyncio.run(run_app(cwd=args.cwd))


if __name__ == "__main__":
    main()
