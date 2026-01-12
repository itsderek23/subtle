from fastapi import APIRouter, HTTPException

from subtle.models import SessionLogFile

router = APIRouter(prefix="/api")


@router.get("/sessions")
def list_sessions():
    sessions = SessionLogFile.all()
    result = []
    for s in sessions:
        breakdown = s.execution_breakdown
        result.append({
            "session_id": s.session_id,
            "project_name": s.project_name,
            "project_path": s.project_path,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "duration_seconds": s.duration.total_seconds() if s.duration else None,
            "agent_time_seconds": breakdown.agent_ms / 1000,
            "tool_time_seconds": breakdown.tool_ms / 1000,
            "input_tokens": s.total_input_tokens,
            "output_tokens": s.total_output_tokens,
            "commit_count": s.commit_count,
            "error_count": s.error_count,
            "tool_loc": s.tool_loc,
            "git_loc": s.git_loc,
        })
    return result


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


def _build_message_dict(index: int, m, duration_seconds: float | None) -> dict:
    ts = m.timestamp
    return {
        "index": index,
        "type": m.type,
        "preview": m.preview,
        "timestamp": ts.isoformat() if ts else None,
        "model": m.model,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "duration_seconds": duration_seconds,
        "is_commit": m.is_commit,
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
