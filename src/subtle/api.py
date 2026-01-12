import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import orjson
from fastapi import APIRouter, HTTPException

from subtle.models import SessionLogFile


def _extract_searchable_text(message: dict) -> str:
    parts = []
    msg = message.get("message", {})
    content = msg.get("content")

    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if "thinking" in block:
                parts.append(block["thinking"])
            if "text" in block:
                parts.append(block["text"])
            if "name" in block:
                parts.append(block["name"])
            if "input" in block:
                inp = block["input"]
                parts.append(orjson.dumps(inp).decode() if isinstance(inp, dict) else str(inp))

    return " ".join(parts)


def _iter_messages_with_text(path: Path):
    with open(path, "r") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                message = orjson.loads(line)
                text = _extract_searchable_text(message)
                yield i, text
            except orjson.JSONDecodeError:
                continue


def _search_file(path: Path, query: str) -> str | None:
    query_lower = query.lower()
    for _, text in _iter_messages_with_text(path):
        if query_lower in text.lower():
            return path.stem
    return None

router = APIRouter(prefix="/api")


def filter_sessions_by_days(sessions: list[SessionLogFile], days: int) -> list[SessionLogFile]:
    cutoff = datetime.now() - timedelta(days=days - 1)
    return [s for s in sessions if datetime.fromtimestamp(os.path.getmtime(s.path)) >= cutoff]


@router.get("/sessions")
def list_sessions(days: int = 7):
    sessions = filter_sessions_by_days(SessionLogFile.all(), days)
    result = []
    for s in sessions:
        breakdown = s.execution_breakdown
        result.append({
            "session_id": s.session_id,
            "project_name": s.project_name,
            "project_path": s.project_path,
            "description": s.description,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "duration_seconds": s.duration.total_seconds() if s.duration else None,
            "agent_time_seconds": breakdown.agent_ms / 1000,
            "tool_time_seconds": breakdown.tool_ms / 1000,
            "input_tokens": s.total_input_tokens,
            "output_tokens": s.total_output_tokens,
            "commit_count": s.commit_count,
            "git_loc": s.git_loc,
        })
    return result


def _get_week_dates(start_date: datetime, days: int = 7) -> list[datetime]:
    return [start_date - timedelta(days=i) for i in range(days - 1, -1, -1)]


def _aggregate_daily_time(sessions: list[SessionLogFile]) -> dict[str, dict]:
    daily: dict[str, dict] = {}
    for s in sessions:
        if not s.start_time:
            continue
        local_time = s.start_time.replace(tzinfo=None)
        date_str = local_time.strftime("%Y-%m-%d")
        if date_str not in daily:
            daily[date_str] = {"ai_seconds": 0, "tool_seconds": 0}
        breakdown = s.execution_breakdown
        daily[date_str]["ai_seconds"] += breakdown.agent_ms / 1000
        daily[date_str]["tool_seconds"] += breakdown.tool_ms / 1000
    return daily


def _build_week_data(dates: list[datetime], daily: dict[str, dict]) -> list[dict]:
    result = []
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        weekday = d.strftime("%a")
        day_data = daily.get(date_str, {"ai_seconds": 0, "tool_seconds": 0})
        hours = (day_data["ai_seconds"] + day_data["tool_seconds"]) / 3600
        result.append({
            "weekday": weekday,
            "date": date_str,
            "hours": round(hours, 2),
        })
    return result


@router.get("/sessions/daily-usage")
def get_daily_usage(days: int = 7):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    current_week_dates = _get_week_dates(today, days)
    previous_week_start = today - timedelta(days=days)
    previous_week_dates = _get_week_dates(previous_week_start, days)

    all_sessions = SessionLogFile.all()
    cutoff = previous_week_dates[0]
    sessions = [
        s for s in all_sessions
        if s.start_time and s.start_time.replace(tzinfo=None) >= cutoff
    ]

    daily = _aggregate_daily_time(sessions)

    current_week = _build_week_data(current_week_dates, daily)
    previous_week = _build_week_data(previous_week_dates, daily)

    current_commits = sum(
        s.commit_count for s in sessions
        if s.start_time and s.start_time.replace(tzinfo=None) >= current_week_dates[0]
    )
    previous_commits = sum(
        s.commit_count for s in sessions
        if s.start_time and s.start_time.replace(tzinfo=None) < current_week_dates[0]
    )

    return {
        "current_week": current_week,
        "previous_week": previous_week,
        "current_commits": current_commits,
        "previous_commits": previous_commits,
    }


@router.get("/sessions/search")
def search_sessions(q: str, days: int = 7):
    sessions = filter_sessions_by_days(SessionLogFile.all(), days)
    paths = [s.path for s in sessions]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda p: _search_file(p, q), paths))

    return {
        "query": q,
        "matching_session_ids": [r for r in results if r],
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    breakdown = session.execution_breakdown
    return {
        "session_id": session.session_id,
        "duration_seconds": session.duration.total_seconds() if session.duration else None,
        "agent_time_seconds": breakdown.agent_ms / 1000,
        "tool_time_seconds": breakdown.tool_ms / 1000,
        "tool_time_breakdown": {k: v / 1000 for k, v in breakdown.tool_breakdown.items()},
        "error_count": session.error_count,
    }


@router.get("/sessions/{session_id}/messages/search")
def search_messages(session_id: str, q: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    query_lower = q.lower()
    matching_indices = [
        i for i, text in _iter_messages_with_text(session.path)
        if query_lower in text.lower()
    ]

    return {
        "query": q,
        "matching_indices": matching_indices,
    }


EXCLUDED_TOOLS = {"AskUserQuestion"}


def _track_tool_use(item: dict, ts, tool_uses: dict[str, float]) -> None:
    tool_id = item.get("id")
    tool_name = item.get("name", "")
    if not tool_id or not ts:
        return
    if tool_name in EXCLUDED_TOOLS:
        return
    tool_uses[tool_id] = ts.timestamp()


def _calculate_tool_duration(item: dict, ts, tool_uses: dict[str, float]) -> float | None:
    tool_id = item.get("tool_use_id")
    if not tool_id or not ts:
        return None
    if tool_id not in tool_uses:
        return None
    duration = ts.timestamp() - tool_uses[tool_id]
    del tool_uses[tool_id]
    return duration


def _process_content_items(content, ts, tool_uses: dict[str, float]) -> float | None:
    if not isinstance(content, list):
        return None

    duration_seconds = None
    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "tool_use":
            _track_tool_use(item, ts, tool_uses)
        elif item_type == "tool_result":
            duration_seconds = _calculate_tool_duration(item, ts, tool_uses)

    return duration_seconds


def _extract_text_content(m) -> str:
    message = m.raw.get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "\n\n".join(text_parts)
    return ""


def _extract_thinking(m) -> str | None:
    message = m.raw.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict) and item.get("type") == "thinking":
            return item.get("thinking", "")
    return None


def _truncate_command(cmd: str, max_len: int = 100) -> str:
    return cmd[:max_len] + "..." if len(cmd) > max_len else cmd


def _build_edit_summary(inp: dict) -> dict | None:
    if "old_string" not in inp or "new_string" not in inp:
        return None
    return {
        "old_lines": len(inp["old_string"].splitlines()),
        "new_lines": len(inp["new_string"].splitlines()),
    }


def _build_tool_info(item: dict) -> dict:
    inp = item.get("input", {})
    tool_info = {
        "id": item.get("id"),
        "name": item.get("name", ""),
    }

    for field in ("file_path", "pattern", "query"):
        if field in inp:
            tool_info[field] = inp[field]

    if "command" in inp:
        tool_info["command"] = _truncate_command(inp["command"])

    edit_summary = _build_edit_summary(inp)
    if edit_summary:
        tool_info["edit_summary"] = edit_summary

    if "content" in inp and "file_path" in inp:
        tool_info["write_lines"] = len(inp["content"].splitlines())

    return tool_info


def _extract_tool_uses(m) -> list[dict]:
    message = m.raw.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []
    return [
        _build_tool_info(item)
        for item in content
        if isinstance(item, dict) and item.get("type") == "tool_use"
    ]


def _truncate_preview(content, max_len: int = 200) -> str:
    text = content if isinstance(content, str) else str(content)
    return text[:max_len] + "..." if len(text) > max_len else text


def _build_tool_result(item: dict) -> dict:
    return {
        "tool_use_id": item.get("tool_use_id"),
        "is_error": item.get("is_error", False),
        "preview": _truncate_preview(item.get("content", "")),
    }


def _extract_tool_results(m) -> list[dict]:
    message = m.raw.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []
    return [
        _build_tool_result(item)
        for item in content
        if isinstance(item, dict) and item.get("type") == "tool_result"
    ]


def _build_message_dict(index: int, m, duration_seconds: float | None) -> dict:
    ts = m.timestamp
    return {
        "index": index,
        "type": m.type,
        "preview": m.preview,
        "text_content": _extract_text_content(m),
        "thinking": _extract_thinking(m),
        "tool_uses": _extract_tool_uses(m),
        "tool_results": _extract_tool_results(m),
        "timestamp": ts.isoformat() if ts else None,
        "model": m.model,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "duration_seconds": duration_seconds,
        "is_commit": m.is_commit,
        "commit_info": m.commit_info,
        "edit_loc": m.edit_loc,
        "write_loc": m.write_loc,
        "git_diff_loc": m.git_diff_loc,
        "is_rejection": m.is_rejection,
        "is_tool_error": m.is_tool_error,
        "is_command_failure": m.is_command_failure,
    }


def _calculate_message_duration(m, prev_user_ts: float | None, tool_uses: dict[str, float]) -> float | None:
    ts = m.timestamp
    content = m.raw.get("message", {}).get("content")
    duration = _process_content_items(content, ts, tool_uses)

    is_assistant_response = m.type == "assistant" and prev_user_ts and ts
    if is_assistant_response:
        duration = ts.timestamp() - prev_user_ts

    return duration


def _process_messages(messages) -> list[dict]:
    tool_uses: dict[str, float] = {}
    prev_user_ts = None
    result = []

    for i, m in enumerate(messages):
        duration_seconds = _calculate_message_duration(m, prev_user_ts, tool_uses)

        if m.type == "user" and m.timestamp:
            prev_user_ts = m.timestamp.timestamp()

        result.append(_build_message_dict(i, m, duration_seconds))

    return result


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return _process_messages(session.messages())


@router.get("/messages/{session_id}/{index}")
def get_message(session_id: str, index: int):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = session.messages()
    if index < 0 or index >= len(messages):
        raise HTTPException(status_code=404, detail="Message not found")
    return messages[index].raw


@router.get("/sessions/{session_id}/message_breakdown")
def get_message_breakdown(session_id: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.message_breakdown()
