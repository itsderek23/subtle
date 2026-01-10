from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from subtle.api import router as api_router
from subtle.routes import router as page_router

app = FastAPI(
    title="Subtle",
    description="Claude Code session log explorer",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_router)
app.include_router(page_router)
