class TestListSessions:
    def test_returns_empty_list_when_no_sessions(self, client, session_factory):
        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_session_metadata(self, client, session_factory):
        session_factory.create(
            session_id="abc123",
            messages=[
                {"type": "user", "timestamp": "2026-01-09T12:00:00Z"},
                {
                    "type": "assistant",
                    "timestamp": "2026-01-09T12:30:00Z",
                    "message": {"usage": {"input_tokens": 100, "output_tokens": 50}},
                },
            ],
        )

        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        session = data[0]
        assert session["session_id"] == "abc123"
        assert session["project_name"] == "myproject"
        assert session["project_path"] == "/Users/test/myproject"
        assert session["duration_seconds"] == 1800
        assert session["input_tokens"] == 100
        assert session["output_tokens"] == 50


class TestListMessages:
    def test_returns_404_for_missing_session(self, client, session_factory):
        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions/nonexistent/messages")

        assert response.status_code == 404

    def test_returns_messages_with_metadata(self, client, session_factory):
        session_factory.create(
            session_id="abc123",
            messages=[
                {
                    "type": "user",
                    "timestamp": "2026-01-09T12:00:00Z",
                    "message": {"content": "Hello there"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-09T12:01:00Z",
                    "message": {
                        "model": "claude-opus-4-5-20251101",
                        "content": [{"type": "text", "text": "Hi!"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                },
            ],
        )

        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions/abc123/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        assert data[0]["index"] == 0
        assert data[0]["type"] == "user"
        assert data[0]["preview"] == "Hello there"

        assert data[1]["index"] == 1
        assert data[1]["type"] == "assistant"
        assert data[1]["model"] == "claude-opus-4-5-20251101"
        assert data[1]["input_tokens"] == 10
        assert data[1]["output_tokens"] == 5


class TestGetMessage:
    def test_returns_404_for_missing_session(self, client, session_factory):
        with session_factory.patch_projects_dir():
            response = client.get("/api/messages/nonexistent/0")

        assert response.status_code == 404

    def test_returns_404_for_invalid_index(self, client, session_factory):
        session_factory.create(session_id="abc123")

        with session_factory.patch_projects_dir():
            response = client.get("/api/messages/abc123/99")

        assert response.status_code == 404

    def test_returns_raw_message(self, client, session_factory):
        raw_message = {
            "type": "user",
            "timestamp": "2026-01-09T12:00:00Z",
            "message": {"content": "Hello"},
            "extra_field": "preserved",
        }
        session_factory.create(session_id="abc123", messages=[raw_message])

        with session_factory.patch_projects_dir():
            response = client.get("/api/messages/abc123/0")

        assert response.status_code == 200
        assert response.json() == raw_message


class TestGetMessageBreakdown:
    def test_returns_404_for_missing_session(self, client, session_factory):
        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions/nonexistent/message_breakdown")

        assert response.status_code == 404

    def test_returns_breakdown(self, client, session_factory):
        session_factory.create(
            session_id="abc123",
            messages=[
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}},
                {"type": "user", "message": {"content": "Hi there"}},
            ],
        )

        with session_factory.patch_projects_dir():
            response = client.get("/api/sessions/abc123/message_breakdown")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert len(data["breakdown"]) == 3

        categories = {b["category"]: b for b in data["breakdown"]}
        assert categories["Bash"]["count"] == 2
        assert categories["Bash"]["type"] == "tool"
        assert categories["assistant:text"]["count"] == 1
        assert categories["user:human_input"]["count"] == 1
