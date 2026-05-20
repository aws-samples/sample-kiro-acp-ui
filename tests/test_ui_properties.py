"""Property-based tests for the ChatUI class.

# Feature: kiro-acp-chat-client, Property 2: Whitespace-only input rejection
# Feature: kiro-acp-chat-client, Property 7: Messages maintain chronological order
# Feature: model-agent-preferences, Property 2: Dropdown displays name field as label
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

    send_calls = []

    def on_send(text):
        send_calls.append(text)

    def on_close():
        pass

    ui = ChatUI(root, on_send, on_close)
    return ui, root, send_calls


def _destroy_chat_ui(root):
    """Safely destroy the tkinter root window."""
    with contextlib.suppress(tk.TclError):
        root.destroy()


# Strategy for generating whitespace-only strings (spaces, tabs, newlines, empty)
whitespace_only_strings = st.text(
    alphabet=st.sampled_from([" ", "\t", "\n", "\r", "\x0b", "\x0c"]),
    min_size=0,
    max_size=100,
)


# **Validates: Requirements 2.5**
@settings(max_examples=200, deadline=None)
@given(whitespace_input=whitespace_only_strings)
def test_whitespace_only_input_rejected(whitespace_input):
    """Property 2: Whitespace-only input rejection.

    For any string composed entirely of whitespace characters (spaces, tabs,
    newlines, or the empty string), the send validation SHALL reject the input,
    the send button SHALL remain disabled, and the conversation state SHALL
    remain unchanged.

    # Feature: kiro-acp-chat-client, Property 2: Whitespace-only input rejection
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root, send_calls = result

    try:
        # Clear any existing input
        ui._input_field.delete(0, tk.END)

        # Insert the whitespace-only string
        ui._input_field.insert(0, whitespace_input)

        # Trigger input change validation
        ui._on_input_changed()

        # Assert: send button remains disabled
        assert "disabled" in ui._send_button.state(), (
            f"Send button should be disabled for whitespace-only input: {repr(whitespace_input)}"
        )

        # Assert: attempting to send does nothing (callback not invoked)
        ui._handle_send()
        assert len(send_calls) == 0, (
            "Send callback should not be invoked for whitespace-only input:"
            f" {repr(whitespace_input)}"
        )
    finally:
        _destroy_chat_ui(root)


# Strategy for generating non-empty message text
message_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
)

# Strategy for generating non-empty message text that avoids markdown syntax
# characters, so assistant messages rendered via markdown won't transform the text.
assistant_message_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z"),
        blacklist_characters="\x00#*_`>|~[]()!-+",
    ),
    min_size=1,
    max_size=100,
).filter(lambda t: t.strip() != "")

# Strategy for generating a sequence of messages with roles
# Each message is a tuple of (role, text) where role is "user" or "assistant"
message_sequence = st.lists(
    st.tuples(
        st.sampled_from(["user", "assistant"]),
        message_text,
    ),
    min_size=1,
    max_size=20,
)

# Strategy for generating a sequence of messages with roles, using plain text
# for assistant messages to avoid markdown rendering transformations.
message_sequence_plain = st.lists(
    st.one_of(
        st.tuples(st.just("user"), message_text),
        st.tuples(st.just("assistant"), assistant_message_text),
    ),
    min_size=1,
    max_size=20,
)


# **Validates: Requirements 5.1**
@settings(max_examples=100, deadline=None)
@given(messages=message_sequence_plain)
def test_messages_maintain_chronological_order(messages):
    """Property 7: Messages maintain chronological order.

    For any sequence of messages added to the conversation (user messages
    and assistant responses), the message display renders them in the exact
    order they were added, preserving chronological ordering.

    # Feature: kiro-acp-chat-client, Property 7: Messages maintain chronological order
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root, _ = result

    try:
        # Add messages in sequence
        for role, text in messages:
            if role == "user":
                ui.append_user_message(text)
            else:
                ui.append_assistant_message(text)

        # Get the full display content
        content = ui._message_display.get("1.0", tk.END)

        # Verify each message appears in the content and in chronological order
        last_pos = -1
        for role, text in messages:
            # Assistant messages go through markdown rendering which strips
            # trailing whitespace from paragraph content
            search_text = text.strip() if role == "assistant" else text
            pos = content.find(search_text, last_pos + 1)
            assert pos > last_pos, (
                f"Message '{text}' (role={role}) not found after position {last_pos} "
                f"in display content"
            )
            last_pos = pos
    finally:
        _destroy_chat_ui(root)


# --- Property 2: Dropdown displays name field as label ---
# Feature: model-agent-preferences, Property 2: Dropdown displays name field as label

# Strategy for generating model dicts with modelId and name keys
model_dicts = st.lists(
    st.fixed_dictionaries(
        {
            "modelId": st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P"), blacklist_characters="\x00"
                ),
                min_size=1,
                max_size=50,
            ),
            "name": st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"
                ),
                min_size=1,
                max_size=50,
            ),
        }
    ),
    min_size=0,
    max_size=10,
)

# Strategy for generating mode dicts with id and name keys
mode_dicts = st.lists(
    st.fixed_dictionaries(
        {
            "id": st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P"), blacklist_characters="\x00"
                ),
                min_size=1,
                max_size=50,
            ),
            "name": st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"
                ),
                min_size=1,
                max_size=50,
            ),
        }
    ),
    min_size=0,
    max_size=10,
)


# **Validates: Requirements 1.4, 2.4**
@settings(max_examples=100, deadline=None)
@given(models=model_dicts)
def test_populate_models_displays_name_as_label(models):
    """Property 2: Dropdown displays name field as label (models).

    For any list of model objects (each with modelId and name fields),
    after populating the model dropdown, the visible labels in the dropdown
    SHALL exactly match ["auto"] + [m["name"] for m in models] in order.

    # Feature: model-agent-preferences, Property 2: Dropdown displays name field as label
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root, _ = result

    try:
        ui.populate_models(models)

        # Get the combobox values (visible labels)
        combobox_values = list(ui._model_combobox["values"])

        # Expected: "auto" prepended, then each model's name field in order
        expected = ["auto"] + [m["name"] for m in models]

        assert combobox_values == expected, (
            f"Model combobox values mismatch.\nExpected: {expected}\nGot: {combobox_values}"
        )
    finally:
        _destroy_chat_ui(root)


# **Validates: Requirements 1.4, 2.4**
@settings(max_examples=100, deadline=None)
@given(modes=mode_dicts)
def test_populate_modes_displays_name_as_label(modes):
    """Property 2: Dropdown displays name field as label (modes).

    For any list of mode objects (each with id and name fields),
    after populating the mode dropdown, the visible labels in the dropdown
    SHALL exactly match [m["name"] for m in modes] in order.

    # Feature: model-agent-preferences, Property 2: Dropdown displays name field as label
    """
    result = _create_chat_ui()
    if result is None:
        pytest.skip("tkinter display not available")

    ui, root, _ = result

    try:
        ui.populate_modes(modes)

        # Get the combobox values (visible labels)
        combobox_values = list(ui._mode_combobox["values"])

        # Expected: each mode's name field in order (no "auto" prepended for modes)
        expected = [m["name"] for m in modes]

        assert combobox_values == expected, (
            f"Mode combobox values mismatch.\nExpected: {expected}\nGot: {combobox_values}"
        )
    finally:
        _destroy_chat_ui(root)
