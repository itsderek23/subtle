from datetime import datetime, timezone

import pytest

from subtle.models import SessionLogFile, decode_project_path


class TestDecodeProjectPath:
    def test_basic_path(self):
        assert decode_project_path("-Users-derek-projects-sniffly") == "/Users/derek/projects/sniffly"

    def test_single_segment(self):
        assert decode_project_path("-home") == "/home"


class TestSessionId:
    def test_from_path(self, session_factory):
        session_factory.create(session_id="abc123")

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("abc123")

        assert session.session_id == "abc123"


class TestProjectName:
    def test_last_segment(self, session_factory):
        session_factory.create(project_path="-Users-derek-projects-sniffly")

        with session_factory.patch_projects_dir():
            sessions = SessionLogFile.all()

        assert sessions[0].project_name == "sniffly"


class TestProjectPath:
    def test_decoded(self, session_factory):
        session_factory.create(project_path="-Users-derek-projects-sniffly")

        with session_factory.patch_projects_dir():
            sessions = SessionLogFile.all()

        assert sessions[0].project_path == "/Users/derek/projects/sniffly"


class TestMessages:
    def test_parses_jsonl(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "timestamp": "2026-01-09T12:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-09T12:01:00Z"},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            messages = session.messages()

        assert len(messages) == 2
        assert messages[0].type == "user"
        assert messages[1].type == "assistant"


class TestTimestamps:
    def test_start_time(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "timestamp": "2026-01-09T12:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.start_time == datetime(2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc)

    def test_end_time(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "timestamp": "2026-01-09T12:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.end_time == datetime(2026, 1, 9, 12, 30, 0, tzinfo=timezone.utc)

    def test_duration(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "timestamp": "2026-01-09T12:00:00Z"},
                {"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.duration.total_seconds() == 1800


class TestTokens:
    def test_totals(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"usage": {"input_tokens": 100, "output_tokens": 50}}},
                {"type": "assistant", "message": {"usage": {"input_tokens": 200, "output_tokens": 100}}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.total_input_tokens == 300
        assert session.total_output_tokens == 150


class TestAll:
    def test_finds_sessions(self, session_factory):
        session_factory.create(session_id="session1")
        session_factory.create(session_id="session2")

        with session_factory.patch_projects_dir():
            sessions = SessionLogFile.all()

        assert len(sessions) == 2
        session_ids = {s.session_id for s in sessions}
        assert session_ids == {"session1", "session2"}

    def test_skips_hidden_project_dirs(self, session_factory):
        session_factory.create(project_path="-Users-test")
        session_factory.create(project_path=".hidden")

        with session_factory.patch_projects_dir():
            sessions = SessionLogFile.all()

        assert len(sessions) == 1


class TestFromId:
    def test_finds_session(self, session_factory):
        session_factory.create(session_id="abc123")

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("abc123")

        assert session is not None
        assert session.session_id == "abc123"

    def test_returns_none_for_missing(self, session_factory):
        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("nonexistent")

        assert session is None


class TestCommits:
    def test_counts_commits(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "content": "[main abc1234] feat: first\n 1 file changed", "is_error": False}
                ]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "content": "[main def5678] feat: second\n 2 files changed", "is_error": False}
                ]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.commit_count == 2
        assert len(session.commits) == 2
        assert session.commits[0]["hash"] == "abc1234"
        assert session.commits[1]["hash"] == "def5678"

    def test_empty_commits(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[{"type": "user"}],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.commit_count == 0
        assert session.commits == []


class TestToolLoc:
    def test_aggregates_edits(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit", "input": {"old_string": "a", "new_string": "b\nc"}}
                ]}},
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit", "input": {"old_string": "x\ny", "new_string": "z"}}
                ]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.tool_loc == {"added": 3, "removed": 3}

    def test_includes_writes(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Write", "input": {"content": "line1\nline2\nline3"}}
                ]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.tool_loc == {"added": 3, "removed": 0}

    def test_empty(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[{"type": "user"}],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.tool_loc == {"added": 0, "removed": 0}


class TestGitLoc:
    def test_aggregates_diff_stats(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "content": "[main abc] feat\n 2 files changed, 10 insertions(+), 5 deletions(-)"}
                ]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "content": "[main def] feat\n 1 file changed, 20 insertions(+), 3 deletions(-)"}
                ]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.git_loc == {"added": 30, "removed": 8}

    def test_none_when_no_git_data(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[{"type": "user"}],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")

        assert session.git_loc is None


class TestMessageBreakdown:
    def test_counts_tools(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        assert result["total"] == 3
        bash_entry = next(b for b in result["breakdown"] if b["category"] == "Bash")
        assert bash_entry["count"] == 2
        assert bash_entry["type"] == "tool"

    def test_counts_assistant_types(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "..."}]}},
                {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "..."}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        thinking = next(b for b in result["breakdown"] if b["category"] == "assistant:thinking")
        assert thinking["count"] == 2
        text = next(b for b in result["breakdown"] if b["category"] == "assistant:text")
        assert text["count"] == 1

    def test_counts_user_types(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "message": {"content": "Hello"}},
                {"type": "user", "message": {"content": "World"}},
                {"type": "user", "message": {"content": "<command-name>/commit</command-name>"}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        human = next(b for b in result["breakdown"] if b["category"] == "user:human_input")
        assert human["count"] == 2
        slash = next(b for b in result["breakdown"] if b["category"] == "user:slash_command")
        assert slash["count"] == 1

    def test_excludes_tools(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "TodoWrite"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "ExitPlanMode"}]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        assert result["total"] == 1
        categories = [b["category"] for b in result["breakdown"]]
        assert "Bash" in categories
        assert "TodoWrite" not in categories
        assert "ExitPlanMode" not in categories

    def test_sorts_by_type_then_count(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[
                {"type": "user", "message": {"content": "Hello"}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi"}]}},
            ],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        categories = [b["category"] for b in result["breakdown"]]
        assert categories == ["Bash", "Read", "assistant:text", "user:human_input"]

    def test_empty_session(self, session_factory):
        session_factory.create(
            session_id="test",
            messages=[{"type": "system"}],
        )

        with session_factory.patch_projects_dir():
            session = SessionLogFile.from_id("test")
            result = session.message_breakdown()

        assert result["total"] == 0
        assert result["breakdown"] == []
