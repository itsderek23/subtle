from fastapi import FastAPI

from subtle.api import router as api_router

app = FastAPI(
    title="Subtle",
    description="Claude Code session log explorer",
    version="0.1.0",
)

app.include_router(api_router)


@app.get("/")
def index():
    return {"message": "Hello World"}
