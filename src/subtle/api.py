from concurrent.futures import ThreadPoolExecutor
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


def _search_file(path: Path, query: str) -> str | None:
    query_lower = query.lower()
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                message = orjson.loads(line)
                text = _extract_searchable_text(message)
                if query_lower in text.lower():
                    return path.stem
            except orjson.JSONDecodeError:
                continue
    return None

router = APIRouter(prefix="/api")


@router.get("/sessions")
def list_sessions():
    sessions = SessionLogFile.all()
    return [
        {
            "session_id": s.session_id,
            "project_name": s.project_name,
            "project_path": s.project_path,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "duration_seconds": s.duration.total_seconds() if s.duration else None,
            "execution_time_seconds": s.execution_time.total_seconds(),
            "input_tokens": s.total_input_tokens,
            "output_tokens": s.total_output_tokens,
            "commit_count": s.commit_count,
            "error_count": s.error_count,
            "tool_loc": s.tool_loc,
            "git_loc": s.git_loc,
        }
        for s in sessions
    ]


@router.get("/sessions/search")
def search_sessions(q: str):
    sessions = SessionLogFile.all()
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
    return {
        "session_id": session.session_id,
        "duration_seconds": session.duration.total_seconds() if session.duration else None,
        "execution_time_seconds": session.execution_time.total_seconds(),
        "error_count": session.error_count,
    }


@router.get("/sessions/{session_id}/messages/search")
def search_messages(session_id: str, q: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    matching_indices = []
    query_lower = q.lower()
    with open(session.path, "r") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                message = orjson.loads(line)
                text = _extract_searchable_text(message)
                if query_lower in text.lower():
                    matching_indices.append(i)
            except orjson.JSONDecodeError:
                continue

    return {
        "query": q,
        "matching_indices": matching_indices,
    }


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str):
    session = SessionLogFile.from_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        {
            "index": i,
            "type": m.type,
            "preview": m.preview,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            "model": m.model,
            "input_tokens": m.input_tokens,
            "output_tokens": m.output_tokens,
            "tools": m.tools,
            "is_commit": m.is_commit,
            "edit_loc": m.edit_loc,
            "write_loc": m.write_loc,
            "git_diff_loc": m.git_diff_loc,
            "is_rejection": m.is_rejection,
            "is_tool_error": m.is_tool_error,
            "is_command_failure": m.is_command_failure,
        }
        for i, m in enumerate(session.messages())
    ]


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
