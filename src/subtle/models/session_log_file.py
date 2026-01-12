import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import orjson

from .message import Message

COMMAND_NAME_PATTERN = re.compile(r"<command-name>/?(\w+)</command-name>")
COMMAND_ARGS_PATTERN = re.compile(r"<command-args>(.*?)</command-args>")


def _parse_command_message(text: str) -> str | None:
    match = COMMAND_NAME_PATTERN.search(text)
    if not match:
        return None
    command = "/" + match.group(1)
    args_match = COMMAND_ARGS_PATTERN.search(text)
    if args_match and args_match.group(1).strip():
        command += " " + args_match.group(1).strip()
    return command


def _truncate_description(text: str, max_len: int = 100) -> str:
    first_line = text.split("\n")[0].strip()
    if len(first_line) > max_len:
        return first_line[:max_len] + "..."
    return first_line


SKIP_PREFIXES = (
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<system-reminder>",
)


def _is_clear_command(text: str) -> bool:
    return "<command-name>/clear</command-name>" in text


def _should_skip_message(text: str) -> bool:
    if not text:
        return True
    if any(text.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True
    if _is_clear_command(text):
        return True
    return False


def _extract_user_message_text(msg: Message) -> str | None:
    message = msg.raw.get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        text = content.strip()
        if _should_skip_message(text):
            return None
        return text
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "").strip()
                if text and not _should_skip_message(text):
                    return text
    return None


@dataclass
class ExecutionBreakdown:
    agent_ms: float = 0
    tool_ms: float = 0
    tool_breakdown: dict[str, float] = field(default_factory=dict)

TYPE_ORDER = {"tool": 0, "assistant": 1, "user": 2}

PROJECTS_DIR = Path.home() / ".claude" / "projects"

EXCLUDED_TOOLS = {"AskUserQuestion"}


def _calculate_turn_duration(messages: list) -> float:
    return sum(
        msg.raw.get("durationMs", 0)
        for msg in messages
        if msg.type == "system" and msg.raw.get("subtype") == "turn_duration"
    )


def _track_tool_use(item: dict, ts: datetime, tool_uses: dict[str, tuple[str, datetime]]) -> None:
    tool_id = item.get("id")
    tool_name = item.get("name", "unknown")
    if not tool_id:
        return
    if tool_name in EXCLUDED_TOOLS:
        return
    tool_uses[tool_id] = (tool_name, ts)


def _process_tool_result(
    item: dict, ts: datetime, tool_uses: dict[str, tuple[str, datetime]]
) -> tuple[str, float] | None:
    tool_id = item.get("tool_use_id")
    if not tool_id or tool_id not in tool_uses:
        return None
    tool_name, use_ts = tool_uses[tool_id]
    duration_ms = (ts - use_ts).total_seconds() * 1000
    del tool_uses[tool_id]
    return (tool_name, duration_ms)


def _process_content_item(
    item: dict, ts: datetime, tool_uses: dict[str, tuple[str, datetime]]
) -> tuple[str, float] | None:
    item_type = item.get("type")
    if item_type == "tool_use":
        _track_tool_use(item, ts, tool_uses)
        return None
    if item_type == "tool_result":
        return _process_tool_result(item, ts, tool_uses)
    return None


def _iter_content_items(content) -> list[dict]:
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def _process_message_content(
    content, ts: datetime, tool_uses: dict[str, tuple[str, datetime]]
) -> list[tuple[str, float]]:
    tool_durations = []
    for item in _iter_content_items(content):
        result = _process_content_item(item, ts, tool_uses)
        if result:
            tool_durations.append(result)
    return tool_durations


def _is_agent_response(prev_type: str | None, current_type: str) -> bool:
    return prev_type in ("user", "assistant") and current_type == "assistant"


def _calculate_gap_ms(prev_ts: datetime, current_ts: datetime) -> float:
    return (current_ts - prev_ts).total_seconds() * 1000


def _iter_timed_messages(messages: list):
    for msg in messages:
        if msg.timestamp and msg.type != "system":
            yield msg


def _calculate_agent_time(messages: list) -> float:
    agent_ms = 0.0
    prev_ts = None
    prev_type = None

    for msg in _iter_timed_messages(messages):
        if prev_ts and _is_agent_response(prev_type, msg.type):
            agent_ms += _calculate_gap_ms(prev_ts, msg.timestamp)

        prev_ts = msg.timestamp
        prev_type = msg.type

    return agent_ms


def _calculate_tool_breakdown(messages: list) -> tuple[float, dict[str, float]]:
    tool_uses: dict[str, tuple[str, datetime]] = {}
    tool_breakdown: dict[str, float] = defaultdict(float)
    tool_ms = 0.0

    for msg in messages:
        ts = msg.timestamp
        if not ts or msg.type == "system":
            continue

        content = msg.raw.get("message", {}).get("content")
        for tool_name, duration_ms in _process_message_content(content, ts, tool_uses):
            tool_ms += duration_ms
            tool_breakdown[tool_name] += duration_ms

    return tool_ms, dict(tool_breakdown)


def decode_project_path(encoded: str) -> str:
    if encoded.startswith("-"):
        encoded = "/" + encoded[1:]
    return encoded.replace("-", "/")


def _is_valid_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".")


def _iter_project_dirs():
    if not PROJECTS_DIR.exists():
        return
    for project_dir in PROJECTS_DIR.iterdir():
        if _is_valid_dir(project_dir):
            yield project_dir


def _iter_log_files(project_dir: Path):
    for log_file in project_dir.glob("*.jsonl"):
        if not log_file.name.startswith("."):
            yield log_file


@dataclass
class SessionLogFile:
    path: Path
    project_dir: Path

    @classmethod
    def all(cls) -> list["SessionLogFile"]:
        sessions = [
            cls(path=log_file, project_dir=project_dir)
            for project_dir in _iter_project_dirs()
            for log_file in _iter_log_files(project_dir)
        ]
        sessions.sort(key=lambda s: s.path.stat().st_mtime, reverse=True)
        return sessions

    @classmethod
    def from_id(cls, session_id: str) -> "SessionLogFile | None":
        for project_dir in _iter_project_dirs():
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

    @property
    def description(self) -> str:
        for msg in self.messages():
            if msg.type != "user":
                continue
            text = _extract_user_message_text(msg)
            if not text:
                continue
            parsed = _parse_command_message(text)
            if parsed:
                return _truncate_description(parsed)
            return _truncate_description(text)
        return "—"

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
        timestamps = [msg.timestamp for msg in self.messages() if msg.timestamp]
        return min(timestamps) if timestamps else None

    @property
    def end_time(self) -> datetime | None:
        timestamps = [msg.timestamp for msg in self.messages() if msg.timestamp]
        return max(timestamps) if timestamps else None

    @property
    def duration(self) -> timedelta | None:
        start = self.start_time
        end = self.end_time
        if start and end:
            return end - start
        return None

    @property
    def execution_time(self) -> timedelta:
        breakdown = self.execution_breakdown
        return timedelta(milliseconds=breakdown.agent_ms)

    @property
    def execution_breakdown(self) -> ExecutionBreakdown:
        messages = self.messages()

        turn_duration_ms = _calculate_turn_duration(messages)
        agent_ms = turn_duration_ms if turn_duration_ms > 0 else _calculate_agent_time(messages)
        tool_ms, tool_breakdown = _calculate_tool_breakdown(messages)

        return ExecutionBreakdown(
            agent_ms=agent_ms,
            tool_ms=tool_ms,
            tool_breakdown=tool_breakdown,
        )

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

    @property
    def error_count(self) -> int:
        count = 0
        for msg in self.messages():
            if msg.is_tool_error or msg.is_command_failure:
                count += 1
        return count

    def _collect_category_counts(self) -> Counter[tuple[str, str]]:
        counts: Counter[tuple[str, str]] = Counter()
        for msg in self.messages():
            cat = msg.breakdown_category
            if cat:
                counts[(cat["category"], cat["type"])] += 1
        return counts

    def _build_breakdown_item(
        self, category: str, msg_type: str, count: int, tool_times: dict[str, float]
    ) -> dict:
        item: dict = {"category": category, "count": count, "type": msg_type}
        has_tool_time = msg_type == "tool" and category in tool_times
        if has_tool_time:
            item["time_seconds"] = tool_times[category] / 1000
        return item

    def message_breakdown(self) -> dict:
        counts = self._collect_category_counts()
        exec_breakdown = self.execution_breakdown
        tool_times = exec_breakdown.tool_breakdown

        breakdown = [
            self._build_breakdown_item(category, msg_type, count, tool_times)
            for (category, msg_type), count in counts.items()
        ]
        breakdown.sort(key=lambda x: (TYPE_ORDER.get(x["type"], 99), -x["count"]))

        return {
            "breakdown": breakdown,
            "total": sum(item["count"] for item in breakdown),
            "agent_time_seconds": exec_breakdown.agent_ms / 1000,
            "tool_time_seconds": exec_breakdown.tool_ms / 1000,
        }
