from datetime import datetime, timezone

from subtle.models import Message


class TestType:
    def test_user(self):
        msg = Message(raw={"type": "user"})
        assert msg.type == "user"

    def test_assistant(self):
        msg = Message(raw={"type": "assistant"})
        assert msg.type == "assistant"

    def test_unknown(self):
        msg = Message(raw={})
        assert msg.type == "unknown"


class TestTimestamp:
    def test_parses_iso(self):
        msg = Message(raw={"timestamp": "2026-01-09T12:47:44.854Z"})
        assert msg.timestamp == datetime(2026, 1, 9, 12, 47, 44, 854000, tzinfo=timezone.utc)

    def test_none(self):
        msg = Message(raw={})
        assert msg.timestamp is None


class TestModel:
    def test_from_assistant_message(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {"model": "claude-opus-4-5-20251101"}
        })
        assert msg.model == "claude-opus-4-5-20251101"

    def test_none_for_user(self):
        msg = Message(raw={"type": "user"})
        assert msg.model is None


class TestInputTokens:
    def test_with_cache(self):
        msg = Message(raw={
            "message": {
                "usage": {
                    "input_tokens": 10,
                    "cache_creation_input_tokens": 100,
                    "cache_read_input_tokens": 200
                }
            }
        })
        assert msg.input_tokens == 310

    def test_without_cache(self):
        msg = Message(raw={
            "message": {
                "usage": {"input_tokens": 50}
            }
        })
        assert msg.input_tokens == 50

    def test_none(self):
        msg = Message(raw={"type": "user"})
        assert msg.input_tokens is None


class TestOutputTokens:
    def test_returns_value(self):
        msg = Message(raw={
            "message": {
                "usage": {"output_tokens": 42}
            }
        })
        assert msg.output_tokens == 42


class TestTools:
    def test_extracts_tool_names(self):
        msg = Message(raw={
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "tool_use", "name": "Read", "id": "123"},
                    {"type": "tool_use", "name": "Bash", "id": "456"},
                ]
            }
        })
        assert msg.tools == ["Read", "Bash"]

    def test_empty_for_user(self):
        msg = Message(raw={"type": "user", "message": {"content": "Hello"}})
        assert msg.tools == []


class TestPreview:
    def test_from_string_content(self):
        msg = Message(raw={"message": {"content": "Hello world"}})
        assert msg.preview == "Hello world"

    def test_from_text_block(self):
        msg = Message(raw={
            "message": {
                "content": [{"type": "text", "text": "Hello there"}]
            }
        })
        assert msg.preview == "Hello there"

    def test_truncates_long_text(self):
        long_text = "x" * 200
        msg = Message(raw={"message": {"content": long_text}})
        assert len(msg.preview) == 103
        assert msg.preview.endswith("...")

    def test_includes_tool_names(self):
        msg = Message(raw={
            "message": {
                "content": [
                    {"type": "text", "text": "Running"},
                    {"type": "tool_use", "name": "Bash"}
                ]
            }
        })
        assert msg.preview == "Running [Tool: Bash]"
