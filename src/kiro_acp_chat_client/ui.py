"""Tkinter-based chat user interface for the Kiro ACP Chat Client."""

import contextlib
import subprocess  # nosec B404 — required for macOS system integration (notifications, sounds)
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from kiro_acp_chat_client.markdown_renderer import render_markdown, setup_tags
from kiro_acp_chat_client.theme import ColorPalette, get_palette


class ChatUI:
    """Tkinter-based chat user interface.

    Provides a scrollable message display area, an input field, and a send button.
    Messages are styled differently for user, assistant, and error messages.
    """

    # Tag names for styling
    _TAG_USER_LABEL = "user_label"
    _TAG_USER_MSG = "user_msg"
    _TAG_ASSISTANT_LABEL = "assistant_label"
    _TAG_ASSISTANT_MSG = "assistant_msg"
    _TAG_ERROR = "error_msg"
    _TAG_TYPING = "typing_indicator"
    _TAG_EMPTY_STATE = "empty_state"

    def __init__(
        self,
        root: tk.Tk,
        on_send: Callable[[str], None],
        on_close: Callable[[], None],
        on_model_changed: Callable[[str], None] | None = None,
        on_mode_changed: Callable[[str], None] | None = None,
    ):
        """Initialize the chat UI.

        Args:
            root: The tkinter root window.
            on_send: Callback invoked with message text when user sends a message.
            on_close: Callback invoked when the window is closed.
            on_model_changed: Callback invoked with model_id when user changes model selection.
            on_mode_changed: Callback invoked with mode_id when user changes mode selection.
        """
        self._root = root
        self._on_send = on_send
        self._on_close = on_close
        self._on_model_changed = on_model_changed
        self._on_mode_changed = on_mode_changed
        self._has_messages = False
        self._typing_visible = False
        self._agent_display_name: str = "Kiro"
        self._palette: ColorPalette = get_palette()

        # Internal mapping from combobox index to model/mode dicts
        self._model_options: list[dict] = []
        self._mode_options: list[dict] = []

        self._setup_window()
        self._setup_widgets()
        self._setup_tags()
        setup_tags(self._message_display, palette=self._palette)
        self._setup_bindings()
        self.show_initializing()

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self._root.title("Kiro ACP Chat")
        self._root.geometry("800x600")
        self._root.minsize(400, 300)
        self._root.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _setup_widgets(self) -> None:
        """Create and layout all UI widgets."""
        # Main container
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=0)  # Toolbar fixed height
        self._root.rowconfigure(1, weight=7)  # Message display gets >=70%
        self._root.rowconfigure(2, weight=0)  # Input area fixed height

        # Toolbar frame (row 0)
        toolbar_frame = ttk.Frame(self._root)
        toolbar_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        model_label = ttk.Label(toolbar_frame, text="Model:")
        model_label.pack(side=tk.LEFT, padx=(0, 4))

        self._model_combobox = ttk.Combobox(toolbar_frame, state="disabled", width=20)
        self._model_combobox.pack(side=tk.LEFT, padx=(0, 12))

        mode_label = ttk.Label(toolbar_frame, text="Agent:")
        mode_label.pack(side=tk.LEFT, padx=(0, 4))

        self._mode_combobox = ttk.Combobox(toolbar_frame, state="disabled", width=20)
        self._mode_combobox.pack(side=tk.LEFT, padx=(0, 4))

        # Message display frame with scrollbar (row 1)
        display_frame = ttk.Frame(self._root)
        display_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(5, 2))
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        self._message_display = tk.Text(
            display_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            cursor="arrow",
            padx=10,
            pady=10,
            font=("TkDefaultFont", 10),
            spacing3=4,
            background=self._palette["bg"],
            foreground=self._palette["fg"],
        )
        self._message_display.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            display_frame, orient=tk.VERTICAL, command=self._message_display.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._message_display.configure(yscrollcommand=scrollbar.set)

        # Input area frame (row 2)
        input_frame = ttk.Frame(self._root)
        input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(2, 5))
        input_frame.columnconfigure(0, weight=1)

        self._input_field = ttk.Entry(input_frame, font=("TkDefaultFont", 10))
        self._input_field.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self._send_button = ttk.Button(input_frame, text="Send", command=self._handle_send)
        self._send_button.grid(row=0, column=1)

        # Start with send button disabled (empty input)
        self._send_button.state(["disabled"])

    def _setup_tags(self) -> None:
        """Configure text tags for message styling."""
        self._message_display.tag_configure(
            self._TAG_USER_LABEL,
            foreground=self._palette["user_label_fg"],
            font=("TkDefaultFont", 10, "bold"),
            justify=tk.RIGHT,
        )
        self._message_display.tag_configure(
            self._TAG_USER_MSG,
            foreground=self._palette["fg"],
            lmargin1=40,
            lmargin2=40,
        )
        self._message_display.tag_configure(
            self._TAG_ASSISTANT_LABEL,
            foreground=self._palette["assistant_label_fg"],
            font=("TkDefaultFont", 10, "bold"),
            justify=tk.LEFT,
        )
        self._message_display.tag_configure(
            self._TAG_ASSISTANT_MSG,
            foreground=self._palette["fg"],
            rmargin=40,
        )
        self._message_display.tag_configure(
            self._TAG_ERROR,
            foreground=self._palette["error_fg"],
            font=("TkDefaultFont", 10, "italic"),
        )
        self._message_display.tag_configure(
            self._TAG_TYPING,
            foreground=self._palette["typing_fg"],
            font=("TkDefaultFont", 9, "italic"),
        )
        self._message_display.tag_configure(
            self._TAG_EMPTY_STATE,
            foreground=self._palette["empty_state_fg"],
            justify=tk.CENTER,
            font=("TkDefaultFont", 11),
        )

    def _setup_bindings(self) -> None:
        """Set up keyboard and event bindings."""
        self._input_field.bind("<Return>", self._handle_enter)
        self._input_field.bind("<KeyRelease>", self._on_input_changed)
        # Combobox selection events
        self._model_combobox.bind("<<ComboboxSelected>>", self._on_model_selected)
        self._mode_combobox.bind("<<ComboboxSelected>>", self._on_mode_selected)
        # Give focus to input field
        self._input_field.focus_set()

    def _show_empty_state(self) -> None:
        """Display the empty state placeholder."""
        self._message_display.configure(state=tk.NORMAL)
        self._message_display.insert(
            tk.END,
            "\nNo conversation history yet.\nType a message below to start chatting with Kiro.\n",
            self._TAG_EMPTY_STATE,
        )
        self._message_display.configure(state=tk.DISABLED)

    def show_initializing(self) -> None:
        """Show an initializing message while the app connects to kiro-cli."""
        self._message_display.configure(state=tk.NORMAL)
        self._message_display.delete("1.0", tk.END)
        self._message_display.insert(
            tk.END,
            "\n⏳ Connecting to Kiro...\nPlease wait while the session is being established.\n",
            self._TAG_EMPTY_STATE,
        )
        self._message_display.configure(state=tk.DISABLED)

    def show_ready(self) -> None:
        """Replace the initializing message with the ready state."""
        self._message_display.configure(state=tk.NORMAL)
        self._message_display.delete("1.0", tk.END)
        self._message_display.insert(
            tk.END,
            "\nReady! Type a message below to start chatting with Kiro.\n",
            self._TAG_EMPTY_STATE,
        )
        self._message_display.configure(state=tk.DISABLED)

    def set_agent_name(self, name: str) -> None:
        """Set the display name used for assistant messages and typing indicator."""
        self._agent_display_name = name

    def _remove_empty_state(self) -> None:
        """Remove the empty state placeholder on first message."""
        if not self._has_messages:
            self._has_messages = True
            self._message_display.configure(state=tk.NORMAL)
            self._message_display.delete("1.0", tk.END)
            self._message_display.configure(state=tk.DISABLED)

    def _handle_send(self) -> None:
        """Handle send button click."""
        text = self.get_input_text()
        if text.strip():
            self._on_send(text.strip())

    def _handle_enter(self, event: tk.Event) -> str:
        """Handle Enter key press in input field."""
        text = self.get_input_text()
        if text.strip():
            self._on_send(text.strip())
        return "break"  # Prevent default behavior

    def _handle_close(self) -> None:
        """Handle window close event."""
        self._on_close()

    def _on_input_changed(self, event: tk.Event | None = None) -> None:
        """Update send button state based on input content."""
        text = self.get_input_text()
        if text.strip():
            self._send_button.state(["!disabled"])
        else:
            self._send_button.state(["disabled"])

    def append_user_message(self, text: str) -> None:
        """Add a user message to the display with 'You' label.

        Args:
            text: The message text to display.
        """
        self._remove_empty_state()
        was_at_bottom = self.is_scrolled_to_bottom

        self._message_display.configure(state=tk.NORMAL)
        self._message_display.insert(tk.END, "You:\n", self._TAG_USER_LABEL)
        self._message_display.insert(tk.END, f"{text}\n\n", self._TAG_USER_MSG)
        self._message_display.configure(state=tk.DISABLED)

        if was_at_bottom:
            self.scroll_to_bottom()

    def append_assistant_message(self, text: str) -> None:
        """Add an assistant message to the display with the agent name label.

        Args:
            text: The message text to display.
        """
        self._remove_empty_state()
        was_at_bottom = self.is_scrolled_to_bottom

        self._message_display.configure(state=tk.NORMAL)
        self._message_display.insert(
            tk.END, f"{self._agent_display_name}:\n", self._TAG_ASSISTANT_LABEL
        )
        render_markdown(self._message_display, text, base_tag=self._TAG_ASSISTANT_MSG)
        self._message_display.insert(tk.END, "\n\n", self._TAG_ASSISTANT_MSG)
        self._message_display.configure(state=tk.DISABLED)

        if was_at_bottom:
            self.scroll_to_bottom()

    def append_error(self, text: str) -> None:
        """Display an error message in the chat area.

        Args:
            text: The error message text to display.
        """
        self._remove_empty_state()
        was_at_bottom = self.is_scrolled_to_bottom

        self._message_display.configure(state=tk.NORMAL)
        self._message_display.insert(tk.END, f"⚠ {text}\n\n", self._TAG_ERROR)
        self._message_display.configure(state=tk.DISABLED)

        if was_at_bottom:
            self.scroll_to_bottom()

    def show_typing_indicator(self) -> None:
        """Show typing indicator in the message display."""
        if self._typing_visible:
            return
        self._typing_visible = True
        was_at_bottom = self.is_scrolled_to_bottom

        self._message_display.configure(state=tk.NORMAL)
        # Use a mark to track where the typing indicator starts
        self._message_display.mark_set("typing_start", "end-1c")
        self._message_display.mark_gravity("typing_start", tk.LEFT)
        self._message_display.insert(
            tk.END, f"{self._agent_display_name} is typing...\n", self._TAG_TYPING
        )
        self._message_display.configure(state=tk.DISABLED)

        if was_at_bottom:
            self.scroll_to_bottom()

    def hide_typing_indicator(self) -> None:
        """Remove the typing indicator from the message display."""
        if not self._typing_visible:
            return
        self._typing_visible = False

        self._message_display.configure(state=tk.NORMAL)
        with contextlib.suppress(tk.TclError):
            self._message_display.delete("typing_start", tk.END)
        self._message_display.configure(state=tk.DISABLED)

    def clear_input(self) -> None:
        """Clear the input field text."""
        self._input_field.delete(0, tk.END)
        self._on_input_changed()

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable the input field and send button.

        Args:
            enabled: True to enable, False to disable.
        """
        if enabled:
            self._input_field.configure(state="normal")
            self._on_input_changed()  # Update send button based on content
        else:
            self._input_field.configure(state="disabled")
            self._send_button.state(["disabled"])

    # --- Model/Mode selector methods ---

    def populate_models(self, models: list[dict]) -> None:
        """Populate the model dropdown with available models.

        Prepends an "auto" entry as the first option, then sets the combobox
        values to the name fields and selects the first item.

        Args:
            models: List of model dicts with 'modelId' and 'name' keys.
        """
        self._model_options = [{"modelId": "auto", "name": "auto"}] + list(models)
        names = [m["name"] for m in self._model_options]
        self._model_combobox["values"] = names
        self._model_combobox.current(0)

    def populate_modes(self, modes: list[dict]) -> None:
        """Populate the mode dropdown with available modes.

        Sets the combobox values to the name fields and selects the first item
        if modes is non-empty.

        Args:
            modes: List of mode dicts with 'id' and 'name' keys.
        """
        self._mode_options = list(modes)
        names = [m["name"] for m in self._mode_options]
        self._mode_combobox["values"] = names
        if self._mode_options:
            self._mode_combobox.current(0)

    def set_selected_model(self, model_id: str) -> None:
        """Set the model dropdown to show the model with the given ID.

        Args:
            model_id: The modelId to select. If not found, does nothing.
        """
        for i, m in enumerate(self._model_options):
            if m["modelId"] == model_id:
                self._model_combobox.current(i)
                return

    def set_selected_mode(self, mode_id: str) -> None:
        """Set the mode dropdown to show the mode with the given ID.

        Args:
            mode_id: The mode id to select. If not found, does nothing.
        """
        for i, m in enumerate(self._mode_options):
            if m["id"] == mode_id:
                self._mode_combobox.current(i)
                return

    def get_selected_model_id(self) -> str:
        """Get the modelId of the currently selected model.

        Returns:
            The modelId string, or "auto" if no selection.
        """
        if not self._model_options:
            return "auto"
        idx = self._model_combobox.current()
        if idx < 0 or idx >= len(self._model_options):
            return "auto"
        return str(self._model_options[idx]["modelId"])

    def get_selected_mode_id(self) -> str:
        """Get the id of the currently selected mode.

        Returns:
            The mode id string, or "" if no selection.
        """
        if not self._mode_options:
            return ""
        idx = self._mode_combobox.current()
        if idx < 0 or idx >= len(self._mode_options):
            return ""
        return str(self._mode_options[idx]["id"])

    def set_selectors_enabled(self, enabled: bool) -> None:
        """Enable or disable both model and mode selectors.

        Args:
            enabled: True to enable (readonly), False to disable.
        """
        state = "readonly" if enabled else "disabled"
        self._model_combobox.configure(state=state)
        self._mode_combobox.configure(state=state)

    def _on_model_selected(self, event: tk.Event | None = None) -> None:
        """Handle model combobox selection change."""
        if self._on_model_changed:
            model_id = self.get_selected_model_id()
            self._on_model_changed(model_id)

    def _on_mode_selected(self, event: tk.Event | None = None) -> None:
        """Handle mode combobox selection change."""
        if self._on_mode_changed:
            mode_id = self.get_selected_mode_id()
            self._on_mode_changed(mode_id)

    def get_input_text(self) -> str:
        """Get current text from the input field.

        Returns:
            The current text in the input field.
        """
        return self._input_field.get()

    @property
    def is_scrolled_to_bottom(self) -> bool:
        """Whether the message display is scrolled to the bottom.

        Returns:
            True if the view is at or near the bottom of the content.
        """
        yview = self._message_display.yview()
        # yview() returns (top, bottom) as fractions 0.0-1.0
        # Consider "at bottom" if the bottom fraction is >= 0.99
        # or if all content is visible (bottom == 1.0)
        # or if the widget hasn't been properly rendered yet (both 0.0)
        if yview[1] >= 0.99:
            return True
        if yview == (0.0, 0.0):
            return True
        # If the view starts at 0.0 and the content is small enough that
        # no scrolling has occurred, consider it at bottom
        return bool(yview[0] == 0.0 and yview[1] == 1.0)

    def scroll_to_bottom(self) -> None:
        """Scroll the message display to show the latest message."""
        self._message_display.see(tk.END)

    @staticmethod
    def _sanitize_for_applescript(text: str) -> str:
        """Sanitize a string for safe use in AppleScript double-quoted strings.

        Removes characters that could break out of the AppleScript string context.
        Only allows alphanumeric, spaces, and basic punctuation.
        """
        # Replace backslashes and double quotes which can escape AppleScript strings
        sanitized = text.replace("\\", "").replace('"', "'")
        # Strip any remaining control characters
        sanitized = "".join(c for c in sanitized if c.isprintable())
        # Truncate to a reasonable notification length
        return sanitized[:100]

    def ask_permission(self, title: str, details: str, options: list[dict]) -> str | None:
        """Show a permission dialog and return the selected option ID.

        Supports multiple options (e.g., Yes/Always/No) via a custom dialog
        when more than 2 options are present.

        Args:
            title: The tool call title (e.g., "Fetching web content")
            details: Additional details about what the tool wants to do (e.g., URL)
            options: List of option dicts with 'optionId', 'name', 'kind'

        Returns:
            The optionId of the selected option, or None if cancelled.
        """
        # Play alert sound and show system notification (macOS only)
        if sys.platform == "darwin":
            try:
                subprocess.Popen(  # nosec B603 B607 — hardcoded executable, no user input
                    ["afplay", "/System/Library/Sounds/Glass.aiff"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                self._root.bell()
            try:
                # Sanitize title to prevent AppleScript injection (T1 mitigation)
                safe_title = self._sanitize_for_applescript(title)
                subprocess.Popen(  # nosec B603 B607 — hardcoded executable, title sanitized via T1 mitigation
                    [
                        "osascript",
                        "-e",
                        (
                            f'display notification "{safe_title}" with title'
                            ' "Kiro ACP Chat" subtitle "Permission Required"'
                            ' sound name "Glass"'
                        ),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
        else:
            self._root.bell()

        # Build a detailed message showing what the tool wants to do (T5 mitigation)
        message_parts = [f"Action: {title}"]
        if details:
            message_parts.append(f"\nDetails:\n{details}")
        message = "\n".join(message_parts)

        # If there are more than 2 options (e.g., Yes/Always/No), use a custom dialog
        if len(options) > 2:
            return self._show_multi_option_dialog(message, options)

        # For simple allow/reject, use a yes/no dialog
        allow_options = [o for o in options if "allow" in o.get("kind", "")]
        reject_options = [o for o in options if "reject" in o.get("kind", "")]

        if allow_options and reject_options:
            result = messagebox.askyesno(
                "Tool Permission Request",
                f"Kiro wants to perform an action:\n\n{message}\n\nAllow this operation?",
                parent=self._root,
            )
            if result:
                return str(allow_options[0]["optionId"])
            else:
                return str(reject_options[0]["optionId"])

        # Fallback: just allow
        if options:
            return str(options[0]["optionId"])
        return None

    def _show_multi_option_dialog(self, message: str, options: list[dict]) -> str | None:
        """Show a custom dialog with multiple buttons for each option.

        Args:
            message: The descriptive message to display.
            options: List of option dicts with 'optionId', 'name', 'kind'.

        Returns:
            The optionId of the selected option, or None if window closed.
        """
        selected_id: str | None = None

        dialog = tk.Toplevel(self._root)
        dialog.title("Tool Permission Request")
        dialog.transient(self._root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center on parent
        dialog.geometry(f"+{self._root.winfo_rootx() + 50}+{self._root.winfo_rooty() + 50}")

        # Message frame
        msg_frame = ttk.Frame(dialog, padding=20)
        msg_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            msg_frame, text="Kiro wants to perform an action:", font=("TkDefaultFont", 13, "bold")
        )
        header.pack(anchor=tk.W)

        # Use a Text widget for the details so long URLs wrap properly
        detail_text = tk.Text(
            msg_frame,
            wrap=tk.WORD,
            height=8,
            width=60,
            relief=tk.FLAT,
            background=dialog.cget("background"),
            font=("TkDefaultFont", 12),
        )
        detail_text.insert(tk.END, message)
        detail_text.configure(state="disabled")
        detail_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Button frame
        btn_frame = ttk.Frame(dialog, padding=(20, 0, 20, 20))
        btn_frame.pack(fill=tk.X)

        def make_handler(option_id: str) -> Callable[[], None]:
            def handler() -> None:
                nonlocal selected_id
                selected_id = option_id
                dialog.destroy()

            return handler

        # Create a button for each option, ordered left to right
        for option in options:
            name = option.get("name", option.get("optionId", "?"))
            btn = ttk.Button(btn_frame, text=name, command=make_handler(option["optionId"]))
            btn.pack(side=tk.LEFT, padx=5)

        # Handle window close (X button) as cancel
        def on_close() -> None:
            nonlocal selected_id
            # Default to reject if available
            reject_options = [o for o in options if "reject" in o.get("kind", "")]
            if reject_options:
                selected_id = reject_options[0]["optionId"]
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)

        # Wait for the dialog to close
        dialog.wait_window()
        return selected_id
