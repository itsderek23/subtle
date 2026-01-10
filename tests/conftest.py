import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

import orjson
import pytest
from fastapi.testclient import TestClient

from subtle.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_projects_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@dataclass
class SessionFactory:
    base_dir: Path
    _counter: int = field(default=0, repr=False)

    def create(
        self,
        messages: list[dict] | None = None,
        session_id: str | None = None,
        project_path: str = "-Users-test-myproject",
    ) -> Path:
        project_dir = self.base_dir / project_path
        project_dir.mkdir(exist_ok=True)

        if session_id is None:
            self._counter += 1
            session_id = f"session{self._counter}"

        log_file = project_dir / f"{session_id}.jsonl"

        if messages is None:
            messages = [{"type": "user"}]

        lines = [orjson.dumps(m).decode() for m in messages]
        log_file.write_text("\n".join(lines))

        return log_file

    @contextmanager
    def patch_projects_dir(self):
        with mock.patch("subtle.models.session_log_file.PROJECTS_DIR", self.base_dir):
            yield


@pytest.fixture
def session_factory(temp_projects_dir):
    return SessionFactory(base_dir=temp_projects_dir)
