"""Data models and JSON-RPC message types for the Kiro ACP Chat Client."""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Union


@dataclass
class JsonRpcRequest:
    """A JSON-RPC 2.0 request message."""

    jsonrpc: str = "2.0"
    id: int = 0
    method: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class JsonRpcResponse:
    """A JSON-RPC 2.0 response message."""

    jsonrpc: str = "2.0"
    id: int = 0
    result: Optional[dict] = None
    error: Optional[dict] = None


@dataclass
class JsonRpcNotification:
    """A JSON-RPC 2.0 notification (no id, no response expected)."""

    jsonrpc: str = "2.0"
    method: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class Message:
    """A single message in the conversation."""

    role: str  # "user" or "assistant"
    content: str  # The message text
    timestamp: float  # time.time() when created
    is_error: bool = False  # Whether this is an error message


@dataclass
class Conversation:
    """The current session's conversation state."""

    messages: list[Message] = field(default_factory=list)
    session_id: Optional[str] = None
    is_waiting: bool = False  # Whether we're waiting for a response

    def add_user_message(self, text: str) -> Message:
        """Add a user message to the conversation."""
        msg = Message(role="user", content=text, timestamp=time.time())
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, text: str) -> Message:
        """Add an assistant message to the conversation."""
        msg = Message(role="assistant", content=text, timestamp=time.time())
        self.messages.append(msg)
        return msg

    def add_error(self, text: str) -> Message:
        """Add an error message to the conversation."""
        msg = Message(
            role="assistant", content=text, timestamp=time.time(), is_error=True
        )
        self.messages.append(msg)
        return msg


# Type alias for any JSON-RPC message
JsonRpcMessage = Union[JsonRpcRequest, JsonRpcResponse, JsonRpcNotification]


def to_json_line(message: JsonRpcMessage) -> str:
    """Serialize a JSON-RPC message to a single newline-delimited JSON line.

    Produces a JSON string with no embedded newlines, terminated by a single '\\n'.
    """
    data = asdict(message)
    # Remove None values from response to keep output clean
    if isinstance(message, JsonRpcResponse):
        if data["result"] is None:
            del data["result"]
        if data["error"] is None:
            del data["error"]
    # Use separators to produce compact JSON with no extra whitespace
    # ensure_ascii=False allows unicode, but separators prevent embedded newlines
    line = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return line + "\n"


def from_json_line(line: str) -> JsonRpcMessage:
    """Parse a JSON line into the appropriate JSON-RPC message dataclass.

    Accepts a JSON string (with or without trailing newline).
    Returns a JsonRpcRequest, JsonRpcResponse, or JsonRpcNotification.
    """
    data = json.loads(line.strip())

    if "id" in data:
        if "method" in data:
            # It's a request (has both id and method)
            return JsonRpcRequest(
                jsonrpc=data.get("jsonrpc", "2.0"),
                id=data["id"],
                method=data["method"],
                params=data.get("params", {}),
            )
        else:
            # It's a response (has id but no method)
            return JsonRpcResponse(
                jsonrpc=data.get("jsonrpc", "2.0"),
                id=data["id"],
                result=data.get("result"),
                error=data.get("error"),
            )
    else:
        # It's a notification (no id)
        return JsonRpcNotification(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )
