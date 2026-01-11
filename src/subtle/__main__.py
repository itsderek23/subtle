import argparse
import os

import uvicorn
from subtle.server import app


def main():
    parser = argparse.ArgumentParser(description="Subtle - Claude Code log explorer")
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=None,
        help="Port to run the server on (default: 8000, or PORT env var)"
    )
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
