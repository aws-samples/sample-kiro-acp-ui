"""Unit tests for the ChatUI class."""

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

    root.withdraw()  # Hide window during tests

    send_calls = []
    close_calls = []

    def on_send(text):
        send_calls.append(text)

    def on_close():
        close_calls.append(True)

    ui = ChatUI(root, on_send, on_close)
    yield ui, root, send_calls, close_calls

    with contextlib.suppress(tk.TclError):
        root.destroy()


class TestChatUIWindowSetup:
    """Tests for window configuration."""

    def test_window_title(self, chat_ui):
        ui, root, _, _ = chat_ui
        assert root.title() == "Kiro ACP Chat"

    def test_window_default_size(self, chat_ui):
        ui, root, _, _ = chat_ui
        # When window is withdrawn, geometry() may not reflect the requested size.
        # Instead verify the geometry was requested correctly by checking the
        # geometry string that was set (before window manager adjusts it).
        # We deiconify briefly to get the actual geometry.
        root.deiconify()
        root.update_idletasks()
        geo = root.geometry()
        root.withdraw()
        # geometry format is "WxH+X+Y"
        size_part = geo.split("+")[0]
        width, height = size_part.split("x")
        assert int(width) == 800
        assert int(height) == 600

    def test_window_minimum_size(self, chat_ui):
        ui, root, _, _ = chat_ui
        min_width = root.minsize()[0]
        min_height = root.minsize()[1]
        assert min_width == 400
        assert min_height == 300


class TestChatUIEmptyState:
    """Tests for empty state placeholder."""

    def test_shows_empty_state_on_init(self, chat_ui):
        ui, root, _, _ = chat_ui
        content = ui._message_display.get("1.0", tk.END)
        assert "Connecting to Kiro" in content

    def test_empty_state_removed_on_first_message(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.append_user_message("Hello")
        content = ui._message_display.get("1.0", tk.END)
        assert "Connecting to Kiro" not in content
        assert "Hello" in content


class TestChatUIMessages:
    """Tests for message display."""

    def test_append_user_message(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.append_user_message("Hello world")
        content = ui._message_display.get("1.0", tk.END)
        assert "You:" in content
        assert "Hello world" in content

    def test_append_assistant_message(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.append_assistant_message("Hi there!")
        content = ui._message_display.get("1.0", tk.END)
        assert "Kiro:" in content
        assert "Hi there!" in content

    def test_append_error(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.append_error("Something went wrong")
        content = ui._message_display.get("1.0", tk.END)
        assert "Something went wrong" in content

    def test_messages_in_chronological_order(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.append_user_message("First")
        ui.append_assistant_message("Second")
        ui.append_user_message("Third")
        content = ui._message_display.get("1.0", tk.END)
        pos_first = content.index("First")
        pos_second = content.index("Second")
        pos_third = content.index("Third")
        assert pos_first < pos_second < pos_third


class TestChatUITypingIndicator:
    """Tests for typing indicator."""

    def test_show_typing_indicator(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.show_typing_indicator()
        content = ui._message_display.get("1.0", tk.END)
        assert "Kiro is typing..." in content

    def test_hide_typing_indicator(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.show_typing_indicator()
        ui.hide_typing_indicator()
        content = ui._message_display.get("1.0", tk.END)
        assert "Kiro is typing..." not in content

    def test_show_typing_indicator_idempotent(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.show_typing_indicator()
        ui.show_typing_indicator()
        content = ui._message_display.get("1.0", tk.END)
        # Should only appear once
        assert content.count("Kiro is typing...") == 1

    def test_hide_typing_indicator_when_not_shown(self, chat_ui):
        ui, root, _, _ = chat_ui
        # Should not raise
        ui.hide_typing_indicator()


class TestChatUIInput:
    """Tests for input field operations."""

    def test_get_input_text(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui._input_field.insert(0, "test message")
        assert ui.get_input_text() == "test message"

    def test_clear_input(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui._input_field.insert(0, "test message")
        ui.clear_input()
        assert ui.get_input_text() == ""

    def test_set_input_enabled_false(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.set_input_enabled(False)
        state = str(ui._input_field.cget("state"))
        assert state == "disabled"

    def test_set_input_enabled_true(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.set_input_enabled(False)
        ui.set_input_enabled(True)
        state = str(ui._input_field.cget("state"))
        assert state == "normal"

    def test_send_button_disabled_when_input_empty(self, chat_ui):
        ui, root, _, _ = chat_ui
        # Initially empty, button should be disabled
        assert "disabled" in ui._send_button.state()

    def test_send_button_enabled_when_input_has_text(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui._input_field.insert(0, "hello")
        ui._on_input_changed()
        assert "disabled" not in ui._send_button.state()

    def test_send_button_disabled_for_whitespace_only(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui._input_field.insert(0, "   ")
        ui._on_input_changed()
        assert "disabled" in ui._send_button.state()


class TestChatUICallbacks:
    """Tests for send and close callbacks."""

    def test_send_callback_on_button_click(self, chat_ui):
        ui, root, send_calls, _ = chat_ui
        ui._input_field.insert(0, "hello")
        ui._handle_send()
        assert send_calls == ["hello"]

    def test_send_callback_strips_whitespace(self, chat_ui):
        ui, root, send_calls, _ = chat_ui
        ui._input_field.insert(0, "  hello  ")
        ui._handle_send()
        assert send_calls == ["hello"]

    def test_send_not_called_for_empty_input(self, chat_ui):
        ui, root, send_calls, _ = chat_ui
        ui._handle_send()
        assert send_calls == []

    def test_send_not_called_for_whitespace_only(self, chat_ui):
        ui, root, send_calls, _ = chat_ui
        ui._input_field.insert(0, "   ")
        ui._handle_send()
        assert send_calls == []

    def test_close_callback(self, chat_ui):
        ui, root, _, close_calls = chat_ui
        ui._handle_close()
        assert close_calls == [True]


class TestChatUIScroll:
    """Tests for scroll behavior."""

    def test_scroll_to_bottom(self, chat_ui):
        ui, root, _, _ = chat_ui
        # Add many messages to create scrollable content
        for i in range(50):
            ui.append_user_message(f"Message {i}")
        root.update_idletasks()
        ui.scroll_to_bottom()
        root.update_idletasks()
        # After scrolling to bottom, the view should show the end
        yview = ui._message_display.yview()
        assert yview[1] >= 0.99 or yview == (0.0, 0.0)

    def test_auto_scroll_on_new_message(self, chat_ui):
        ui, root, _, _ = chat_ui
        # Add messages - should auto-scroll since we start at bottom
        ui.append_user_message("First message")
        ui.append_assistant_message("Response")
        # Verify messages are present
        content = ui._message_display.get("1.0", tk.END)
        assert "First message" in content
        assert "Response" in content


class TestChatUIToolbarPopulate:
    """Tests for model and mode selector population."""

    def test_populate_models_prepends_auto(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [
            {"modelId": "model-1", "name": "Model One"},
            {"modelId": "model-2", "name": "Model Two"},
        ]
        ui.populate_models(models)
        assert ui._model_options[0] == {"modelId": "auto", "name": "auto"}
        assert len(ui._model_options) == 3

    def test_populate_models_sets_combobox_values(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [
            {"modelId": "model-1", "name": "Model One"},
            {"modelId": "model-2", "name": "Model Two"},
        ]
        ui.populate_models(models)
        values = list(ui._model_combobox["values"])
        assert values == ["auto", "Model One", "Model Two"]

    def test_populate_models_selects_first(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [{"modelId": "model-1", "name": "Model One"}]
        ui.populate_models(models)
        assert ui._model_combobox.current() == 0

    def test_populate_modes_sets_combobox_values(self, chat_ui):
        ui, root, _, _ = chat_ui
        modes = [
            {"id": "dev", "name": "Developer"},
            {"id": "default", "name": "Default"},
        ]
        ui.populate_modes(modes)
        values = list(ui._mode_combobox["values"])
        assert values == ["Developer", "Default"]

    def test_populate_modes_selects_first(self, chat_ui):
        ui, root, _, _ = chat_ui
        modes = [{"id": "dev", "name": "Developer"}]
        ui.populate_modes(modes)
        assert ui._mode_combobox.current() == 0

    def test_populate_modes_empty_list(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.populate_modes([])
        assert ui._mode_options == []
        values = list(ui._mode_combobox["values"])
        assert values == []


class TestChatUIToolbarSelection:
    """Tests for model and mode selector get/set."""

    def test_set_selected_model(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [
            {"modelId": "model-1", "name": "Model One"},
            {"modelId": "model-2", "name": "Model Two"},
        ]
        ui.populate_models(models)
        ui.set_selected_model("model-2")
        assert ui._model_combobox.current() == 2  # index 2 (auto=0, model-1=1, model-2=2)

    def test_set_selected_model_not_found(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [{"modelId": "model-1", "name": "Model One"}]
        ui.populate_models(models)
        ui.set_selected_model("nonexistent")
        # Should remain at first (auto)
        assert ui._model_combobox.current() == 0

    def test_set_selected_mode(self, chat_ui):
        ui, root, _, _ = chat_ui
        modes = [
            {"id": "dev", "name": "Developer"},
            {"id": "default", "name": "Default"},
        ]
        ui.populate_modes(modes)
        ui.set_selected_mode("default")
        assert ui._mode_combobox.current() == 1

    def test_set_selected_mode_not_found(self, chat_ui):
        ui, root, _, _ = chat_ui
        modes = [{"id": "dev", "name": "Developer"}]
        ui.populate_modes(modes)
        ui.set_selected_mode("nonexistent")
        # Should remain at first
        assert ui._mode_combobox.current() == 0

    def test_get_selected_model_id(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [
            {"modelId": "model-1", "name": "Model One"},
            {"modelId": "model-2", "name": "Model Two"},
        ]
        ui.populate_models(models)
        ui.set_selected_model("model-1")
        assert ui.get_selected_model_id() == "model-1"

    def test_get_selected_model_id_auto(self, chat_ui):
        ui, root, _, _ = chat_ui
        models = [{"modelId": "model-1", "name": "Model One"}]
        ui.populate_models(models)
        assert ui.get_selected_model_id() == "auto"

    def test_get_selected_model_id_no_options(self, chat_ui):
        ui, root, _, _ = chat_ui
        assert ui.get_selected_model_id() == "auto"

    def test_get_selected_mode_id(self, chat_ui):
        ui, root, _, _ = chat_ui
        modes = [
            {"id": "dev", "name": "Developer"},
            {"id": "default", "name": "Default"},
        ]
        ui.populate_modes(modes)
        ui.set_selected_mode("default")
        assert ui.get_selected_mode_id() == "default"

    def test_get_selected_mode_id_no_options(self, chat_ui):
        ui, root, _, _ = chat_ui
        assert ui.get_selected_mode_id() == ""


class TestChatUIToolbarEnabled:
    """Tests for selector enable/disable."""

    def test_set_selectors_enabled_true(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.set_selectors_enabled(True)
        assert str(ui._model_combobox.cget("state")) == "readonly"
        assert str(ui._mode_combobox.cget("state")) == "readonly"

    def test_set_selectors_enabled_false(self, chat_ui):
        ui, root, _, _ = chat_ui
        ui.set_selectors_enabled(False)
        assert str(ui._model_combobox.cget("state")) == "disabled"
        assert str(ui._mode_combobox.cget("state")) == "disabled"

    def test_selectors_start_disabled(self, chat_ui):
        ui, root, _, _ = chat_ui
        assert str(ui._model_combobox.cget("state")) == "disabled"
        assert str(ui._mode_combobox.cget("state")) == "disabled"


class TestChatUIToolbarCallbacks:
    """Tests for model/mode selection callbacks."""

    def test_on_model_selected_calls_callback(self):
        """Test that selecting a model triggers the callback."""
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("tkinter display not available")
            return

        root.withdraw()
        model_calls = []

        def on_model_changed(model_id):
            model_calls.append(model_id)

        ui = ChatUI(root, lambda t: None, lambda: None, on_model_changed=on_model_changed)
        models = [{"modelId": "model-1", "name": "Model One"}]
        ui.populate_models(models)
        ui.set_selectors_enabled(True)

        # Simulate selecting model-1
        ui._model_combobox.current(1)
        ui._on_model_selected()

        assert model_calls == ["model-1"]

        with contextlib.suppress(tk.TclError):
            root.destroy()

    def test_on_mode_selected_calls_callback(self):
        """Test that selecting a mode triggers the callback."""
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("tkinter display not available")
            return

        root.withdraw()
        mode_calls = []

        def on_mode_changed(mode_id):
            mode_calls.append(mode_id)

        ui = ChatUI(root, lambda t: None, lambda: None, on_mode_changed=on_mode_changed)
        modes = [
            {"id": "dev", "name": "Developer"},
            {"id": "default", "name": "Default"},
        ]
        ui.populate_modes(modes)
        ui.set_selectors_enabled(True)

        # Simulate selecting "Default"
        ui._mode_combobox.current(1)
        ui._on_mode_selected()

        assert mode_calls == ["default"]

        with contextlib.suppress(tk.TclError):
            root.destroy()

    def test_no_callback_when_none(self, chat_ui):
        """Test that no error occurs when callbacks are None."""
        ui, root, _, _ = chat_ui
        models = [{"modelId": "model-1", "name": "Model One"}]
        ui.populate_models(models)
        # Should not raise even though on_model_changed is None
        ui._on_model_selected()
        ui._on_mode_selected()
