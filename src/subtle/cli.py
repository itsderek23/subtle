import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        prog="subtle",
        description="Claude Code session log explorer"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    start_parser = subparsers.add_parser("start", help="Start the web server")
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Port to run the server on (default: 8000, or PORT env var)"
    )
    start_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    subparsers.add_parser("version", help="Show version information")

    args = parser.parse_args()

    if args.command == "start":
        import uvicorn
        from subtle.server import app
        port = args.port or int(os.environ.get("PORT", 8000))
        uvicorn.run(app, host=args.host, port=port)
    elif args.command == "version":
        import sys
        from subtle import __version__
        print(f"subtle {__version__}")
        print(f"Python {sys.version}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
