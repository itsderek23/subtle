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
