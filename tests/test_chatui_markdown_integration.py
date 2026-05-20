"""Integration tests for ChatUI markdown rendering.

Validates that the ChatUI correctly integrates the markdown renderer for
assistant messages while leaving user messages and error messages unaffected.

Validates: Requirements 12.1, 12.2, 12.3, 12.4
"""

import contextlib
import tkinter as tk

import pytest

from kiro_acp_chat_client.ui import ChatUI


@pytest.fixture
def chat_ui():
    """Create a ChatUI instance for testing."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("tkinter display not available")
        return

    root.withdraw()

    ui = ChatUI(root, on_send=lambda t: None, on_close=lambda: None)
    yield ui, root

    with contextlib.suppress(tk.TclError):
        root.destroy()


class TestAssistantMessageFormattedOutput:
    """Test that append_assistant_message() produces formatted output with tags.

    Validates: Requirement 12.1
    """

    def test_bold_text_rendered_without_delimiters(self, chat_ui):
        """Bold markdown in assistant messages should render without ** delimiters."""
        ui, root = chat_ui
        ui.append_assistant_message("**bold** text")

        content = ui._message_display.get("1.0", tk.END)
        # The rendered text should contain "bold text" without **
        assert "bold" in content
        assert "text" in content
        assert "**bold**" not in content

    def test_bold_tag_applied(self, chat_ui):
        """The md_bold tag should be applied to bold text in assistant messages."""
        ui, root = chat_ui
        ui.append_assistant_message("**bold** text")

        # Find ranges where md_bold tag is applied
        bold_ranges = ui._message_display.tag_ranges("md_bold")
        assert len(bold_ranges) > 0, "md_bold tag should be applied to bold text"

        # Verify the tagged text is "bold"
        tagged_text = ui._message_display.get(str(bold_ranges[0]), str(bold_ranges[1]))
        assert tagged_text == "bold"

    def test_italic_text_rendered_without_delimiters(self, chat_ui):
        """Italic markdown in assistant messages should render without * delimiters."""
        ui, root = chat_ui
        ui.append_assistant_message("*italic* word")

        content = ui._message_display.get("1.0", tk.END)
        assert "italic" in content
        assert "word" in content
        # Should not contain the raw *italic* pattern
        # Check that the single asterisks around "italic" are gone
        # The content should have "italic" without surrounding *
        lines = content.split("\n")
        # Find the line with the message content (after "Kiro:")
        msg_content = " ".join(lines).replace("Kiro:", "").strip()
        assert "*italic*" not in msg_content


class TestUserMessagesUnaffected:
    """Test that user messages are not processed by markdown renderer.

    Validates: Requirement 12.1
    """

    def test_user_message_preserves_bold_syntax(self, chat_ui):
        """User messages should display **bold** verbatim without processing."""
        ui, root = chat_ui
        ui.append_user_message("**not bold**")

        content = ui._message_display.get("1.0", tk.END)
        assert "**not bold**" in content

    def test_user_message_no_bold_tag(self, chat_ui):
        """User messages should not have md_bold tag applied."""
        ui, root = chat_ui
        ui.append_user_message("**not bold**")

        bold_ranges = ui._message_display.tag_ranges("md_bold")
        assert len(bold_ranges) == 0, "md_bold tag should not be applied to user messages"

    def test_user_message_preserves_inline_code_syntax(self, chat_ui):
        """User messages should display `code` verbatim."""
        ui, root = chat_ui
        ui.append_user_message("`some code`")

        content = ui._message_display.get("1.0", tk.END)
        assert "`some code`" in content

    def test_user_message_no_inline_code_tag(self, chat_ui):
        """User messages should not have md_inline_code tag applied."""
        ui, root = chat_ui
        ui.append_user_message("`some code`")

        code_ranges = ui._message_display.tag_ranges("md_inline_code")
        assert len(code_ranges) == 0


class TestErrorMessagesUnaffected:
    """Test that error messages are not processed by markdown renderer.

    Validates: Requirement 12.1
    """

    def test_error_message_preserves_bold_syntax(self, chat_ui):
        """Error messages should display **bold** verbatim without processing."""
        ui, root = chat_ui
        ui.append_error("**not bold**")

        content = ui._message_display.get("1.0", tk.END)
        assert "**not bold**" in content

    def test_error_message_no_bold_tag(self, chat_ui):
        """Error messages should not have md_bold tag applied."""
        ui, root = chat_ui
        ui.append_error("**not bold**")

        bold_ranges = ui._message_display.tag_ranges("md_bold")
        assert len(bold_ranges) == 0, "md_bold tag should not be applied to error messages"

    def test_error_message_preserves_header_syntax(self, chat_ui):
        """Error messages should display # header verbatim."""
        ui, root = chat_ui
        ui.append_error("# not a header")

        content = ui._message_display.get("1.0", tk.END)
        # The error message includes the warning symbol prefix
        assert "# not a header" in content


class TestAutoScrollPreservation:
    """Test that auto-scroll behavior is preserved after markdown rendering.

    Validates: Requirement 12.2

    Note: In a withdrawn/headless tkinter window, yview() returns unreliable
    values. These tests verify the auto-scroll code path is exercised by
    checking that scroll_to_bottom() is called (via the see(END) mechanism)
    without errors when appending markdown-rendered messages.
    """

    def test_append_assistant_message_does_not_error(self, chat_ui):
        """Appending assistant messages with markdown should not raise errors."""
        ui, root = chat_ui

        # This exercises the full auto-scroll code path in append_assistant_message
        for i in range(10):
            ui.append_assistant_message(f"Message {i} with **bold** content")

        # If we get here without error, the scroll logic executed successfully
        content = ui._message_display.get("1.0", tk.END)
        assert "Message 9" in content

    def test_scroll_to_bottom_callable_after_markdown(self, chat_ui):
        """scroll_to_bottom() should work after markdown rendering."""
        ui, root = chat_ui

        ui.append_assistant_message("## Header\n\n- item 1\n- item 2\n\n**bold**")

        # Explicitly calling scroll_to_bottom should not raise
        ui.scroll_to_bottom()
        root.update_idletasks()

        # Verify content was rendered
        content = ui._message_display.get("1.0", tk.END)
        assert "Header" in content
        assert "item 1" in content


class TestKiroLabelPreservation:
    """Test that 'Kiro:' label is preserved before rendered content.

    Validates: Requirement 12.3
    """

    def test_kiro_label_present(self, chat_ui):
        """'Kiro:' should appear before the message content."""
        ui, root = chat_ui
        ui.append_assistant_message("hello")

        content = ui._message_display.get("1.0", tk.END)
        assert "Kiro:" in content

        # Verify "Kiro:" appears before "hello"
        kiro_pos = content.index("Kiro:")
        hello_pos = content.index("hello")
        assert kiro_pos < hello_pos

    def test_kiro_label_has_assistant_label_tag(self, chat_ui):
        """'Kiro:' should have the assistant_label tag applied."""
        ui, root = chat_ui
        ui.append_assistant_message("hello")

        # Check that assistant_label tag has ranges
        label_ranges = ui._message_display.tag_ranges("assistant_label")
        assert len(label_ranges) > 0, "assistant_label tag should be applied to 'Kiro:'"

        # Verify the tagged text contains "Kiro:"
        tagged_text = ui._message_display.get(str(label_ranges[0]), str(label_ranges[1]))
        assert "Kiro:" in tagged_text

    def test_kiro_label_with_markdown_content(self, chat_ui):
        """'Kiro:' label should be present even with complex markdown."""
        ui, root = chat_ui
        ui.append_assistant_message("## Header\n\n**bold** text")

        content = ui._message_display.get("1.0", tk.END)
        assert "Kiro:" in content

        # Label should still have its tag
        label_ranges = ui._message_display.tag_ranges("assistant_label")
        assert len(label_ranges) > 0


class TestPlainTextTransparency:
    """Test that plain text without markdown renders identically to plain insertion.

    Validates: Requirement 12.4
    """

    def test_plain_text_no_formatting_tags(self, chat_ui):
        """Plain text should not have any markdown formatting tags applied."""
        ui, root = chat_ui
        ui.append_assistant_message("plain text without any markdown")

        # Check that no markdown-specific tags are applied
        for tag in [
            "md_bold",
            "md_italic",
            "md_inline_code",
            "md_code_block",
            "md_h1",
            "md_h2",
            "md_h3",
            "md_blockquote",
            "md_link",
        ]:
            ranges = ui._message_display.tag_ranges(tag)
            assert len(ranges) == 0, f"Tag {tag} should not be applied to plain text"

    def test_plain_text_content_preserved(self, chat_ui):
        """Plain text content should appear exactly as provided."""
        ui, root = chat_ui
        ui.append_assistant_message("plain text")

        content = ui._message_display.get("1.0", tk.END)
        assert "plain text" in content

    def test_plain_text_has_assistant_msg_tag(self, chat_ui):
        """Plain text in assistant messages should have the assistant_msg base tag."""
        ui, root = chat_ui
        ui.append_assistant_message("plain text")

        # The assistant_msg tag should be applied to the message content
        msg_ranges = ui._message_display.tag_ranges("assistant_msg")
        assert len(msg_ranges) > 0, "assistant_msg tag should be applied to message content"
