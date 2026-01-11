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


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.messages()
    tool_uses: dict[str, float] = {}
    prev_user_ts = None
    excluded_tools = {"AskUserQuestion"}
    result = []

    for i, m in enumerate(messages):
        ts = m.timestamp
        duration_seconds = None

        content = m.raw.get("message", {}).get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                if item.get("type") == "tool_use":
                    tool_id = item.get("id")
                    tool_name = item.get("name", "")
                    if tool_id and ts and tool_name not in excluded_tools:
                        tool_uses[tool_id] = ts.timestamp()

                elif item.get("type") == "tool_result":
                    tool_id = item.get("tool_use_id")
                    if tool_id and tool_id in tool_uses and ts:
                        duration_seconds = ts.timestamp() - tool_uses[tool_id]
                        del tool_uses[tool_id]

        if m.type == "assistant" and prev_user_ts and ts:
            duration_seconds = ts.timestamp() - prev_user_ts

        if m.type == "user" and ts:
            prev_user_ts = ts.timestamp()

        result.append({
            "index": i,
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
        })

    return result


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
