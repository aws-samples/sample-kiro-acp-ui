"""Unit tests for data models and JSON-RPC message types."""

import json
import time
from unittest.mock import patch

from kiro_acp_chat_client.models import (
    Conversation,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    from_json_line,
    to_json_line,
)


class TestJsonRpcRequest:
    def test_default_values(self):
        req = JsonRpcRequest()
        assert req.jsonrpc == "2.0"
        assert req.id == 0
        assert req.method == ""
        assert req.params == {}

    def test_custom_values(self):
        req = JsonRpcRequest(id=1, method="initialize", params={"key": "value"})
        assert req.id == 1
        assert req.method == "initialize"
        assert req.params == {"key": "value"}


class TestJsonRpcResponse:
    def test_default_values(self):
        resp = JsonRpcResponse()
        assert resp.jsonrpc == "2.0"
        assert resp.id == 0
        assert resp.result is None
        assert resp.error is None

    def test_with_result(self):
        resp = JsonRpcResponse(id=1, result={"capabilities": {}})
        assert resp.result == {"capabilities": {}}
        assert resp.error is None

    def test_with_error(self):
        resp = JsonRpcResponse(id=1, error={"code": -1, "message": "fail"})
        assert resp.result is None
        assert resp.error == {"code": -1, "message": "fail"}


class TestJsonRpcNotification:
    def test_default_values(self):
        notif = JsonRpcNotification()
        assert notif.jsonrpc == "2.0"
        assert notif.method == ""
        assert notif.params == {}

    def test_custom_values(self):
        notif = JsonRpcNotification(
            method="session/update", params={"sessionId": "abc"}
        )
        assert notif.method == "session/update"
        assert notif.params == {"sessionId": "abc"}


class TestMessage:
    def test_creation(self):
        msg = Message(role="user", content="hello", timestamp=1000.0)
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp == 1000.0
        assert msg.is_error is False

    def test_error_message(self):
        msg = Message(role="assistant", content="error", timestamp=1000.0, is_error=True)
        assert msg.is_error is True


class TestConversation:
    def test_empty_conversation(self):
        conv = Conversation()
        assert conv.messages == []
        assert conv.session_id is None
        assert conv.is_waiting is False

    def test_add_user_message(self):
        conv = Conversation()
        msg = conv.add_user_message("hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.is_error is False
        assert len(conv.messages) == 1
        assert conv.messages[0] is msg

    def test_add_assistant_message(self):
        conv = Conversation()
        msg = conv.add_assistant_message("hi there")
        assert msg.role == "assistant"
        assert msg.content == "hi there"
        assert msg.is_error is False
        assert len(conv.messages) == 1

    def test_add_error(self):
        conv = Conversation()
        msg = conv.add_error("something went wrong")
        assert msg.role == "assistant"
        assert msg.content == "something went wrong"
        assert msg.is_error is True
        assert len(conv.messages) == 1

    def test_message_ordering(self):
        conv = Conversation()
        conv.add_user_message("first")
        conv.add_assistant_message("second")
        conv.add_user_message("third")
        assert [m.content for m in conv.messages] == ["first", "second", "third"]


class TestToJsonLine:
    def test_request_serialization(self):
        req = JsonRpcRequest(id=1, method="initialize", params={"key": "val"})
        line = to_json_line(req)
        assert line.endswith("\n")
        assert "\n" not in line[:-1]  # No embedded newlines
        data = json.loads(line)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["method"] == "initialize"
        assert data["params"] == {"key": "val"}

    def test_response_serialization_with_result(self):
        resp = JsonRpcResponse(id=1, result={"status": "ok"})
        line = to_json_line(resp)
        assert line.endswith("\n")
        data = json.loads(line)
        assert data["id"] == 1
        assert data["result"] == {"status": "ok"}
        assert "error" not in data

    def test_response_serialization_with_error(self):
        resp = JsonRpcResponse(id=1, error={"code": -1, "message": "fail"})
        line = to_json_line(resp)
        data = json.loads(line)
        assert "result" not in data
        assert data["error"] == {"code": -1, "message": "fail"}

    def test_notification_serialization(self):
        notif = JsonRpcNotification(method="session/update", params={"data": "x"})
        line = to_json_line(notif)
        assert line.endswith("\n")
        data = json.loads(line)
        assert data["method"] == "session/update"
        assert "id" not in data or data.get("id") is None  # notifications shouldn't need id

    def test_no_embedded_newlines_with_multiline_content(self):
        req = JsonRpcRequest(
            id=1, method="test", params={"text": "line1\nline2\nline3"}
        )
        line = to_json_line(req)
        # Only the trailing newline should exist
        assert line.count("\n") == 1
        assert line.endswith("\n")


class TestFromJsonLine:
    def test_parse_request(self):
        line = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"key":"val"}}\n'
        msg = from_json_line(line)
        assert isinstance(msg, JsonRpcRequest)
        assert msg.id == 1
        assert msg.method == "initialize"
        assert msg.params == {"key": "val"}

    def test_parse_response_with_result(self):
        line = '{"jsonrpc":"2.0","id":1,"result":{"status":"ok"}}\n'
        msg = from_json_line(line)
        assert isinstance(msg, JsonRpcResponse)
        assert msg.id == 1
        assert msg.result == {"status": "ok"}
        assert msg.error is None

    def test_parse_response_with_error(self):
        line = '{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"fail"}}\n'
        msg = from_json_line(line)
        assert isinstance(msg, JsonRpcResponse)
        assert msg.error == {"code": -1, "message": "fail"}
        assert msg.result is None

    def test_parse_notification(self):
        line = '{"jsonrpc":"2.0","method":"session/update","params":{"data":"x"}}\n'
        msg = from_json_line(line)
        assert isinstance(msg, JsonRpcNotification)
        assert msg.method == "session/update"
        assert msg.params == {"data": "x"}

    def test_parse_without_trailing_newline(self):
        line = '{"jsonrpc":"2.0","id":5,"method":"test","params":{}}'
        msg = from_json_line(line)
        assert isinstance(msg, JsonRpcRequest)
        assert msg.id == 5

    def test_round_trip_request(self):
        original = JsonRpcRequest(id=42, method="session/prompt", params={"text": "hi"})
        restored = from_json_line(to_json_line(original))
        assert isinstance(restored, JsonRpcRequest)
        assert restored.id == original.id
        assert restored.method == original.method
        assert restored.params == original.params

    def test_round_trip_response(self):
        original = JsonRpcResponse(id=7, result={"sessionId": "abc123"})
        restored = from_json_line(to_json_line(original))
        assert isinstance(restored, JsonRpcResponse)
        assert restored.id == original.id
        assert restored.result == original.result

    def test_round_trip_notification(self):
        original = JsonRpcNotification(
            method="session/update", params={"content": "chunk"}
        )
        restored = from_json_line(to_json_line(original))
        assert isinstance(restored, JsonRpcNotification)
        assert restored.method == original.method
        assert restored.params == original.params
