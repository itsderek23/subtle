from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import orjson

from .message import Message

TYPE_ORDER = {"tool": 0, "assistant": 1, "user": 2}

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
                try:
                    data = orjson.loads(line)
                    messages.append(Message(raw=data))
                except orjson.JSONDecodeError:
                    continue
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
    def execution_time(self) -> timedelta:
        total_ms = 0
        for msg in self.messages():
            if msg.type == "system" and msg.raw.get("subtype") == "turn_duration":
                total_ms += msg.raw.get("durationMs", 0)
        return timedelta(milliseconds=total_ms)

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

    @property
    def commits(self) -> list[dict]:
        result = []
        for msg in self.messages():
            info = msg.commit_info
            if info:
                result.append(info)
        return result

    @property
    def commit_count(self) -> int:
        return len(self.commits)

    @property
    def tool_loc(self) -> dict:
        added = 0
        removed = 0
        for msg in self.messages():
            edit = msg.edit_loc
            if edit:
                added += edit["added"]
                removed += edit["removed"]
            write = msg.write_loc
            if write:
                added += write
        return {"added": added, "removed": removed}

    @property
    def git_loc(self) -> dict | None:
        added = 0
        removed = 0
        found = False
        for msg in self.messages():
            diff = msg.git_diff_loc
            if diff:
                found = True
                added += diff["added"]
                removed += diff["removed"]
        if not found:
            return None
        return {"added": added, "removed": removed}

    def message_breakdown(self) -> dict:
        counts: Counter[tuple[str, str]] = Counter()
        for msg in self.messages():
            cat = msg.breakdown_category
            if cat:
                key = (cat["category"], cat["type"])
                counts[key] += 1

        breakdown = []
        for (category, msg_type), count in counts.items():
            breakdown.append({
                "category": category,
                "count": count,
                "type": msg_type,
            })

        breakdown.sort(key=lambda x: (TYPE_ORDER.get(x["type"], 99), -x["count"]))

        total = sum(item["count"] for item in breakdown)
        return {"breakdown": breakdown, "total": total}
