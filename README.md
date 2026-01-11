# Subtle

Explore and analyze your Claude Code logs with ease.

![screenshot](docs/screenshot.png)

## Setup

```bash
uv sync
```

## Run

```bash
uv run python -m subtle
```

Server starts at http://127.0.0.1:8000

### Custom Port

Specify a port via command line:

```bash
uv run python -m subtle --port 3000
uv run python -m subtle -p 3000
```

Or via environment variable:

```bash
PORT=3000 uv run python -m subtle
```

CLI arguments take precedence over environment variables.

## Test

```bash
uv run pytest
```
