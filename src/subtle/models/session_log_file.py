from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import orjson

from .message import Message

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def decode_project_path(encoded: str) -> str:
    if encoded.startswith("-"):
        encoded = "/" + encoded[1:]
    return encoded.replace("-", "/")


@dataclass
class SessionLogFile:
    path: Path
    project_dir: Path

    @classmethod
    def all(cls) -> list["SessionLogFile"]:
        sessions = []
        if not PROJECTS_DIR.exists():
            return sessions
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            if project_dir.name.startswith("."):
                continue
            for log_file in project_dir.glob("*.jsonl"):
                if log_file.name.startswith("."):
                    continue
                sessions.append(cls(path=log_file, project_dir=project_dir))
        sessions.sort(key=lambda s: s.path.stat().st_mtime, reverse=True)
        return sessions

    @classmethod
    def from_id(cls, session_id: str) -> "SessionLogFile | None":
        if not PROJECTS_DIR.exists():
            return None
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            if project_dir.name.startswith("."):
                continue
            log_file = project_dir / f"{session_id}.jsonl"
            if log_file.exists():
                return cls(path=log_file, project_dir=project_dir)
        return None

    @property
    def session_id(self) -> str:
        return self.path.stem

    @property
    def project_name(self) -> str:
        parts = self.project_dir.name.split("-")
        return parts[-1] if parts else self.project_dir.name

    @property
    def project_path(self) -> str:
        return decode_project_path(self.project_dir.name)

    def messages(self) -> list[Message]:
        messages = []
        with open(self.path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = orjson.loads(line)
                messages.append(Message(raw=data))
        return messages

    @property
    def start_time(self) -> datetime | None:
        messages = self.messages()
        for msg in messages:
            if msg.timestamp:
                return msg.timestamp
        return None

    @property
    def end_time(self) -> datetime | None:
        messages = self.messages()
        for msg in reversed(messages):
            if msg.timestamp:
                return msg.timestamp
        return None

    @property
    def duration(self) -> timedelta | None:
        start = self.start_time
        end = self.end_time
        if start and end:
            return end - start
        return None

    @property
    def total_input_tokens(self) -> int:
        total = 0
        for msg in self.messages():
            tokens = msg.input_tokens
            if tokens:
                total += tokens
        return total

    @property
    def total_output_tokens(self) -> int:
        total = 0
        for msg in self.messages():
            tokens = msg.output_tokens
            if tokens:
                total += tokens
        return total
