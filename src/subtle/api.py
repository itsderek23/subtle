from fastapi import APIRouter, HTTPException

from subtle.models import SessionLogFile

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
            "input_tokens": s.total_input_tokens,
            "output_tokens": s.total_output_tokens,
        }
        for s in sessions
    ]


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
