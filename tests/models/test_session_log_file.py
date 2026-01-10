import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import orjson
import pytest

from subtle.models import SessionLogFile, decode_project_path


class TestDecodeProjectPath:
    def test_basic_path(self):
        assert decode_project_path("-Users-derek-projects-sniffly") == "/Users/derek/projects/sniffly"

    def test_single_segment(self):
        assert decode_project_path("-home") == "/home"


class TestSessionId:
    def test_from_path(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-test-project"
        project_dir.mkdir()
        log_file = project_dir / "abc123.jsonl"
        log_file.write_text("")

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.session_id == "abc123"


class TestProjectName:
    def test_last_segment(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-derek-projects-sniffly"
        project_dir.mkdir()
        log_file = project_dir / "test.jsonl"
        log_file.write_text("")

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.project_name == "sniffly"


class TestProjectPath:
    def test_decoded(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-derek-projects-sniffly"
        project_dir.mkdir()
        log_file = project_dir / "test.jsonl"
        log_file.write_text("")

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.project_path == "/Users/derek/projects/sniffly"


class TestMessages:
    def test_parses_jsonl(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-test"
        project_dir.mkdir()
        log_file = project_dir / "session.jsonl"

        lines = [
            orjson.dumps({"type": "user", "timestamp": "2026-01-09T12:00:00Z"}).decode(),
            orjson.dumps({"type": "assistant", "timestamp": "2026-01-09T12:01:00Z"}).decode(),
        ]
        log_file.write_text("\n".join(lines))

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        messages = session.messages()

        assert len(messages) == 2
        assert messages[0].type == "user"
        assert messages[1].type == "assistant"


class TestTimestamps:
    def test_start_time(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-test"
        project_dir.mkdir()
        log_file = project_dir / "session.jsonl"

        lines = [
            orjson.dumps({"type": "user", "timestamp": "2026-01-09T12:00:00Z"}).decode(),
            orjson.dumps({"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"}).decode(),
        ]
        log_file.write_text("\n".join(lines))

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.start_time == datetime(2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc)

    def test_end_time(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-test"
        project_dir.mkdir()
        log_file = project_dir / "session.jsonl"

        lines = [
            orjson.dumps({"type": "user", "timestamp": "2026-01-09T12:00:00Z"}).decode(),
            orjson.dumps({"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"}).decode(),
        ]
        log_file.write_text("\n".join(lines))

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.end_time == datetime(2026, 1, 9, 12, 30, 0, tzinfo=timezone.utc)

    def test_duration(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-test"
        project_dir.mkdir()
        log_file = project_dir / "session.jsonl"

        lines = [
            orjson.dumps({"type": "user", "timestamp": "2026-01-09T12:00:00Z"}).decode(),
            orjson.dumps({"type": "assistant", "timestamp": "2026-01-09T12:30:00Z"}).decode(),
        ]
        log_file.write_text("\n".join(lines))

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.duration.total_seconds() == 1800


class TestTokens:
    def test_totals(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-test"
        project_dir.mkdir()
        log_file = project_dir / "session.jsonl"

        lines = [
            orjson.dumps({
                "type": "assistant",
                "message": {"usage": {"input_tokens": 100, "output_tokens": 50}}
            }).decode(),
            orjson.dumps({
                "type": "assistant",
                "message": {"usage": {"input_tokens": 200, "output_tokens": 100}}
            }).decode(),
        ]
        log_file.write_text("\n".join(lines))

        session = SessionLogFile(path=log_file, project_dir=project_dir)
        assert session.total_input_tokens == 300
        assert session.total_output_tokens == 150


class TestAll:
    def test_finds_sessions(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-test-myproject"
        project_dir.mkdir()
        (project_dir / "session1.jsonl").write_text("{}")
        (project_dir / "session2.jsonl").write_text("{}")
        (project_dir / ".hidden.jsonl").write_text("{}")

        with mock.patch("subtle.models.session_log_file.PROJECTS_DIR", temp_projects_dir):
            sessions = SessionLogFile.all()

        assert len(sessions) == 2
        session_ids = {s.session_id for s in sessions}
        assert session_ids == {"session1", "session2"}

    def test_skips_hidden_project_dirs(self, temp_projects_dir):
        visible_dir = temp_projects_dir / "-Users-test"
        visible_dir.mkdir()
        (visible_dir / "session.jsonl").write_text("{}")

        hidden_dir = temp_projects_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "session.jsonl").write_text("{}")

        with mock.patch("subtle.models.session_log_file.PROJECTS_DIR", temp_projects_dir):
            sessions = SessionLogFile.all()

        assert len(sessions) == 1


class TestFromId:
    def test_finds_session(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-test"
        project_dir.mkdir()
        (project_dir / "abc123.jsonl").write_text("{}")

        with mock.patch("subtle.models.session_log_file.PROJECTS_DIR", temp_projects_dir):
            session = SessionLogFile.from_id("abc123")

        assert session is not None
        assert session.session_id == "abc123"

    def test_returns_none_for_missing(self, temp_projects_dir):
        project_dir = temp_projects_dir / "-Users-test"
        project_dir.mkdir()

        with mock.patch("subtle.models.session_log_file.PROJECTS_DIR", temp_projects_dir):
            session = SessionLogFile.from_id("nonexistent")

        assert session is None


@pytest.fixture
def temp_projects_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
