from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
if not TEMPLATES_DIR.exists():
    PROJECT_ROOT = PACKAGE_DIR.parent.parent
    TEMPLATES_DIR = PROJECT_ROOT / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def sessions_list(request: Request):
    return templates.TemplateResponse(request, "sessions_list.html")


@router.get("/session/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: str):
    return templates.TemplateResponse(request, "session_detail.html", {"session_id": session_id})
