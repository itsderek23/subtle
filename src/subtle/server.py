from fastapi import FastAPI

app = FastAPI(
    title="Subtle",
    description="Claude Code session log explorer",
    version="0.1.0",
)


@app.get("/")
def index():
    return {"message": "Hello World"}
