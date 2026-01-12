from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from subtle.api import router as api_router
from subtle.routes import router as page_router

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
if not STATIC_DIR.exists():
    PROJECT_ROOT = PACKAGE_DIR.parent.parent
    STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(
    title="Subtle",
    description="Claude Code session log explorer",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)
app.include_router(page_router)
