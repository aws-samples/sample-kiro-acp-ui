"""Unit tests for dark mode palette application.

Validates Requirements 1.2, 1.3, 1.5:
- Dark palette colors are applied when detect_dark_mode() returns True
- Light palette colors are applied when detect_dark_mode() returns False
- Markdown renderer tag colors match the active palette
"""

import contextlib
import tkinter as tk
from unittest.mock import patch

import pytest

from kiro_acp_chat_client.markdown_renderer import setup_tags
from kiro_acp_chat_client.theme import DARK_PALETTE, LIGHT_PALETTE
from kiro_acp_chat_client.ui import ChatUI


@pytest.fixture
def root():
    """Create a tkinter root window for testing."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("tkinter display not available")
        return
    root.withdraw()
    yield root
    with contextlib.suppress(tk.TclError):
        root.destroy()


class TestDarkPaletteApplied:
    """Test that dark palette colors are applied when detect_dark_mode() returns True."""

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_message_display_uses_dark_bg(self, mock_get_palette, root):
        """Req 1.2: Dark background applied to message display widget."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        bg = ui._message_display.cget("background")
        assert bg == DARK_PALETTE["bg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_message_display_uses_dark_fg(self, mock_get_palette, root):
        """Req 1.2: Dark foreground applied to message display widget."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.cget("foreground")
        assert fg == DARK_PALETTE["fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_user_label_tag_uses_dark_color(self, mock_get_palette, root):
        """Req 1.2: User label tag uses dark palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("user_label", "foreground")
        assert fg == DARK_PALETTE["user_label_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_assistant_label_tag_uses_dark_color(self, mock_get_palette, root):
        """Req 1.2: Assistant label tag uses dark palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("assistant_label", "foreground")
        assert fg == DARK_PALETTE["assistant_label_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_error_tag_uses_dark_color(self, mock_get_palette, root):
        """Req 1.2: Error tag uses dark palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("error_msg", "foreground")
        assert fg == DARK_PALETTE["error_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=DARK_PALETTE)
    def test_typing_tag_uses_dark_color(self, mock_get_palette, root):
        """Req 1.2: Typing indicator tag uses dark palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("typing_indicator", "foreground")
        assert fg == DARK_PALETTE["typing_fg"]


class TestLightPaletteApplied:
    """Test that light palette colors are applied when detect_dark_mode() returns False."""

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_message_display_uses_light_bg(self, mock_get_palette, root):
        """Req 1.5: Light background applied to message display widget."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        bg = ui._message_display.cget("background")
        assert bg == LIGHT_PALETTE["bg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_message_display_uses_light_fg(self, mock_get_palette, root):
        """Req 1.5: Light foreground applied to message display widget."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.cget("foreground")
        assert fg == LIGHT_PALETTE["fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_user_label_tag_uses_light_color(self, mock_get_palette, root):
        """Req 1.5: User label tag uses light palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("user_label", "foreground")
        assert fg == LIGHT_PALETTE["user_label_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_assistant_label_tag_uses_light_color(self, mock_get_palette, root):
        """Req 1.5: Assistant label tag uses light palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("assistant_label", "foreground")
        assert fg == LIGHT_PALETTE["assistant_label_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_error_tag_uses_light_color(self, mock_get_palette, root):
        """Req 1.5: Error tag uses light palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("error_msg", "foreground")
        assert fg == LIGHT_PALETTE["error_fg"]

    @patch("kiro_acp_chat_client.ui.get_palette", return_value=LIGHT_PALETTE)
    def test_typing_tag_uses_light_color(self, mock_get_palette, root):
        """Req 1.5: Typing indicator tag uses light palette color."""
        ui = ChatUI(root, lambda t: None, lambda: None)
        fg = ui._message_display.tag_cget("typing_indicator", "foreground")
        assert fg == LIGHT_PALETTE["typing_fg"]


class TestMarkdownRendererDarkPalette:
    """Test that setup_tags() applies dark palette colors to markdown tags."""

    def test_code_block_bg_uses_dark_palette(self, root):
        """Req 1.3: Code block background matches dark palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=DARK_PALETTE)
        bg = text_widget.tag_cget("md_code_block", "background")
        assert bg == DARK_PALETTE["code_block_bg"]

    def test_inline_code_bg_uses_dark_palette(self, root):
        """Req 1.3: Inline code background matches dark palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=DARK_PALETTE)
        bg = text_widget.tag_cget("md_inline_code", "background")
        assert bg == DARK_PALETTE["inline_code_bg"]

    def test_link_fg_uses_dark_palette(self, root):
        """Req 1.3: Link foreground matches dark palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=DARK_PALETTE)
        fg = text_widget.tag_cget("md_link", "foreground")
        assert fg == DARK_PALETTE["link_fg"]

    def test_blockquote_fg_uses_dark_palette(self, root):
        """Req 1.3: Blockquote foreground matches dark palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=DARK_PALETTE)
        fg = text_widget.tag_cget("md_blockquote", "foreground")
        assert fg == DARK_PALETTE["blockquote_fg"]

    def test_hrule_fg_uses_dark_palette(self, root):
        """Req 1.3: Horizontal rule foreground matches dark palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=DARK_PALETTE)
        fg = text_widget.tag_cget("md_hrule", "foreground")
        assert fg == DARK_PALETTE["hrule_fg"]


class TestMarkdownRendererLightPalette:
    """Test that setup_tags() applies light palette colors to markdown tags."""

    def test_code_block_bg_uses_light_palette(self, root):
        """Req 1.3: Code block background matches light palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=LIGHT_PALETTE)
        bg = text_widget.tag_cget("md_code_block", "background")
        assert bg == LIGHT_PALETTE["code_block_bg"]

    def test_inline_code_bg_uses_light_palette(self, root):
        """Req 1.3: Inline code background matches light palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=LIGHT_PALETTE)
        bg = text_widget.tag_cget("md_inline_code", "background")
        assert bg == LIGHT_PALETTE["inline_code_bg"]

    def test_link_fg_uses_light_palette(self, root):
        """Req 1.3: Link foreground matches light palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=LIGHT_PALETTE)
        fg = text_widget.tag_cget("md_link", "foreground")
        assert fg == LIGHT_PALETTE["link_fg"]

    def test_blockquote_fg_uses_light_palette(self, root):
        """Req 1.3: Blockquote foreground matches light palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=LIGHT_PALETTE)
        fg = text_widget.tag_cget("md_blockquote", "foreground")
        assert fg == LIGHT_PALETTE["blockquote_fg"]

    def test_hrule_fg_uses_light_palette(self, root):
        """Req 1.3: Horizontal rule foreground matches light palette."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=LIGHT_PALETTE)
        fg = text_widget.tag_cget("md_hrule", "foreground")
        assert fg == LIGHT_PALETTE["hrule_fg"]


class TestMarkdownRendererNoPalette:
    """Test that setup_tags() uses default colors when no palette is provided."""

    def test_code_block_bg_uses_default(self, root):
        """Req 1.5: Without palette, code block uses default hardcoded color."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=None)
        bg = text_widget.tag_cget("md_code_block", "background")
        assert bg == "#f5f5f5"  # Default from MARKDOWN_TAGS

    def test_link_fg_uses_default(self, root):
        """Req 1.5: Without palette, link uses default hardcoded color."""
        text_widget = tk.Text(root)
        setup_tags(text_widget, palette=None)
        fg = text_widget.tag_cget("md_link", "foreground")
        assert fg == "#1a73e8"  # Default from MARKDOWN_TAGS
