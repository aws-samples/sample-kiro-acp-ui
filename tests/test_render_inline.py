"""Unit tests for the render_inline() function."""

import tkinter as tk

import pytest

from kiro_acp_chat_client.markdown_renderer import render_inline, setup_tags


def _make_widget():
    """Create a tk.Text widget for testing; skip if display unavailable."""
    try:
        root = tk.Tk()
        root.withdraw()
        text_widget = tk.Text(root)
        setup_tags(text_widget)
        return root, text_widget
    except tk.TclError:
        pytest.skip("Tkinter display not available")


def _get_text(widget):
    """Get all text content from widget (strip trailing newline)."""
    return widget.get("1.0", tk.END).rstrip("\n")


def _get_tags_at(widget, index):
    """Get tags applied at a specific index."""
    return widget.tag_names(index)


class TestRenderInlinePlainText:
    """Tests for plain text rendering (no markdown)."""

    def test_plain_text_inserted_with_base_tags(self):
        root, w = _make_widget()
        try:
            render_inline(w, "hello world", ("base_tag",))
            assert _get_text(w) == "hello world"
            tags = _get_tags_at(w, "1.0")
            assert "base_tag" in tags
        finally:
            root.destroy()

    def test_empty_text_inserts_nothing(self):
        root, w = _make_widget()
        try:
            render_inline(w, "", ("base_tag",))
            assert _get_text(w) == ""
        finally:
            root.destroy()

    def test_no_tags_tuple(self):
        root, w = _make_widget()
        try:
            render_inline(w, "plain", ())
            assert _get_text(w) == "plain"
        finally:
            root.destroy()


class TestRenderInlineBold:
    """Tests for bold formatting."""

    def test_bold_asterisk_removes_delimiters(self):
        root, w = _make_widget()
        try:
            render_inline(w, "**bold text**", ())
            assert _get_text(w) == "bold text"
        finally:
            root.destroy()

    def test_bold_asterisk_applies_tag(self):
        root, w = _make_widget()
        try:
            render_inline(w, "**bold**", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_bold" in tags
            assert "base" in tags
        finally:
            root.destroy()

    def test_bold_underscore_removes_delimiters(self):
        root, w = _make_widget()
        try:
            render_inline(w, "__bold text__", ())
            assert _get_text(w) == "bold text"
        finally:
            root.destroy()

    def test_bold_underscore_applies_tag(self):
        root, w = _make_widget()
        try:
            render_inline(w, "__bold__", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_bold" in tags
        finally:
            root.destroy()

    def test_unmatched_bold_displayed_verbatim(self):
        root, w = _make_widget()
        try:
            render_inline(w, "**unmatched", ())
            assert _get_text(w) == "**unmatched"
        finally:
            root.destroy()


class TestRenderInlineItalic:
    """Tests for italic formatting."""

    def test_italic_asterisk_removes_delimiters(self):
        root, w = _make_widget()
        try:
            render_inline(w, "*italic text*", ())
            assert _get_text(w) == "italic text"
        finally:
            root.destroy()

    def test_italic_asterisk_applies_tag(self):
        root, w = _make_widget()
        try:
            render_inline(w, "*italic*", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_italic" in tags
            assert "base" in tags
        finally:
            root.destroy()

    def test_italic_underscore_removes_delimiters(self):
        root, w = _make_widget()
        try:
            render_inline(w, "_italic text_", ())
            assert _get_text(w) == "italic text"
        finally:
            root.destroy()

    def test_unmatched_italic_displayed_verbatim(self):
        root, w = _make_widget()
        try:
            render_inline(w, "*unmatched", ())
            assert _get_text(w) == "*unmatched"
        finally:
            root.destroy()


class TestRenderInlineBoldItalic:
    """Tests for bold+italic formatting."""

    def test_bold_italic_removes_delimiters(self):
        root, w = _make_widget()
        try:
            render_inline(w, "***bold italic***", ())
            assert _get_text(w) == "bold italic"
        finally:
            root.destroy()

    def test_bold_italic_applies_both_tags(self):
        root, w = _make_widget()
        try:
            render_inline(w, "***text***", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_bold" in tags
            assert "md_italic" in tags
            assert "base" in tags
        finally:
            root.destroy()


class TestRenderInlineCode:
    """Tests for inline code formatting."""

    def test_inline_code_removes_backticks(self):
        root, w = _make_widget()
        try:
            render_inline(w, "`code here`", ())
            assert _get_text(w) == "code here"
        finally:
            root.destroy()

    def test_inline_code_applies_tag(self):
        root, w = _make_widget()
        try:
            render_inline(w, "`code`", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_inline_code" in tags
            assert "base" in tags
        finally:
            root.destroy()

    def test_inline_code_protects_content(self):
        """Content inside backticks should not be parsed for other formatting."""
        root, w = _make_widget()
        try:
            render_inline(w, "`**not bold**`", ())
            assert _get_text(w) == "**not bold**"
            tags = _get_tags_at(w, "1.0")
            assert "md_bold" not in tags
            assert "md_inline_code" in tags
        finally:
            root.destroy()

    def test_unmatched_backtick_displayed_verbatim(self):
        root, w = _make_widget()
        try:
            render_inline(w, "`unmatched", ())
            assert _get_text(w) == "`unmatched"
        finally:
            root.destroy()


class TestRenderInlineLinks:
    """Tests for link formatting."""

    def test_link_displays_text_only(self):
        root, w = _make_widget()
        try:
            render_inline(w, "[click here](https://example.com)", ())
            assert _get_text(w) == "click here"
        finally:
            root.destroy()

    def test_link_applies_tag(self):
        root, w = _make_widget()
        try:
            render_inline(w, "[link](https://example.com)", ("base",))
            tags = _get_tags_at(w, "1.0")
            assert "md_link" in tags
            assert "base" in tags
        finally:
            root.destroy()


class TestRenderInlineMixed:
    """Tests for mixed inline formatting."""

    def test_text_with_bold_in_middle(self):
        root, w = _make_widget()
        try:
            render_inline(w, "hello **world** end", ())
            assert _get_text(w) == "hello world end"
        finally:
            root.destroy()

    def test_multiple_formats_in_one_line(self):
        root, w = _make_widget()
        try:
            render_inline(w, "**bold** and *italic*", ())
            assert _get_text(w) == "bold and italic"
        finally:
            root.destroy()

    def test_code_and_bold_together(self):
        root, w = _make_widget()
        try:
            render_inline(w, "`code` and **bold**", ())
            assert _get_text(w) == "code and bold"
        finally:
            root.destroy()

    def test_link_with_surrounding_text(self):
        root, w = _make_widget()
        try:
            render_inline(w, "see [docs](http://x.com) for info", ())
            assert _get_text(w) == "see docs for info"
        finally:
            root.destroy()
