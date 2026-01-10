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


class TestEditLoc:
    def test_single_line_edit(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {
                        "old_string": "hello",
                        "new_string": "world"
                    }
                }]
            }
        })
        assert msg.edit_loc == {"added": 1, "removed": 1}

    def test_multiline_edit(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {
                        "old_string": "line1\nline2",
                        "new_string": "new1\nnew2\nnew3"
                    }
                }]
            }
        })
        assert msg.edit_loc == {"added": 3, "removed": 2}

    def test_none_for_non_edit(self):
        msg = Message(raw={"type": "user"})
        assert msg.edit_loc is None


class TestWriteLoc:
    def test_single_line(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "Write",
                    "input": {"content": "hello world"}
                }]
            }
        })
        assert msg.write_loc == 1

    def test_multiline(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "Write",
                    "input": {"content": "line1\nline2\nline3"}
                }]
            }
        })
        assert msg.write_loc == 3

    def test_none_for_non_write(self):
        msg = Message(raw={"type": "user"})
        assert msg.write_loc is None


class TestIsCommit:
    def test_detects_commit(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main caf1219] feat: add new feature\n 3 files changed, 42 insertions(+)",
                    "is_error": False
                }]
            }
        })
        assert msg.is_commit is True

    def test_false_for_error(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main caf1219] feat: add new feature",
                    "is_error": True
                }]
            }
        })
        assert msg.is_commit is False

    def test_false_for_non_commit(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "Files listed successfully"
                }]
            }
        })
        assert msg.is_commit is False


class TestCommitInfo:
    def test_extracts_info(self):
        msg = Message(raw={
            "timestamp": "2026-01-09T12:00:00.000Z",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main abc1234] feat: add login feature\n 2 files changed",
                    "is_error": False
                }]
            }
        })
        info = msg.commit_info
        assert info["hash"] == "abc1234"
        assert info["message"] == "feat: add login feature"
        assert info["timestamp"] is not None

    def test_none_for_non_commit(self):
        msg = Message(raw={"type": "user"})
        assert msg.commit_info is None


class TestGitDiffLoc:
    def test_parses_insertions_and_deletions(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main abc1234] feat\n 3 files changed, 42 insertions(+), 12 deletions(-)"
                }]
            }
        })
        assert msg.git_diff_loc == {"added": 42, "removed": 12}

    def test_insertions_only(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main abc1234] feat\n 1 file changed, 10 insertions(+)"
                }]
            }
        })
        assert msg.git_diff_loc == {"added": 10, "removed": 0}

    def test_deletions_only(self):
        msg = Message(raw={
            "message": {
                "content": [{
                    "type": "tool_result",
                    "content": "[main abc1234] feat\n 1 file changed, 5 deletions(-)"
                }]
            }
        })
        assert msg.git_diff_loc == {"added": 0, "removed": 5}

    def test_none_for_no_stats(self):
        msg = Message(raw={"type": "user"})
        assert msg.git_diff_loc is None


class TestBreakdownCategory:
    def test_tool_use_bash(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Bash", "id": "123"}]
            }
        })
        assert msg.breakdown_category == {"category": "Bash", "type": "tool"}

    def test_tool_use_read(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Read", "id": "123"}]
            }
        })
        assert msg.breakdown_category == {"category": "Read", "type": "tool"}

    def test_excluded_tool_todowrite(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "TodoWrite", "id": "123"}]
            }
        })
        assert msg.breakdown_category is None

    def test_excluded_tool_exitplanmode(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "ExitPlanMode", "id": "123"}]
            }
        })
        assert msg.breakdown_category is None

    def test_excluded_tool_killshell(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "KillShell", "id": "123"}]
            }
        })
        assert msg.breakdown_category is None

    def test_assistant_thinking(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "thinking", "thinking": "Let me think..."}]
            }
        })
        assert msg.breakdown_category == {"category": "assistant:thinking", "type": "assistant"}

    def test_assistant_text(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Hello!"}]
            }
        })
        assert msg.breakdown_category == {"category": "assistant:text", "type": "assistant"}

    def test_assistant_text_with_tool_use_returns_tool(self):
        msg = Message(raw={
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Let me run this"},
                    {"type": "tool_use", "name": "Bash", "id": "123"}
                ]
            }
        })
        assert msg.breakdown_category == {"category": "Bash", "type": "tool"}

    def test_user_human_input_string(self):
        msg = Message(raw={
            "type": "user",
            "message": {"content": "Hello, can you help me?"}
        })
        assert msg.breakdown_category == {"category": "user:human_input", "type": "user"}

    def test_user_slash_command(self):
        msg = Message(raw={
            "type": "user",
            "message": {"content": "<command-name>/commit</command-name>"}
        })
        assert msg.breakdown_category == {"category": "user:slash_command", "type": "user"}

    def test_user_human_input_list(self):
        msg = Message(raw={
            "type": "user",
            "message": {
                "content": [{"type": "text", "text": "Hello there"}]
            }
        })
        assert msg.breakdown_category == {"category": "user:human_input", "type": "user"}

    def test_skill_prompt_excluded(self):
        msg = Message(raw={
            "type": "user",
            "message": {
                "content": [{
                    "type": "text",
                    "text": "\n---\ndescription: Create commit\nallowed-tools: Bash\n---"
                }]
            }
        })
        assert msg.breakdown_category is None

    def test_tool_result_excluded(self):
        msg = Message(raw={
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "content": "Success"}]
            }
        })
        assert msg.breakdown_category is None

    def test_system_message_excluded(self):
        msg = Message(raw={"type": "system", "subtype": "turn_duration"})
        assert msg.breakdown_category is None

    def test_file_history_snapshot_excluded(self):
        msg = Message(raw={"type": "file-history-snapshot"})
        assert msg.breakdown_category is None
