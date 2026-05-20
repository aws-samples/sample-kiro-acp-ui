"""Property-based tests for agent name propagation.

**Property 3: Agent display name reflects current mode selection**

For any mode change to a mode with name N, the assistant message label and
typing indicator SHALL use the name N for all subsequent messages until the
next mode change.

**Validates: Requirements 4.2, 4.3**
"""

import contextlib
import tkinter as tk

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.ui import ChatUI


def _create_chat_ui():
    """Create a ChatUI instance for testing. Returns None if tkinter unavailable."""
    try:
        root = tk.Tk()
    except tk.TclError:
        return None

    root.withdraw()

    def on_send(text):
        pass

    def on_close():
        pass

    ui = ChatUI(root, on_send, on_close)
    return ui, root


def _destroy_chat_ui(root):
    """Safely destroy the tkinter root window."""
    with contextlib.suppress(tk.TclError):
        root.destroy()


# Strategy for generating agent display names — printable non-empty strings
# avoiding markdown-special characters so rendered text is predictable
agent_names = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z"),
        blacklist_characters="\x00\n\r",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# Strategy for generating sequences of mode changes (list of agent names)
name_sequences = st.lists(agent_names, min_size=1, max_size=10)


# **Validates: Requirements 4.2, 4.3**
@settings(max_examples=100, deadline=None)
@given(name=agent_names)
def test_set_agent_name_used_in_assistant_message(name):
    """Property 3: set_agent_name propagates to append_assistant_message.

    When set_agent_name(name) is called, subsequent calls to
    append_assistant_message() use that name as the label.

    **Validates: Requirements 4.2, 4.3**
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root = result

    try:
        ui.set_agent_name(name)
        ui.append_assistant_message("Hello")

        content = ui._message_display.get("1.0", tk.END)
        assert f"{name}:" in content, (
            f"Expected agent name '{name}:' in message display, got: {content!r}"
        )
    finally:
        _destroy_chat_ui(root)


# **Validates: Requirements 4.2, 4.3**
@settings(max_examples=100, deadline=None)
@given(name=agent_names)
def test_set_agent_name_used_in_typing_indicator(name):
    """Property 3: set_agent_name propagates to show_typing_indicator.

    When set_agent_name(name) is called, subsequent calls to
    show_typing_indicator() use that name in the typing text.

    **Validates: Requirements 4.2, 4.3**
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root = result

    try:
        ui.set_agent_name(name)
        ui.show_typing_indicator()

        content = ui._message_display.get("1.0", tk.END)
        expected_typing = f"{name} is typing..."
        assert expected_typing in content, (
            f"Expected typing indicator '{expected_typing}' in display, got: {content!r}"
        )
    finally:
        _destroy_chat_ui(root)


# **Validates: Requirements 4.2, 4.3**
@settings(max_examples=100, deadline=None)
@given(name=agent_names, num_messages=st.integers(min_value=1, max_value=5))
def test_agent_name_persists_across_multiple_messages(name, num_messages):
    """Property 3: Agent name persists until next set_agent_name call.

    After set_agent_name(name) is called, all subsequent assistant messages
    use that name until set_agent_name is called again.

    **Validates: Requirements 4.2, 4.3**
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root = result

    try:
        ui.set_agent_name(name)

        for _ in range(num_messages):
            ui.append_assistant_message("test message")

        content = ui._message_display.get("1.0", tk.END)
        # The name should appear once per message as a label
        occurrences = content.count(f"{name}:")
        assert occurrences == num_messages, (
            f"Expected '{name}:' to appear {num_messages} times, "
            f"but found {occurrences} in: {content!r}"
        )
    finally:
        _destroy_chat_ui(root)


# **Validates: Requirements 4.2, 4.3**
@settings(max_examples=100, deadline=None)
@given(names=name_sequences)
def test_last_set_name_used_after_sequence_of_changes(names):
    """Property 3: For any sequence of mode changes, the last set name is used.

    After a sequence of set_agent_name() calls, only the most recently set
    name is used for subsequent assistant messages and typing indicators.

    **Validates: Requirements 4.2, 4.3**
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root = result

    try:
        # Apply a sequence of name changes
        for name in names:
            ui.set_agent_name(name)

        last_name = names[-1]

        # Clear display to isolate the test
        ui._message_display.configure(state=tk.NORMAL)
        ui._message_display.delete("1.0", tk.END)
        ui._message_display.configure(state=tk.DISABLED)
        ui._has_messages = False
        ui._typing_visible = False

        # Append a message — should use the last name
        ui.append_assistant_message("test")
        content = ui._message_display.get("1.0", tk.END)
        assert f"{last_name}:" in content, (
            f"Expected last agent name '{last_name}:' in display after "
            f"sequence of {len(names)} changes, got: {content!r}"
        )

        # Show typing indicator — should also use the last name
        ui.show_typing_indicator()
        content = ui._message_display.get("1.0", tk.END)
        expected_typing = f"{last_name} is typing..."
        assert expected_typing in content, (
            f"Expected typing indicator '{expected_typing}' in display, got: {content!r}"
        )
    finally:
        _destroy_chat_ui(root)
