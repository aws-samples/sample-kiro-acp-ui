"""Dark mode detection and color palette management."""

import subprocess  # nosec B404 — required for macOS dark mode detection
import sys
from typing import TypedDict


class ColorPalette(TypedDict):
    bg: str
    fg: str
    input_bg: str
    input_fg: str
    user_label_fg: str
    assistant_label_fg: str
    error_fg: str
    typing_fg: str
    empty_state_fg: str
    code_block_bg: str
    inline_code_bg: str
    link_fg: str
    blockquote_fg: str
    hrule_fg: str


LIGHT_PALETTE: ColorPalette = {
    "bg": "#ffffff",
    "fg": "#1a1a1a",
    "input_bg": "#ffffff",
    "input_fg": "#1a1a1a",
    "user_label_fg": "#1a73e8",
    "assistant_label_fg": "#0d7377",
    "error_fg": "#d32f2f",
    "typing_fg": "#757575",
    "empty_state_fg": "#9e9e9e",
    "code_block_bg": "#f5f5f5",
    "inline_code_bg": "#f0f0f0",
    "link_fg": "#1a73e8",
    "blockquote_fg": "#555555",
    "hrule_fg": "#cccccc",
}

DARK_PALETTE: ColorPalette = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "input_bg": "#2d2d2d",
    "input_fg": "#d4d4d4",
    "user_label_fg": "#569cd6",
    "assistant_label_fg": "#4ec9b0",
    "error_fg": "#f48771",
    "typing_fg": "#808080",
    "empty_state_fg": "#6a6a6a",
    "code_block_bg": "#2d2d2d",
    "inline_code_bg": "#3c3c3c",
    "link_fg": "#569cd6",
    "blockquote_fg": "#9cdcfe",
    "hrule_fg": "#444444",
}


def detect_dark_mode() -> bool:
    """Detect macOS dark mode at startup."""
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(  # nosec B603 B607 — hardcoded command, no user input
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() == "Dark"
    except (subprocess.TimeoutExpired, OSError):
        return False


def get_palette() -> ColorPalette:
    """Return the appropriate color palette based on system appearance."""
    if detect_dark_mode():
        return DARK_PALETTE
    return LIGHT_PALETTE
