"""Controller that coordinates between the UI and ACP client."""

import logging
import os

from kiro_acp_chat_client.acp_client import ACPClient
from kiro_acp_chat_client.models import Conversation
from kiro_acp_chat_client.preferences_manager import Preferences, PreferencesManager
from kiro_acp_chat_client.process_manager import ProcessManager
from kiro_acp_chat_client.ui import ChatUI

logger = logging.getLogger(__name__)


class ChatController:
    """Coordinates between the UI and ACP client.

    Manages conversation state, validates user input, orchestrates
    message sending/receiving, and handles errors.
    """

    MAX_MESSAGE_LENGTH = 2000

    def __init__(
        self,
        ui: ChatUI,
        acp_client: ACPClient,
        process_manager: ProcessManager,
        preferences_manager: PreferencesManager,
        cwd: str | None = None,
    ) -> None:
        self._ui = ui
        self._acp_client = acp_client
        self._process_manager = process_manager
        self._preferences_manager = preferences_manager
        self._cwd = cwd or os.getcwd()
        self._conversation = Conversation()
        self._available_models: list[dict] = []
        self._available_modes: list[dict] = []
        self._current_model_id: str = "auto"
        self._current_mode_id: str = ""
        self._log_message_content: bool = False

    async def start(self) -> None:
        """Initialize ACP connection and create session.

        Called on application startup. Spawns the kiro-cli acp process,
        sends the initialize handshake, creates a session, populates
        model/mode selectors, restores preferences, and sends ACP
        requests for non-default restored preferences.
        Handles errors by disabling input/selectors and showing error in UI.
        """
        # Disable input and selectors until session is ready
        self._ui.set_input_enabled(False)
        self._ui.set_selectors_enabled(False)
        try:
            await self._process_manager.start()
            await self._acp_client.initialize()
            session_result = await self._acp_client.create_session(self._cwd)
            session_id = session_result.get("sessionId", "")
            self._conversation.session_id = session_id
            logger.info("Startup complete. Session ID: %s", session_id)

            # Parse models and modes from session response
            models_data = session_result.get("models", {})
            modes_data = session_result.get("modes", {})
            available_models = (
                models_data.get("availableModels", []) if isinstance(models_data, dict) else []
            )
            available_modes = (
                modes_data.get("availableModes", []) if isinstance(modes_data, dict) else []
            )
            self._available_models = available_models
            self._available_modes = available_modes

            # Populate UI dropdowns
            self._ui.populate_models(available_models)
            self._ui.populate_modes(available_modes)

            # Load and resolve preferences
            prefs = self._preferences_manager.load()
            restored_model = self._resolve_model_preference(prefs.model_id, available_models)
            restored_mode = self._resolve_mode_preference(prefs.mode_id, available_modes)
            self._log_message_content = prefs.log_message_content

            # Set UI selections
            self._ui.set_selected_model(restored_model)
            self._ui.set_selected_mode(restored_mode)
            self._current_model_id = restored_model
            self._current_mode_id = restored_mode

            # Send ACP requests for non-default restored preferences
            if restored_model != "auto":
                await self._acp_client.set_model(session_id, restored_model)
            if available_modes and restored_mode != available_modes[0].get("id", ""):
                await self._acp_client.set_mode(session_id, restored_mode)

            # Save resolved preferences
            self._preferences_manager.save(
                Preferences(
                    model_id=restored_model,
                    mode_id=restored_mode,
                    log_message_content=self._log_message_content,
                )
            )

            # Set agent display name based on initial mode
            self._ui.set_agent_name(self._get_mode_name(restored_mode))

            # Session ready — show ready state and enable input/selectors
            self._ui.show_ready()
            self._ui.set_input_enabled(True)
            self._ui.set_selectors_enabled(True)
        except Exception as e:
            self._ui.set_input_enabled(False)
            self._ui.set_selectors_enabled(False)
            self._ui.append_error(str(e))

    async def send_message(self, text: str) -> None:
        """Validate and send a user message.

        1. Validate non-empty, non-whitespace, <= 2000 chars
        2. Display user message in UI
        3. Clear input field
        4. Show typing indicator, disable input
        5. Send prompt via ACP
        6. Stream response chunks via _stream_response()
        7. Remove typing indicator, re-enable input
        On error: hide typing indicator, show error, retain input text, re-enable input
        """
        # Validate input
        if not text or not text.strip():
            return
        if len(text) > self.MAX_MESSAGE_LENGTH:
            self._ui.append_error(
                f"Message too long ({len(text)} chars). Maximum is {self.MAX_MESSAGE_LENGTH}."
            )
            return

        # Add user message to conversation and display in UI
        if self._log_message_content:
            logger.info(
                "Sending message with session_id=%s: %s", self._conversation.session_id, text[:50]
            )
        else:
            logger.info(
                "Sending message with session_id=%s (content logging disabled)",
                self._conversation.session_id,
            )
        self._conversation.add_user_message(text)
        self._ui.append_user_message(text)

        # Clear input field
        self._ui.clear_input()

        # Show typing indicator and disable input
        self._ui.show_typing_indicator()
        self._ui.set_input_enabled(False)
        self._conversation.is_waiting = True

        try:
            # Send prompt via ACP client
            session_id = self._conversation.session_id or ""
            await self._acp_client.send_prompt(session_id, text)

            # Stream and accumulate the response
            assistant_text = await self._stream_response()

            # Display the full assistant response
            self._ui.hide_typing_indicator()
            if assistant_text:
                self._conversation.add_assistant_message(assistant_text)
                self._ui.append_assistant_message(assistant_text)
            else:
                # Empty response from agent
                error_msg = "Kiro could not generate a response. Please try again."
                self._conversation.add_error(error_msg)
                self._ui.append_error(error_msg)

            # Re-enable input
            self._ui.set_input_enabled(True)
            self._conversation.is_waiting = False

        except Exception as e:
            # On error: hide typing indicator, show error, retain input text, re-enable input
            self._ui.hide_typing_indicator()
            self._ui.append_error(str(e))
            self._ui.set_input_enabled(True)
            self._conversation.is_waiting = False

    async def _stream_response(self) -> str:
        """Read streaming updates and return the accumulated response text.

        Handles:
        - session/update notifications with agent_message_chunk
        - session/request_permission requests
        - Final response detection (message with id but no method)

        Returns:
            The concatenated assistant response text.

        Raises:
            Exception: Propagated from read_update() on connection errors.
        """
        chunks: list[str] = []
        while True:
            message = await self._acp_client.read_update()

            # Check if this is a request from the agent (has both "id" and "method")
            if "id" in message and "method" in message:
                method = message.get("method", "")
                if method == "session/request_permission":
                    # Agent is asking for tool permission
                    await self._handle_permission_request(message)
                    continue
                else:
                    # Unknown request from agent — skip
                    logger.warning("Unknown request from agent: %s", method)
                    continue

            # Check if this is the final response (has "id" but no "method")
            if "id" in message and "method" not in message:
                # Turn is complete
                break

            # Check if this is a session/update notification with agent_message_chunk
            method = message.get("method", "")
            if method == "session/update":
                params = message.get("params", {})
                update = params.get("update", {})
                session_update_type = update.get("sessionUpdate", "")
                if session_update_type == "agent_message_chunk":
                    content = update.get("content", {})
                    if content.get("type") == "text":
                        chunk = content.get("text", "")
                        chunks.append(chunk)
                elif session_update_type == "tool_call":
                    # Tool is being invoked
                    tool_title = update.get("title", "unknown tool")
                    logger.info("Tool call: %s", tool_title)

            # All other notifications (commands/available, metadata, mcp events, etc.)
            # are silently skipped

        return "".join(chunks)

    def _resolve_model_preference(self, saved_id: str, available: list[dict]) -> str:
        """Resolve a saved model preference against available models.

        Returns saved_id if it exists in available, otherwise "auto".
        """
        for model in available:
            if model.get("modelId") == saved_id:
                return saved_id
        return "auto"

    def _resolve_mode_preference(self, saved_id: str, available: list[dict]) -> str:
        """Resolve a saved mode preference against available modes.

        Returns saved_id if it exists in available, otherwise the first mode's id.
        Returns "" if available is empty.
        """
        if not available:
            return ""
        for mode in available:
            if mode.get("id") == saved_id:
                return saved_id
        return str(available[0].get("id", ""))

    def _get_mode_name(self, mode_id: str) -> str:
        """Get the display name for a mode by its ID.

        Returns the mode's name if found, otherwise "Kiro" as fallback.
        """
        for mode in self._available_modes:
            if mode.get("id") == mode_id:
                return str(mode.get("name", "Kiro"))
        return "Kiro"

    async def on_model_changed(self, model_id: str) -> None:
        """Handle user changing the model selection.

        Sends set_model ACP request. On success, saves preferences.
        On error, reverts selector to previous value and shows error.
        """
        previous_model_id = self._current_model_id
        try:
            session_id = self._conversation.session_id or ""
            response = await self._acp_client.set_model(session_id, model_id)
            if "error" in response:
                # Revert selector and show error
                self._ui.set_selected_model(previous_model_id)
                error_msg = response["error"].get("message", "Failed to set model")
                self._ui.append_error(error_msg)
                return
            # Success: update current and save preferences
            self._current_model_id = model_id
            self._preferences_manager.save(
                Preferences(
                    model_id=model_id,
                    mode_id=self._current_mode_id,
                    log_message_content=self._log_message_content,
                )
            )
        except Exception as e:
            # Revert selector and show error
            self._ui.set_selected_model(previous_model_id)
            self._ui.append_error(str(e))

    async def on_mode_changed(self, mode_id: str) -> None:
        """Handle user changing the mode selection.

        Sends set_mode ACP request. On success, saves preferences.
        On error, reverts selector to previous value and shows error.
        """
        previous_mode_id = self._current_mode_id
        try:
            session_id = self._conversation.session_id or ""
            response = await self._acp_client.set_mode(session_id, mode_id)
            if "error" in response:
                # Revert selector and show error
                self._ui.set_selected_mode(previous_mode_id)
                error_msg = response["error"].get("message", "Failed to set mode")
                self._ui.append_error(error_msg)
                return
            # Success: update current and save preferences
            self._current_mode_id = mode_id
            self._ui.set_agent_name(self._get_mode_name(mode_id))
            self._preferences_manager.save(
                Preferences(
                    model_id=self._current_model_id,
                    mode_id=mode_id,
                    log_message_content=self._log_message_content,
                )
            )
        except Exception as e:
            # Revert selector and show error
            self._ui.set_selected_mode(previous_mode_id)
            self._ui.append_error(str(e))

    async def shutdown(self) -> None:
        """Clean up ACP session and terminate subprocess."""
        await self._process_manager.shutdown()

    async def _handle_permission_request(self, message: dict) -> None:
        """Handle a session/request_permission request from the agent.

        Shows a dialog to the user and sends the response back.

        Note: The ACP protocol only provides toolCallId and title in the
        toolCall payload. Tool parameters (e.g., URL for web fetch) are not
        included in the permission request, so we cannot display them.
        """
        request_id = message["id"]
        params = message.get("params", {})
        tool_call = params.get("toolCall", {})
        options = params.get("options", [])

        # Build description from tool call info
        title = tool_call.get("title", "Unknown action")
        # Try to get details from content (if ACP ever provides it)
        details_parts = []
        content = tool_call.get("content", [])
        if content:
            for item in content:
                if item.get("type") == "diff":
                    path = item.get("path", "")
                    details_parts.append(f"File: {path}")
                elif item.get("type") == "content":
                    inner = item.get("content", {})
                    if inner.get("type") == "text":
                        details_parts.append(inner.get("text", ""))
                elif item.get("type") == "text":
                    details_parts.append(item.get("text", ""))

        # Extract tool input parameters if available (e.g., URL for web fetch)
        tool_input = tool_call.get("input", {})
        if tool_input and isinstance(tool_input, dict):
            for key, value in tool_input.items():
                if isinstance(value, str) and value:
                    details_parts.append(f"{key}: {value}")

        details = "\n".join(details_parts)

        # Show permission dialog to user
        selected_option_id = self._ui.ask_permission(title, details.strip(), options)

        # Send response back to agent
        if selected_option_id:
            result = {"outcome": {"outcome": "selected", "optionId": selected_option_id}}
        else:
            result = {"outcome": {"outcome": "cancelled"}}

        await self._acp_client.respond_to_request(request_id, result)
        logger.info("Permission response: %s -> %s", title, selected_option_id)
