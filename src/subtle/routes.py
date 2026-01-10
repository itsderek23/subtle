from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def sessions_list(request: Request):
    return templates.TemplateResponse(request, "sessions_list.html")


@router.get("/session/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: str):
    return templates.TemplateResponse(request, "session_detail.html", {"session_id": session_id})
