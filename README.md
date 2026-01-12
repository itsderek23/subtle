# Subtle - Claude Code session log explorer

Explore and analyze your Claude Code session logs with ease. Subtle is a local, privacy-focused web app that helps you understand your Claude Code usage patterns.

_👇 Click the image for a short video:_
<a href="./docs/subtle_recording.gif" target="_blank"><img src="./docs/screenshot.png" /></a>

## Table of Contents

- [Privacy](#privacy)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)

## Privacy

Subtle runs entirely on your local machine:

* All data processing happens locally
* No telemetry
* Your conversations never leave your computer

## Prerequisites

- Python 3.10 or higher
- Claude Code session logs (stored in `~/.claude/projects/`)

## Installation

```bash
# uv
uv add subtle-claude-code

# Or with pip
pip install subtle-claude-code
```

## Usage

```bash
subtle start
```

Server starts at http://127.0.0.1:8000

For the list of available options, run:

```bash
subtle --help
```

### Custom Port

```bash
subtle start --port 3000
```

Or via environment variable:

```bash
PORT=3000 subtle start
```

## Development

### Setup

```bash
git clone https://github.com/itsderek23/subtle.git
cd subtle
uv sync
```

### Run locally

```bash
uv run subtle start
```

### Test

```bash
uv run pytest
```
